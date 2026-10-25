# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 必須。保存済みプロファイル名（1〜64文字、小文字英字で始まり、小文字英字・数字・`_`・`-` を使用） |

## 役割

検証対象となる、Strata が管理するローカル runtime instance のプロファイルを選びます。`runtime verify` はその instance の API と起動情報を再確認し、モデルがロード済みなら1トークン生成も行います（`strata_cli/cli.py:197-201,216-225`、`strata_control/readiness.py:1-5,84-86`）。

## 使い方

```sh
strata runtime verify --profile my-model
```

計画表示では `--plan` を付けます。計画で表示された owner/instance を実行時にも要求する場合は、両方の ID を指定します。

```sh
strata runtime verify --profile my-model --plan
strata runtime verify --profile my-model --if-owner-id <OWNER_ID> --if-instance-id <INSTANCE_ID>
```

## 値と既定値

- `--profile` は `required=True` の文字列引数で、既定値はありません。alias や `choices` は定義されていません（`strata_cli/cli.py:216-225`）。
- runtime 側はプロファイル名を `[a-z][a-z0-9_-]{0,63}` で検証します。保存済みプロファイル名でなければならず、JSON 設定ファイルのパスは受け付けません（`strata_control/profiles.py:25`、`strata_control/runtime.py:95-98`）。名前が保存されていない場合、通常実行は「未保存」エラーになります（`strata_control/profiles.py:150-166`）。
- 同じ `--profile` を複数回指定した場合の専用検証はありません。特殊な action ではない通常の `argparse` 引数です（`strata_cli/cli.py:216-225`）。

## 実行時の動作

CLI は `--profile` の値と `--wait`（既定300秒）、`--load`、`--plan`、ID 前提条件を `management.runtime_action()` に渡します（`strata_cli/cli.py:216-225,1345-1356`）。このアクションはプロファイル名を検証し、通常実行では保存済みプロファイルの revision を読み、検証操作を journal に記録してから runtime owner へ要求します（`strata_control/management.py:235-270`、`strata_control/runtime.py:687-699`、`strata_control/journal.py:376-393`）。

通常実行では owner host が対象 instance の ready 状態、ready file の PID/instance 一致を確認してから、loopback 等の設定済み endpoint に `GET /v1/telemetry` を送り、応答の instance ID、launch attestation、model ID を照合します（`strata_control/runtime.py:1189-1199`、`strata_control/readiness.py:89-117`）。モデルがロード済みなら `POST /v1/chat/completions` に `max_tokens: 1` の probe を送り、生成応答と completion token 数を検査します。生成レスポンス本文は保存しない実装です（`strata_control/readiness.py:1-5,121-143`）。

- `--load` がない場合、model が未ロードなら API identity と launch attestation の確認まで行い、生成確認はせず `readiness_state: unloaded` を返します。`--load` を付けると未ロード時にも generation probe を進め、検証中にモデルロードを促します（`strata_cli/cli.py:218-220`、`strata_control/readiness.py:113-125`）。
- `--plan` は状態を照会し、`would_load` と `would_verify: false` を含む計画を返します。実際の API/generation probe は実行しません。計画と同時に `--if-owner-id` / `--if-instance-id` は指定できません（`strata_control/management.py:239-254`）。
- `--if-owner-id` と `--if-instance-id` は対で指定します。現在の owner と instance が一致しない場合、実行を拒否します（`strata_control/management.py:255-270`、`strata_control/runtime.py:1176-1188`）。

## 適用条件と副作用

- 対象は保存済みプロファイルに紐づく、managed runtime の owner が制御する ready instance です。未起動・停止中など ready でない場合は `runtime_not_ready` で検証できません（`strata_control/runtime.py:1189-1190`）。管理 transport は Windows または POSIX の Unix domain socket 対応環境を対象にし、それ以外では拒否されます（`strata_control/runtime.py:81-92`）。
- 操作結果は `runtime.verify` として操作 journal に記録されます。API への telemetry 要求とチャット completion 要求が発生し、`--load` の場合は未ロードモデルのロードも起こり得ます（`strata_control/management.py:264-270`、`strata_control/journal.py:376-405`、`strata_control/readiness.py:101-143`）。
- API key は run config または `STRATA_API_KEY` から取得され、HTTP Authorization header に使われます。これは `--profile` 固有の値ではありません（`strata_control/readiness.py:42-53,61-65`）。

## 出力とエラー

- 成功時は human 出力にプロファイル名、状態、instance ID、API URL、起動構成確認、generation/unloaded 状態を表示します。JSON 出力では runtime 結果を含む JSON を出力します。計画成功時は plan のみを出力し、成功は終了コード `0`、失敗は結果の `exit_code`（通常は `6`）を返します（`strata_cli/cli.py:1357-1373`）。
- endpoint・instance・attestation・model の不一致、HTTP/transport 異常、無効な probe 応答、生成 token 不在などは検証失敗になります。失敗コードを含む結果を出し、human 出力では runtime start/restart/verify の失敗時に取得可能な engine log のヒントを stderr に追記します（`strata_control/readiness.py:67-79,98-143`、`strata_control/runtime.py:1191-1208`、`strata_cli/cli.py:1369-1373,1376-1388`）。
- `--profile` の省略は parser が必須引数エラーとして拒否します。形式不正は `ProfileError`（既定終了コード2）、未保存プロファイルは終了コード5です（`strata_cli/cli.py:216-217`、`strata_control/profiles.py:30-35,150-166`）。

## 根拠

- parser 定義と runtime コマンドの説明: `strata_cli/cli.py:197-225`
- profile 名の形式・検証: `strata_control/profiles.py:25,150-166`、`strata_control/runtime.py:95-98`
- CLI から管理処理への引き渡しと出力・終了コード: `strata_cli/cli.py:1345-1373`
- plan と通常実行の分岐、ID 前提条件、journal 記録: `strata_control/management.py:235-270`、`strata_control/journal.py:376-405`
- owner 側の readiness 条件・照合: `strata_control/runtime.py:1172-1208`
- API probe、未ロード時の扱い、1-token generation: `strata_control/readiness.py:84-143`

調査は上記 checkout のソースに限定しました。CLI `--help` の実行や Release 配布物の照合は行っていません。
