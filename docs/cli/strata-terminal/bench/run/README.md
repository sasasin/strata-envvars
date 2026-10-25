# `strata bench run`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/bench_standard.py`、`strata_cli/bench.py` |

## 役割

稼働中の Strata server にリクエストを送り、推論応答と利用可能な server telemetry をベンチマーク証跡として保存します。既定の `standard-v1` は固定 workload の標準ベンチマークです。`serving-smoke` などの serving suite は、同時リクエスト、過負荷、キャンセル等を含む serving 動作を測ります（parser と suite 定義: `strata_cli/cli.py:291-334`、`strata_cli/bench.py:50-54`）。

このコマンドはチューニングや設定適用をしません。標準スイートの結果は `complete`、`partial`、`nonconforming` の状態を持つ報告書です。Serving suite は各 phase の成功、失敗、時間、telemetry を記録し、結果が不成功なら終了コード `6` を返します（`strata_cli/bench_standard.py:895-896,928-960`、`strata_cli/bench.py:857-888`、`strata_cli/cli.py:1226-1234`）。

## 代表的な使い方

```sh
# 保存済み profile を使い、標準 workload を実行
strata bench run --profile NAME --track default --track-notes "release と setup の設定"

# 既に動いている loopback server に標準 workload を送る
strata bench run --url http://127.0.0.1:8080

# serving smoke suite を新しい結果ディレクトリへ保存
strata bench run --profile NAME --suite serving-smoke --out ./bench-results/smoke-01

# 標準 workload に任意の同時実行 stage を追加
strata bench run --profile NAME --optional-concurrency
```

`--profile` と `--url` は相互排他で、どちらか一方が必要です。`--url` は server root を指定し、parser の説明では remote 接続に HTTPS が必要です。`--profile` は保存済み serving profile またはインストール済み run config を指します。認証 key は既定で `STRATA_API_KEY` 環境変数から読みます（`strata_cli/cli.py:294-314`）。

## 実行モード

| モード | 例 | 動作 |
| --- | --- | --- |
| 標準ベンチマーク（既定） | `strata bench run --profile NAME` | `standard-v1` の固定 fixture を順番に実行します。必要なら warm-up、performance、sanity を行い、`--optional-concurrency` 指定時は短い要求4件を同時に開始する3 roundを加えます。 |
| 標準ベンチマーク（稼働中 server） | `strata bench run --url https://host/` | 指定した稼働 server を使います。profile の起動・停止は行いません。 |
| Serving suite | `strata bench run --profile NAME --suite parallel-mixed-v1 --out DIR` | 選択した suite の workload を実行します。`--out` は新規ディレクトリが必須です。並列数、repeat、timeout などは suite 用 parser 値で指定します。 |

## 主な動作と副作用

- 標準 suite で `--profile` を使うと、その profile の server health を調べます。server が応答しなければ、`strata serve --profile ... --quiet` を子プロセスとして起動し、model load を待ってからベンチマークし、終了時にこの実行が起動した子プロセスだけを停止します。既に同 profile の server が応答していればその server を使い、停止しません。`--no-start` は標準 suite で profile server が停止中でも起動しない指定です（`strata_cli/cli.py:1253-1305,1306-1328`、`strata_cli/bench_standard.py:673-695,716-735`）。
- 標準 suite は `--out` を省略できます。作業ディレクトリに `bench/results` があればその下、なければ `bench-results` を使い、日付・GPU 名・run ID を含む新規フォルダを作ります。`results.json` と `README.md` に加え、設定、生成出力、必要に応じて engine log、provenance を保存します。モデルファイルの hash は既定で取り、`--skip-model-hash` では省略して run を nonconforming とします（`strata_cli/cli.py:1279-1281,1302-1305`、`strata_cli/bench_standard.py:766-780,807-809,899-960`）。
- `standard-v1` は固定 workload のため、`--concurrency`、`--repeat`、`--request-timeout`、`--condition`、`--require-managed-match`、`--telemetry-credential-env` は利用できません。workload 変更につながる標準 suite 用設定は parser の実行分岐で拒否され、これらの測定用設定は serving suite で使います（`strata_cli/cli.py:1241-1248`）。
- Serving suite は既に loaded 状態の Strata instance と versioned telemetry を要求し、事前・事後状態を記録します。過負荷 suite は server の `max_queue` と `queue_timeout` を、キャンセル suite は対応する slots/queue/disconnect telemetry を必要とします。出力先は既存パスや symlink であってはならず、新規の private directory として作られます。phase 進捗は `progress.json`、結果は `results.json` に記録されます（`strata_cli/bench.py:744-792,796-810,843-888`）。
- Serving suite の範囲は concurrency `1..16`（`parallel-overload-v1` は `1..64`）、repeat `1..5`、request timeout `1..600` 秒です。既定値はそれぞれ `4`、`1`、`120` 秒。標準 suite は protocol 固定の workload と1800秒 timeout を使います。`--require-managed-match` は保存 profile が必要です（`strata_cli/cli.py:301-308,1190-1203`）。

## 注意点と失敗

`docs/BENCHMARK_PROTOCOL.md` は本 revision 時点で status が draft で、pilot validation pending と記載されています。標準 suite を確定済みの公式性能値や hardware/model qualification とみなさず、報告書の状態・missing measurements・limitations を確認してください（Strata `docs/BENCHMARK_PROTOCOL.md:1-18`、`strata_cli/bench_standard.py:9-11`）。Serving suite も client-observed timing と server telemetry を記録するもので、engine batch-window 計測や hardware attestation ではありません（`strata_cli/bench.py:1-5,868-880`）。

標準 suite は server がいない、loaded model がない、`/props` に応答しない、または fixture が manifest と一致しない場合に失敗します。suite 中の要求失敗や中断は部分証跡に反映されます。profile から起動した engine を停止できない場合は run を失敗扱いにし、`ENGINE-NOT-STOPPED.txt` を試行作成して、process が port/GPU を保持している可能性を stderr に知らせます（`strata_cli/bench_standard.py:96-128,781-790,895-897`、`strata_cli/cli.py:1312-1328`）。一般的な CLI validation error は終了コード `2`、外部状態・接続等の失敗はコード `5`、benchmark 実行・証跡失敗はコード `6` となる経路があります。JSON 出力は `--output json` または `--json` で選べます（`strata_cli/cli.py:527-533,1131,1188-1198,1234,1247-1252,2166-2188`）。

標準 suite は `outputs.jsonl` に prompt/answer の証跡を含むため、共有・公開前に生成物を確認してください。runner は個人情報にあたる home path、host name、private address、key を redact しますが、利用者が private とみなす全情報を識別できるとは限りません（Strata `docs/BENCHMARK_PROTOCOL.md:42-47`、`strata_cli/bench_standard.py:9-11,907-923`）。

## 関連文書

- [CLI 索引](../../../README.md) — `strata bench run` の option 一覧と scope。
- [`--profile`](--profile.md)、[`--url`](--url.md)、[`--suite`](--suite.md)、[`--out`](--out.md)、[`--output`](--output.md) — 入力、suite、保存先、出力形式。
- [`--no-start`](--no-start.md)、[`--optional-concurrency`](--optional-concurrency.md)、[`--load-timeout`](--load-timeout.md)、[`--skip-model-hash`](--skip-model-hash.md) — 標準 suite の実行指定。
- Strata `docs/BENCHMARK_PROTOCOL.md` — `standard-v1` workload と結果形式（draft）。

## 根拠

- Strata `strata_cli/cli.py:291-334` — `bench run` parser、suite、引数。
- Strata `strata_cli/cli.py:1129-1234,1237-1328,2147-2148` — suite の振り分け、validation、起動、出力と exit status。
- Strata `strata_cli/bench_standard.py:673-735,766-809,895-960` — profile engine の起動・停止、standard report の生成。
- Strata `strata_cli/bench.py:1-5,50-54,744-888` — serving suite の workload、適用条件、証跡。
- Strata `docs/BENCHMARK_PROTOCOL.md:1-18,28-47` — standard protocol の状態、使い方、標準 suite と quick benchmark の区別。
