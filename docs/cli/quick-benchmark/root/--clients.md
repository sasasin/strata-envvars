# `--clients`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（実体: `python tools/strata_bench.py`） |
| オプション | `--clients` |
| 別名 | なし |
| 値 | 整数 `N`。parser で `int` に変換。ソース上の範囲制限なし |

## 役割

通常の quick benchmark suite に、N 個のリクエストを同時に送る負荷測定を追加します。サーバーの並列 slot 数より N が大きい場合、余分なリクエストは順番待ちになります。これは `strata bench run` の標準比較ベンチマークとは別のローカル計測です。

## 使い方

```sh
./bench.sh --clients 4
```

Windows では `BENCH.bat --clients 4` を使います。両 wrapper は引数を `tools/strata_bench.py` に渡します。Python を直接実行する場合は `python tools/strata_bench.py --clients 4` です。

## 値と既定値

- 省略時は `0` です。suite は `if self.clients` の条件でこの測定を呼ぶため、既定では並列リクエスト測定を行いません。
- `N` は `argparse` の `type=int` で変換されます。数値でない値は argparse のエラーになります。parser に正数の下限や上限は定義されていません。
- 0 は明示しても測定を省略します。負数は parser を通り、truthy 値として測定関数を呼びますが、`range(N)` が空になるためリクエスト thread は作られず、結果には負の client 数と 0 tok/s が記録されます。実用上は正数を指定してください。

## 実行時の動作

正数 N の場合、各 round で N 個の thread を開始し、それぞれが Strata の `/v1/chat/completions` へ streaming request を1件送信します。各要求は別 nonce を含む約400語の prompt と最大128生成 token を使います。round 数は `--runs` に従い、省略時3回です（`--runs` が1未満なら suite 内で1回に補正）。`--think` が有効なら request の thinking 設定も変わります。

測定結果には round ごとの生成 token 合計・wall time・合計 tok/s と、応答があった要求の first-token 時間および latency の p50/p95、エラー件数が記録されます。サーバーの `total_slots` を取得できなければ1 slot として扱い、N が slot 数を超えると順番待ちの注記を表示します。この option 自体はサーバーの並列設定を変更しません。

既存サーバーを利用する場合は、そのサーバーに追加負荷を与えます。既存サーバーを利用しない場合は、benchmark が設定を使って server を起動し、suite 終了時に起動したプロセスを停止します。通常の結果一式は出力先（既定 `bench/results`）に新しい結果 directory として書かれ、その `results.json` と README に client 測定値が含まれます。

## 適用条件と副作用

サーバーが応答し、認証が通る必要があります。server slot 数より多い同時要求は並行実行されず待機します。N にソース上の上限がないため、大きな値では thread と HTTP request が増え、サーバーと実行環境への負荷も増えます。GPU/server の設定変更は行わず、ベンチマーク要求を追加する動作です。

client request 内で発生した例外は `serve_load.one` が捕捉し、各要求の `err` として記録します。`--clients` 測定の失敗件数は client report に記録されますが、suite 共通の `failures` には追加されません。そのため client request のエラーだけでは最終終了コードは1にならず、終了コード1の判定は他の suite 項目の失敗状況によります。

## 出力とエラー

- 非整数値は argparse が拒否し、usage/error を表示して終了コード2になります（`type=int` の parser 定義）。
- モデル設定がない、指定 URL に Strata が応答しない、または指定ポートが別サービスで使われている場合は stderr に診断を出して終了コード2です。server 起動後に ready timeout となった場合はログ末尾を stderr に出して終了コード1です。いずれも client 測定に入る前の失敗経路です。
- client request の HTTP/通信等の例外は要求単位の error として報告結果に入り、他の suite が完了すれば処理は続きます。

## 根拠

- `tools/strata_bench.py:933-948` — parser 定義。`--clients` は `type=int`、既定値 `0`、`metavar="N"`。
- `tools/strata_bench.py:227-233,372-413` — 値の受け渡し、thread の生成、round 集計、0 の場合の skip。
- `tools/strata_bench.py:1001-1008` — `parallel_slots` による注意表示と suite 起動。
- `tools/strata_bench.py:645,861-866` — server slot 数の取得と README への concurrency 結果出力。
- `tools/strata_bench.py:969-999,1011-1037` — server 未準備等の終了経路、結果保存と終了コード判定。
- `tools/serve_load.py:34-72` — client が送る streaming request と要求単位の例外捕捉。
- `bench.sh:6-13`, `BENCH.bat:6-19` — wrapper が引数を Python CLI に委譲する処理。
- `docs/cli/README.md:1522-1544` — quick-benchmark の索引、コマンド階層、予定リンク。

調査は parser と関連ソースの読解に限定しました。CLI help の実行、build、GPU 実行、性能測定、テストは行っていません。
