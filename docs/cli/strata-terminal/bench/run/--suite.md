# `--suite`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--suite` |
| 別名 | なし |
| 値 | `standard-v1`、`serving-smoke`、`parallel-mixed-v1`、`parallel-overload-v1`、`parallel-cancel-v1`、`parallel-prefill-cancel-v1` |

## 役割

ベンチマークのプロトコル／ワークロードを選びます。省略時は `standard-v1` です。これは固定プロトコルに沿う標準ベンチマークで、残りの値は稼働中 Strata server に対するサービング比較スイートです（`strata_cli/cli.py:293-300`）。サービングスイートが実行する phase の並びは `strata_cli/bench.py:50-54` に定義されています。

## 使い方

標準スイート（省略時も同じ）:

```sh
strata bench run --profile my-profile --suite standard-v1
```

稼働中 server のサービング比較:

```sh
strata bench run --url http://127.0.0.1:8080 --suite serving-smoke --out ./bench-results/smoke-01
```

`--profile` と `--url` はどちらか一方が必須です（`strata_cli/cli.py:294-296`）。サービングスイートでは新規出力先の `--out` も必須です。

## 値と既定値

- `standard-v1`: 既定値。`strata_cli/bench_standard.py` の固定プロトコルを実行します。出力先 `--out` は省略でき、省略時は実行場所の `./bench/results`（存在すれば）または `./bench-results` 以下に新規フォルダーを作ります（`strata_cli/cli.py:309-311, 1279-1281`）。
- `serving-smoke`: `warmup`、`serial`、`mixed` を各スイート定義どおり実行します。
- `parallel-mixed-v1`: `warmup`、`serial`、`mixed`、`mixed`。
- `parallel-overload-v1`: `warmup`、`overload`、`recovery`。
- `parallel-cancel-v1`: `warmup`、`cancel_active`、`cancel_queued`、`recovery`。
- `parallel-prefill-cancel-v1`: `warmup`、`cancel_prefill`、`recovery`。

最後の5値では `--concurrency` は通常 `1..16`、`parallel-overload-v1` の場合 `1..64`（既定値 `4`）です。`--repeat` は `1..5`（既定値 `1`）、`--request-timeout` は `1..600` 秒（既定値 `120`）です。CLI は省略された値をこの既定値に置き換え、範囲外ならエラーにします（`strata_cli/cli.py:301-308, 1188-1196`）。warmup・recovery・cancel phase は repeat 回数にかかわらず各1回で、その他の phase を repeat 回実行します（`strata_cli/bench.py:117-120`）。

この parser は `choices` で6値に限定します。未知の値は argparse の usage error（終了コード `2`）になります（`strata_cli/cli.py:297-300`）。同じ `--suite` を複数回指定した場合は通常の `store` action で最後の値が使われます。短縮名はありません。

## 実行時の動作

`standard-v1` は `strata_cli/cli.py:1186-1187` で標準ランナーに分岐します。`--concurrency`、`--repeat`、`--request-timeout`、`--condition`、`--require-managed-match`、`--telemetry-credential-env` は標準スイートに適用できず、指定するとエラーになります。これらは workload 固定のための制約です。標準ランナーの request timeout は1800秒です（`strata_cli/cli.py:307-308`; `strata_cli/bench_standard.py:47, 768-770`）。標準スイート用の `--optional-concurrency` などは別途 parser に定義されています（`strata_cli/cli.py:315-334, 1241-1248`）。

`standard-v1` 以外は serving runner に渡されます。`--out` がない場合は開始前にエラーです。runner は server の telemetry を読み、モデルがロード済みで versioned telemetry があることを確認してから実行します。`parallel-overload-v1` は queue admission limit と正の queue timeout を必要とし、concurrency が admission limit を超えなければなりません。cancel 系は有効 slot 数が `1..16` で disconnect telemetry が必要です。`parallel-cancel-v1` はさらに queue と2秒以上の queue timeout、および concurrency が全 slot をカバーすることを要求します。`parallel-prefill-cancel-v1` は slot と concurrency がそれぞれ2以上必要です（`strata_cli/bench.py:757-791`）。

サービング実行の出力先は既存のパスや symlink であってはならず、存在確認後に新規ディレクトリを作ります。進捗を `progress.json` に記録し、完了時に `results.json` を書きます。profile を指定した場合は保存済み profile に benchmark lease を設定します（`strata_cli/bench.py:755-756, 792-802, 881-888`; `strata_cli/cli.py:1219-1225`）。サーバーへ実際のベンチマーク request を送り、キャンセル系では request の切断も行います。

標準スイートは `/health` などの endpoint を確認し、固定 corpus の request を server に送信します。`--profile` で指定した server が応答していない場合、`--no-start` がなければ profile の engine を起動してベンチマーク後に停止します。すでに稼働していれば停止しません（`strata_cli/bench_standard.py:781-789`; `strata_cli/cli.py:1292-1305`）。標準スイートは新規結果フォルダーに結果とレポートを保存します（`strata_cli/bench_standard.py:835-840, 899-960`）。

## 適用条件と副作用

- `--suite` の選択で、受理される関連 option、必要な出力先、実行ランナー、server 起動の可能性が変わります。
- serving suite は server を自動起動せず、ロード済み model と telemetry がある server を必要とします（`strata_cli/bench.py:757-760`）。標準スイートは profile を使うと未稼働 engine を起動し得ます（`strata_cli/cli.py:1292-1305`）。
- どちらの経路も server request や結果ファイルの生成を伴います。標準スイートの測定 request と結果ディレクトリ、serving suite の progress/result ファイルの内容は各ランナーに実装されています（`strata_cli/bench_standard.py:843-868, 899-960`; `strata_cli/bench.py:812-888`）。
- 既存の serving 出力ディレクトリ、必要な server 状態・telemetry の不足、各 suite 固有条件の不成立は失敗になります。標準スイートで無効な関連 option を指定した場合も実行前に拒否されます。

## 出力とエラー

`--out` 不足、数値範囲違反、標準スイートに非対応の option などの CLI 検証エラーは `_error` 経由で終了コード `2` になります（`strata_cli/cli.py:1188-1198, 1241-1248`）。serving suite が失敗報告を作成した場合は JSON／人間向け要約を出し、`successful` が false なら終了コード `6` です（`strata_cli/cli.py:1226-1234`）。実行前の server/telemetry 条件不足は `ProfileError` となり、CLI のエラー処理で終了します（`strata_cli/bench.py:757-791`; `strata_cli/cli.py:2166-2173`）。標準スイートは `results.json` と `README.md` を出力し、run status が complete 以外なら終了コード `6` です（`strata_cli/bench_standard.py:955-960`; `strata_cli/cli.py:1312-1328`）。

## 根拠

- parser の選択肢、既定値、相互作用する option: `strata_cli/cli.py:293-334`
- suite と phase の対応、repeat の扱い、serving runner の条件・結果出力: `strata_cli/bench.py:50-54, 117-120, 744-888`
- mode 分岐、必須引数、検証、出力と終了コード: `strata_cli/cli.py:1129-1234, 1237-1328`
- 標準 runner の server 条件、出力先、結果生成: `strata_cli/bench_standard.py:768-789, 835-840, 899-960`
- `--suite` 自体は上記 parser 定義と使用箇所から照合しました。CLI help、build、テスト、ベンチマーク実行は行っていません。
