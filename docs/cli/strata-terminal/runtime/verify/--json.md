# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--json` |
| 別名 | なし（`--output json` が同じ出力を選ぶ） |
| 値 | 値を取らないフラグ。省略時は `human` 出力 |

## 役割

検証結果を JSON で標準出力へ出します。`--json` は `--output json` の alias です。検証の内容や成功条件は変えず、`--plan` を併用した場合も JSON で計画を返します。

## 使い方

```sh
strata runtime verify --profile my-profile --json
strata runtime verify --profile my-profile --plan --json
```

## 値と既定値

値は不要です。parser は `store_true` で登録し、one-shot コマンド群の `--output`（`human` / `json`、既定値 `human`）を JSON に切り替えます。したがって `--json` と `--output json` は同じ JSON 出力を選び、`--json` を省略すると人間向け出力です。重複指定時の特別な処理はありません。

## 実行時の動作

- 通常の `runtime verify` は、検証操作の結果を `{"schema_version":1,...}` の JSON オブジェクトとして標準出力へ出し、結果が `ok` でない場合は結果の `exit_code`（なければ `6`）を終了コードにします。
- `--plan` と併用すると、現在の runtime 状態を調べ、ready な owned instance と owner / instance ID を含む `plan` を `{"schema_version":1,"ok":true,"plan":...}` 形式で返します。この経路は実検証を行わず、`wait` の値も検証処理には使いません。
- 実検証では `--wait`（既定 300 秒、有限値 1〜600 秒）と `--load`、任意の `--if-owner-id` / `--if-instance-id` を runtime 管理処理に渡します。ID の片方だけを指定すると拒否されます。`--plan` に ID 条件を付けた場合も拒否され、計画の確認後に実行する場合は両方の ID を指定して状態変化を照合できます。
- 検証は owner に RPC し、operation journal に `runtime.verify` の操作を記録します。ready ファイルと子プロセスを照合し、API の telemetry で instance / model / launch attestation を確認します。モデルがロード済みなら一 token の chat completion probe も行います。
- `--load` は未ロードモデルを probe のためにロードするよう要求します。指定しない場合、API が未ロードを報告すると generation probe を送らず、`generation_ready: false`、`readiness_state: "unloaded"` の結果を返すことがあります。この場合でも API identity と launch attestation の確認結果は返されます。

## 適用条件と副作用

`--json` は出力形式だけを切り替え、検証を開始するかどうかは変えません。副作用は `--json` 自体ではなく、通常の verify 経路にあります。通常経路は owner とのローカル RPC と operation journal への記録を行います。また readiness probe は profile の API endpoint に接続し、モデルがロード済みの場合は一 token の生成要求を送ります。`--load` を付けると未ロードモデルをロードする場合があります。`--plan` は現在の状態を読むだけで、verify 操作や generation probe は実行しません。

## 出力とエラー

通常経路の成功・失敗は JSON の `ok` を含む結果オブジェクトで出力されます。検証失敗時は runtime の状態、エラー識別子、終了コードなどが結果に含まれ得ます。`runtime_not_ready`、計画後に owner / instance が変わった場合、ready ファイル不正、instance / model / attestation の不一致、API probe の失敗などは検証失敗経路です。CLI で捕捉する入力・実行エラーも JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` 形式で出力されます。通常の verify 結果が失敗した場合、CLI はその結果の終了コードを返します。

## 根拠

- `strata_cli/cli.py:216-225` は `runtime verify` parser、`--output` の値と既定値を定義します。`strata_cli/cli.py:508-515` は `runtime_verify` を含む one-shot parser 群に `--json` を `store_true` alias として追加します。
- `strata_cli/cli.py:1331-1373` は JSON 出力、plan 結果、終了コード、verify 失敗時の分岐を実装します。`strata_cli/cli.py:2223-2237` は `--json` を `output="json"` に変換します。`strata_cli/cli.py:527-542` は JSON エラー / 成功 envelope を定義します。
- `strata_control/management.py:188-270` は plan と実行の分岐、wait の範囲、ID 条件、journal 付き実行を定義します。`strata_control/journal.py:376-405` は直接操作の記録と verify 結果の記録項目を示します。
- `strata_control/runtime.py:687-699` は verify の入力検証と owner RPC を行います。`strata_control/runtime.py:1166-1208` は実行可能な owner / instance の確認、ready 状態、probe の呼び出しと失敗応答を処理します。
- `strata_control/readiness.py:84-143` は API identity / attestation の確認、未ロード時の結果、one-token generation probe と応答検証を実装します。
- 補助資料として同一 checkout の `python strata.py runtime verify --help` を確認し、`--json` が `--output json` の alias であることを parser 定義と照合しました。別 OS / 実稼働 instance での API 経路はこの調査では実行していません。
