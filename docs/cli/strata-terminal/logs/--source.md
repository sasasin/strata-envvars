# `--source`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--source` |
| 別名 | なし |
| 値 | `runtime` または `harness` |

## 役割

`strata logs` で取得するリクエスト活動の出所を選びます。parser の既定値は `runtime` です。現行実装では `runtime` がサーバーの redacted request activity を表示しますが、`harness` は選択肢として受理された後、未対応として終了します。

## 使い方

```sh
strata logs --source runtime
```

`--source` を省略した場合も `runtime` として処理されます。`--follow` を組み合わせた場合は、同じ runtime activity をポーリングして新しい遷移を表示します。

## 値と既定値

- `runtime`: サーバーの telemetry snapshot に含まれるリクエスト活動を使います。省略時の値です。
- `harness`: parser の `choices` には含まれますが、実行処理で「shared local harness activity is unavailable」として拒否され、終了コード `5` になります。
- 上記以外の値は `argparse` が無効な choice として拒否し、コマンドの usage/error 経路になります。

## 実行時の動作

`strata_cli/monitor_commands.py` の `add_logs` が `--source` に `choices=("runtime", "harness")` と `default="runtime"` を設定します（`strata_cli/monitor_commands.py:63-67`）。コマンド実行時は、interval と `--json` / `--follow` / `--output` の組み合わせを先に検証した後、`harness` を選んだ場合には endpoint の解決・通信より前にエラーを返します。したがって現在 `harness` を使ってローカル harness のログを読む経路はありません（`strata_cli/monitor_commands.py:176-202`）。

`runtime` の場合、共通接続設定（`--url`、保存済み `--connection`、credential 環境変数、timeout）を解決し、`Endpoint` を作って `strata_cli.logs.run` に渡します（`strata_cli/monitor_commands.py:195-202`）。接続先は明示 URL / connection / 環境設定などで決まります。`Endpoint.snapshot()` はまず `/v1/telemetry` を読み、404 の場合に旧形式の `/metrics` と `/v1/status` へ fallback します（`strata_cli/client.py:134-152`）。read-only telemetry のみを許す `Endpoint.get` が HTTP GET を行い、認証 credential がある場合は Bearer header として渡します（`strata_cli/client.py:101-125`）。

one-shot では、利用可能な activity を JSON 出力するか、人間向けに表示します。snapshot の activity を最大 32 件に制限し、固定形式・許可された event/outcome・短い request ID のみを sanitizer が残します（`strata_cli/logs.py:101-124`、`strata_cli/client.py:239-268`）。`--follow` は serving instance ID が必要で、初回 snapshot の後、指定 interval ごとに snapshot を取得して増分遷移を表示します。保持上限を超えた欠落は gap として通知し、instance が変わった場合も通知します（`strata_cli/logs.py:25-57, 125-151`）。

`--source` 自体は出力形式や polling を変えません。それらは `--follow`、`--interval`、`--output`、`--json` が制御します。これらの制約を満たす例として、JSON 一回出力は `strata logs --source runtime --output json`、follow の JSONL は `strata logs --source runtime --follow --output jsonl` です（`strata_cli/monitor_commands.py:67-72, 176-188`）。

## 適用条件と副作用

`runtime` は telemetry endpoint と request activity を提供するサーバーが必要です。旧形式 endpoint への fallback で取得できる status-only telemetry には activity がなく、one-shot / follow とも「request activity is unavailable on this server」で失敗します（`strata_cli/client.py:134-152, 244-268`、`strata_cli/logs.py:105-108`）。`--follow` では serving instance ID がない場合も終了コード `5` です（`strata_cli/logs.py:125-126`）。

コマンドは読み取り専用で、`--source` によるファイル作成・変更やサーバー設定変更はありません。activity は bounded / redacted な遷移記録で、永続的なサーバーログ全体を選ぶオプションではありません（`strata_cli/monitor_commands.py:64-66`、`strata_cli/logs.py:1, 101-124`）。

## 出力とエラー

`--source harness` は `strata: shared local harness activity is unavailable; use --source runtime` を stderr に出し、終了コード `5` を返します。`--output json` / `jsonl` の machine mode では同じ失敗を `ok: false` と `error.code: 5` の JSON にします（`strata_cli/monitor_commands.py:124-129, 168-188`）。

`--source runtime` でも activity が利用不可なら終了コード `5` です。値が未許可、または他の logs 用 option の組み合わせ・interval が不正な場合は別の parser / validation error になります（`strata_cli/monitor_commands.py:66, 176-188`）。接続時の認証失敗・通信失敗などは共通 client の `ClientError` として報告され、その終了コードに従います（`strata_cli/client.py:117-125`、`strata_cli/monitor_commands.py:231-244`）。

## 根拠

- parser 定義と option scope: `strata_cli/monitor_commands.py:63-72`
- `harness` の受理後に失敗する分岐、`runtime` の接続処理と `logs.run` 呼び出し: `strata_cli/monitor_commands.py:176-202`
- redacted snapshot、one-shot / follow、instance ID 要件、通信 retry: `strata_cli/logs.py:101-151`
- read-only HTTP transport と snapshot fallback: `strata_cli/client.py:101-152`
- activity の sanitizer / 上限: `strata_cli/client.py:239-268`
- 共通エラー出力と終了コード処理: `strata_cli/monitor_commands.py:124-129, 231-244`

調査時点の Strata 作業ツリーは `main...origin/main` で未コミット変更なしでした。CLI help は実行せず、checkout 内の parser と実装を根拠にしました。
