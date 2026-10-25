# `STRATA_BATCH_TELEMETRY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

バッチ推論中の decode window について、処理した verifier row 数と稼働中の request slot 数を低頻度で計測し、エンジン標準出力に `BSTAT` 行として出します。さらに `--batch-groups` による pipelined path では、各 stage の起動から完了 poll までの host 側経過時間を `PSTAT` 行として出します。GPU kernel の使用率や request が実際に出力した token 数を測るものではありません。

通常利用者向けの設定経路はサーバーの `--batch-telemetry` / `--no-batch-telemetry`、run config の `batch_telemetry`、または CLI/profile 経由です。ネイティブエンジンに直接環境変数を渡す場合は、文字列が厳密に `1` の場合だけ有効です。

## 値と判定

| 読み取り経路 | 値 | 結果 |
|---|---|---|
| ネイティブエンジン (`generate.cpp`) | unset、空文字、`0`、`true`、`01`、`1x` など | 無効 |
| ネイティブエンジン (`generate.cpp`) | 文字列全体が `1` | 有効 |
| `strata serve` CLI/profile の環境値解決 | 環境変数 unset | 下記の config/profile/default を評価 |
| `strata serve` CLI/profile の環境値解決 | 環境変数が設定済み | 値が厳密に `1` のとき true、それ以外は false |

ネイティブ側は `getenv()` の非 null に加えて `env[0] == '1'` と `env[1] == '\0'` を確認します。前方一致や数値変換ではありません。値はバッチ生成ループの初期化時に一度読みます。エンジン実行中に環境を書き換えても反映されません。無効時に telemetry の protocol 行は出しません。

## 有効になる条件

- エンジンのバッチ生成経路で有効になります。通常の solo request path にはこの測定処理はありません。
- `BSTAT` は serial batch と pipelined batch の両方で、完了した batch window を数えます。
- `PSTAT` は `o.batch > 0 && o.batch_groups > 1 && stages.size() + 1 > 1` の pipelined path だけが対象です。stage 数が 2〜16 の範囲に限り sampler が有効です。
- CUDA/HIP/SYCL の backend 条件で環境変数の意味を変える分岐は、この読み取り箇所にはありません。

## 実行時の詳細

サーバーは `child_env()` で親環境をコピーし、config の `env` を反映した後、`batch_telemetry` 設定を適用してエンジンを起動します。サーバーの CLI 指定があればそれが config より優先されます。値が true なら子環境の変数を `1` にし、false なら削除します。どちらも明示されなければ継承値を保ちます。server 起動時に config 内の `batch_telemetry` が bool 以外なら `batch_telemetry must be true or false` で拒否します。

`strata` CLI の serve/profile 解決では、コマンド指定、保存済み profile、run config、環境変数、既定値の順で選択します。環境変数は設定済みの場合のみ評価し、厳密な `1` 以外を false とします。既定値は false です。環境変数が選ばれた場合、CLI は true/false を server の `--batch-telemetry` / `--no-batch-telemetry` に正規化して渡します。

`BSTAT` の集計は少なくとも1 row/window と1 active row/window がある window のみ受け付けます。処理 row は pipeline の padding row や batch MTP row を含み、active row はその window に表現された live slot 数です。サンプルは最初の含有 window から概ね1秒経過したときに出力され、全 slot が idle になったときは1秒未満でも最後の部分サンプルを出します。出力形式は `BSTAT <windows> <processed_rows> <active_rows> <elapsed_ms>` です。

pipelined path の `PSTAT` は stage 数、経過 microseconds、stage ごとの in-flight microseconds を出します。計測値には完了 poll までの待ち時間が含まれるため GPU kernel 利用率ではありません。Python サーバーは `BSTAT` / `PSTAT` 行を protocol sample として保存し、request の token 出力には流しません。文書上、monitor は BSTAT を rows/window と active slots/window、PSTAT を stage host span として表示します。

## 根拠

- `src/program/generate.cpp:11209-11220` — 環境変数の厳密な判定、sampler 初期化、BSTAT 出力。
- `src/program/generate.cpp:11535-11536,11695-11697` — serial/pipelined window 完了時に集計。
- `src/program/generate.cpp:11585-11587,11646,11732,11744,11759-11766` — pipelined 条件と PSTAT の測定・出力。
- `include/strata/core/batch_telemetry.hpp:12-47` — BSTAT の集計条件、約1秒ごとおよび idle 時の部分サンプル。
- `include/strata/core/batch_telemetry.hpp:49-108` — stage in-flight の host 時間集計と 2〜16 stage 条件。
- `serve/server.py:3349-3362,896-902,8121-8129,8192-8195` — 子環境の継承/config/CLI 優先とエンジン起動。
- `serve/server.py:8036-8037` — config 値の bool 検証。
- `serve/server.py:1182-1191` — BSTAT/PSTAT を解析し request 出力から除外。
- `strata_cli/cli.py:57-58,743-767,802-803` — CLI/profile の設定順、環境値の判定、server 引数への反映。
- `docs/TERMINAL.md:270` — monitor の値の説明と、solo path・古い engine では sample がない旨。
- `docs/DEVELOPER_INTEGRATION_HANDOFF.md:169` — stage host span は poll delay を含み GPU kernel occupancy ではない旨、および CUDA/HIP/SYCL で未 qualification の旨。

`docs/DETAILS.md` は調査対象 checkout に存在しません。Strata の資料では機能と monitor 表示が説明されていますが、この環境変数による native CUDA/HIP/SYCL ビルドや実機計測の結果は確認できませんでした。
