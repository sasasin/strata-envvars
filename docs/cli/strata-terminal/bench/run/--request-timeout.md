# `strata bench run --request-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--request-timeout` |
| 別名 | なし |
| 値 | 秒数（`float`、1〜600、両端を含む） |

## 役割

serving suite の推論 API リクエストに渡す timeout 秒数です。`serving-smoke`、`parallel-mixed-v1`、`parallel-overload-v1`、`parallel-cancel-v1`、`parallel-prefill-cancel-v1` で使われます。suite を指定しない場合の標準 suite（`standard-v1`）では workload の条件を固定するため、この option は使用できません。

## 使い方

```sh
strata bench run --profile my-profile --suite serving-smoke \
  --request-timeout 180 --out ./bench-smoke-timeout
```

出力先は新規ディレクトリでなければなりません。`--profile` の代わりに `--url URL` で既に稼働中の server を指定することもできます。

## 値と既定値

- 値は必須です。`argparse` の `type=float` で読み込み、serving suite では 1〜600 秒の範囲を検証します。小数も指定できます。
- 省略時は serving suite で 120 秒です。parser 上の既定値は `None` で、実行時に 120 を補います。
- 範囲外、NaN、無限大は validation error となり、エラーコード 2 で終了します。範囲は inclusive です。
- `--suite standard-v1`（既定）で明示すると、範囲内の値であっても「標準 suite には適用されない」として拒否されます。省略した場合は拒否されません。

## 実行時の動作

serving suite の処理では `request_timeout` を通常 phase の `_phase` と cancellation phase の `_cancel_phase` に渡し、そこから各推論リクエストの `urllib` HTTP 呼び出しへ `timeout` として渡します。これにより warmup、serial、mixed、overload、recovery の各 request と、cancellation suite の対象 request・companion request の接続／stream 処理に適用されます。

ソースで確認できるのは `urllib` の `open(..., timeout=...)` への値の受け渡しです。benchmark 全体や各 request に対して別途、単調時計による総経過時間 deadline を判定する実装は確認できません。

この option は inference API の request timeout です。CLI は telemetry 用 endpoint を別に作り、その接続 timeout は3秒に固定しています。benchmark 開始時の endpoint は10秒ですが、ここでの `--request-timeout` では変わりません。

request が timeout 例外になると、その request の `error_code` は例外型名を含む `connection_...` となり、request は失敗として記録されます。通常 phase は全 request 成功を pass 条件とし、overload phase でも timeout は `admission_full` / `queue_wait_timeout` のような期待される拒否には含まれず、unexpected failure 扱いです。そのため該当 phase と全 run は失敗になります。run は残りの制御経路を通って `results.json` と最終 `progress.json` を保存し、失敗時の CLI 終了コードは6です。

## 適用条件と副作用

- serving suite では `--out` が必須です。未指定なら run 処理開始前にエラーコード2で拒否されます。
- 出力先が既に存在する場合も拒否されます。検査後に新しい出力ディレクトリを作成し、progress 記録と最終 report を保存します。timeout による request 失敗でも、通常は部分的な測定結果を含む report が残ります。
- `parallel-overload-v1` では `--request-timeout` の上限は他 suite と同じ600秒です。server の queue timeout を指定・変更する option ではなく、server の queue timeout や telemetry timeout と独立しています。
- `strata bench run` の `--request-timeout` は `strata tune run` にも同名の option がありますが、別 command scope です。この文書は `strata bench run` のものだけを扱います。

## 出力とエラー

- 値の範囲エラーは human 出力では stderr に `strata: ...` を出し、JSON 出力（`--output json`）では `ok: false` とエラーコード2を含む JSON を stdout に出します。
- standard suite での使用も同じくエラーコード2です。
- HTTP request timeout は parser error ではありません。通常は request の失敗として report に記録され、run の `successful` が false の場合は summary を出して終了コード6を返します。human 出力は stdout、JSON 出力は stdout です。

## 根拠

- `strata_cli/cli.py:293-308` — `bench run` parser、`--request-timeout` の型・初期値・help（serving suite 用、標準 suite 固定値の説明）。
- `strata_cli/cli.py:1186-1196` — standard suite への振り分け、120秒の既定値、1〜600秒 validation。
- `strata_cli/cli.py:1215-1234` — inference endpoint を10秒、telemetry endpoint を3秒で作成し、timeout を serving benchmark へ渡す経路と最終出力・終了コード。
- `strata_cli/cli.py:1237-1248` — standard suite で明示された `--request-timeout` を拒否する条件。
- `strata_cli/bench.py:223-248,273-300` — inference request の HTTP 呼び出しに timeout を渡す箇所と通信例外の記録。
- `strata_cli/bench.py:306-327,360-371` — cancellation suite の request に同じ timeout を渡し、完了待ちと通信例外を記録する箇所。
- `strata_cli/bench.py:744-756,792-802,812-840` — benchmark 側の範囲再検証、出力ディレクトリ・progress 作成、各 phase への値の伝播。
- `strata_cli/bench.py:843-888` — postflight、report 保存、および run 成功判定。
- `strata_cli/bench.py:618-636` — timeout 等の予期しない request failure を phase 失敗として扱う条件。
- `strata_cli/client.py:84-110` — telemetry endpoint の独立した timeout 設定。
- `strata_cli/cli.py:527-532,2166-2173` — validation error の stderr / JSON 表示と終了コード。
- `docs/TERMINAL.md:134-152` — serving suite と標準 suite の利用者向け説明。source の parser・実装を優先して記述。
