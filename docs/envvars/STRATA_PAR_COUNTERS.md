# `STRATA_PAR_COUNTERS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

研究・診断用の並列処理カウンターを有効にします。Strata の CUDA batch engine は batch window、drain、admission、idle tick、expert 処理の集計を stderr に出します。Python サーバーは空き slot を待った要求数と待ち時間を集計し、batch serving 中の `/metrics` JSON に `live.par_counters` として追加します。どちらもカウンターと観測値の出力で、batch の実行方式を切り替える設定ではありません。

## 値と判定

| 読み取り箇所 | 有効になる値 | 無効になる値 | 読み取り時期 |
|---|---|---|---|
| C++ `ParCounters` | 値全体が ASCII の `1` ちょうど | 未設定、空文字、`01`、`1 `、`true`、その他すべて | batch 処理経路で `ParCounters` を構築した時 |
| Python サーバー | 値全体が文字列 `1` ちょうど | 未設定、空文字、`01`、`1 `、`true`、その他すべて | `serve/server.py` のモジュール import 時 |

C++ は `getenv()` の結果が非 null で、先頭文字が `1`、かつ次の文字が終端 `\0` であることを検査します。Python は `os.environ.get(...) == "1"` で文字列全体を比較します。数値変換、trim、大文字小文字変換、fallback はありません。C++ の `on_` はオブジェクトに保持され、オブジェクト構築後の環境変更では変わりません。Python の `PAR_COUNTERS` は import 時の値を保持します。

## 有効になる条件

- C++ カウンターは `generate.cpp` の `--batch` slot 処理に置かれています。通常の単一要求経路ではこの `ParCounters` を使いません。batch slots 自体は `--batch N` / `--slots N` によって選択されます。
- サーバー側のカウンターは `PAR_COUNTERS` が真でも、エンジンの `batch` 値が正の場合だけ status に現れます。slot が空かず、要求が空き slot を待って取得した場合にのみ待ち数・待ち時間が加算されます。
- サーバー自身は親プロセスの環境を import 時に読みます。一方、エンジン子プロセス用環境は `child_env()` が `os.environ` をコピーし、設定プロファイルの `cfg.env` を後から重ねます。このため `cfg.env` の `STRATA_PAR_COUNTERS` は C++ エンジンの値を上書きできますが、既に import 済みの Python 側 `PAR_COUNTERS` は変えません。
- サーバー実装は Python 標準ライブラリのプロセス環境を読むだけです。C++ の参照は batch engine 実装内です。外部ライブラリや GPU driver に対するこの名前の転送・設定は確認できません。

## 実行時の詳細

C++ の `ParCounters` は batch 処理中に window ごとの行数・有効 slot 数を加算します。pipelined batch では control line の前の drain と in-flight group 数も記録します。カウンターが ON のときだけ `pc.on()` が true となり、drain 時の in-flight group 数を数えるための走査も実行されます。batch slots がすべて idle になった時に `flush()` が呼ばれ、集計対象がある場合に stderr へ `strata par: ...`、必要なら `strata par experts: ...` を出力し、flush 後にカウンターをリセットします。途中でエラーを返す経路では、その時点までの集計を必ず flush する処理は確認できません。この変数自体による警告、終了、エラー経路はありません。

Python サーバーでは、要求が空き slot を得た時点で、それ以前に slot 待ちへ入っていた場合の経過秒数を `queue_wait_s` に足し、`queued` を 1 増やします。待ち中にキャンセルされるなど、slot 取得まで至らない場合はこの加算箇所を通りません。カウンター辞書は engine wrapper に作られ、slot condition が既にある場合には再作成されません。`metrics()` は batch serving のとき辞書のコピーを `live.par_counters` に含め、`GET /metrics` の JSON 応答がそれを返します。実装コメント (`serve/server.py:330`) は `/v1/status` に表示としていますが、`v1_status()` の返却値 (`:5069-5096`) には `live` フィールドがなく、このカウンターも含まれません。サーバー側の値は stdout/stderr ログではなく `/metrics` 応答で観測します。

## 根拠

- `include/strata/program/par_counters.hpp:25-30` は C++ の厳密な `"1"` 判定とオブジェクト内 cache、`:32-74` は集計項目・stderr 出力・flush 後の reset を定義します。
- `src/program/generate.cpp:12499-12552` は batch slots 経路に `ParCounters` を置きます。`:12850,12963-12967` と `:13269,13336,13461-13464` は通常・pipelined batch で開始、window 集計、idle 時 flush する位置です。`:13503-13509` は ON の場合に drain の in-flight group 数を数えます。
- `serve/server.py:330` は import 時の完全一致判定、`:1206-1211` は server wrapper のカウンター初期化、`:2015-2029` は slot 待ちの終了時に待ち回数と秒数を更新する処理です。
- `serve/server.py:3747-3760` は子プロセス環境を親環境からコピーして `cfg.env` を適用します。`:1077-1079` はその環境を Strata engine subprocess に渡します。
- `serve/server.py:4955-4960,4985-5007` は `/metrics` JSON の `live.par_counters` を構築する処理、`:7108-7121` は `/metrics` endpoint の応答です。`:5053-5096` の `/v1/status` 応答にはこのフィールドがありません（`:330` のコメントの記述とは異なります）。
- `src/program/generate.cpp:3196-3197,6016-6021` は `--batch` / `--slots` と batch slot の役割を示します。`docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。
