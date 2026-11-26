# STRATA_PAR_COUNTERS

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

研究・診断用の計数を有効にする。Strata エンジンでは、バッチ並列処理のウィンドウ、パイプラインの drain、admission などをホスト側で集計し、バッチ処理が idle になったとき stderr に strata par: の行を出す。設定は計数の分岐だけを切り替え、スロット選択や生成結果を変更する処理は見つからない。読み取りと集計実装は ParCounters（engine/include/strata/program/par_counters.hpp:25-30,32-74）、生成ループでの生成と flush は engine/src/program/generate.cpp:16831-16837,17469-17475,18358-18364。

Strata の Python サーバーは同じ値を起動時に判定し、並列スロットで空きを待ったリクエスト数と待ち時間の合計を記録する。バッチサーバーの /metrics JSON の live.par_counters にその累積値を含める。これはエンジンの stderr 集計とは別のカウンターである（terminal/serve/server_parts/base.py:280、terminal/serve/server.py:2193-2199,5263-5265,5295-5306,7390-7404）。

## 値と判定

どちらの読み取り箇所も値全体を文字列 1 と比較する。数値変換、前後空白の除去、大文字小文字変換はしない。C++ は getenv が非 null で、先頭が 1 かつ次の文字が終端 NUL のときだけ有効。Python は os.environ.get(...) == "1" で判定する。未設定、空文字、0、01、1anything、true、TRUE、前後に空白がある値はいずれも無効。CLI 引数や別環境変数による上書き・fallback は実装にない（engine/include/strata/program/par_counters.hpp:29、terminal/serve/server_parts/base.py:280）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| エンジン ParCounters | OFF | 文字列全体が 1 | 空文字、0、01、1x、true、空白付きなど |
| Python サーバー | OFF | 文字列全体が 1 | 空文字、0、01、1x、true、空白付きなど |

## 有効になる条件

- エンジン側は generate.cpp のバッチ処理経路で ParCounters が構築される場合に計数する。ビルド macro、OS、backend、モデル状態による追加の環境値判定はこの実装箇所にない。計数は有効値でも、計測対象のバッチウィンドウ等が起きなければ報告する値がなく、flush は出力しない（engine/src/program/generate.cpp:16831,17471-17475,18360-18364、engine/include/strata/program/par_counters.hpp:52-54）。
- サーバー側の live.par_counters は self.engine.batch を整数化した値が 0 以外のときだけ /metrics JSON に含まれる。環境変数が有効でも batch が 0 のときはこのフィールドを追加しない（terminal/serve/server.py:5295-5306）。
- サーバーでの値判定は base.py のモジュール読み込み時に定数 PAR_COUNTERS として行われる。実行中の環境変更を再読する処理はない（terminal/serve/server_parts/base.py:280、terminal/serve/server.py:80-106）。
- エンジン側は ParCounters オブジェクトの構築時に読み取る。生成ループ中に値を再読したり、キャッシュ値を更新したりする処理はない（engine/include/strata/program/par_counters.hpp:25-30、engine/src/program/generate.cpp:16831）。

## 実行時の詳細

エンジンでは on_ が false のとき各計数フックが早期 return する。true のとき、通常バッチ経路はウィンドウごとに行数と live slot 数を加算し、すべての slot が idle になった時点で flush する。パイプライン経路はバッチ処理が idle になった時点で同様に flush する。flush の書式には windows、rows、used、live slot/window のヒストグラム、drain の回数・待ち時間、admission 数・prompt token 数と時間、adaptive round、launch できなかった tick の理由が含まれる。ただし、現行 generate.cpp にある ParCounters の呼び出し箇所では adapt と no_launch の更新メソッドを呼んでいないため、これら2項目はこの経路では加算されない。expert の差分値は対象区間に記録値がある場合にだけ追加行にする（engine/include/strata/program/par_counters.hpp:32-74、engine/src/program/generate.cpp:17219-17231,17469-17475,18048-18054,18358-18364,18415-18424,23725-23728）。

パイプラインの drain 計数では、対象の制御行が BGEN で始まるかを見て admission drain とその他に分類する。この計数フックはパイプラインで drain する分岐にある。drain 時間は steady_clock で計測される。カウンター有効時は計測のため drain 前後にホスト時計を読むが、この設定専用の GPU 同期呼び出しはない（engine/src/program/generate.cpp:18415-18424、engine/include/strata/program/par_counters.hpp:37-42）。

サーバーでは、リクエストが空き slot を待ち始めたとき admit_since を記録し、slot を獲得したとき queued を1増やし、経過秒を queue_wait_s に加える。したがって、待ちの途中で期限切れなどにより獲得へ至らなかった要求はこの成功時加算箇所を通らない。カウンター辞書はサーバーインスタンス初期化時に作成され、slot_cv が既にある再初期化では辞書も維持される。/metrics JSON の live にはコピーが入るため、読み出し側の変更で内部値は変わらない（terminal/serve/server.py:1006-1018,2182-2201,5295-5306,7390-7404）。

## ログと測定値

エンジンの報告は stderr で、実装上の先頭文字列は strata par: wall ...。対象カウンターが未記録なら出力しない。Python サーバー側はログを出さず、認証済み /metrics の通常 JSON 応答に live.par_counters として queued および queue_wait_s を含める。/metrics が Prometheus の text format を要求する場合は別の描画経路に入り、JSON の live フィールドは返さない（engine/include/strata/program/par_counters.hpp:52-73、terminal/serve/server.py:5295-5306,7390-7404）。

ソースと docs/DETAILS.md に、この変数による性能測定値や比較条件の記載は確認できなかったため、測定値は記載しない。

## 根拠

- engine/include/strata/program/par_counters.hpp:25-30,32-74 — C++ 側の値判定、カウンター、stderr 出力。
- engine/src/program/generate.cpp:16831-16837,17219-17231,17469-17475,18048-18054,18358-18364,18415-18424,23725-23728 — エンジンでの構築、計数フック、flush。
- terminal/serve/server_parts/base.py:280 — Python 側の厳密な文字列比較。
- terminal/serve/server.py:80-106,1006-1018,2193-2199,5263-5265,5295-5306,7390-7404 — import、カウンター寿命、待ち計数、/metrics JSON への追加。
