# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `## main...origin/main` で、未コミット変更は表示されていません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--output` |
| 別名 | なし（`--json` は別の one-shot alias） |
| 値 | `human` または `json` |

## 役割

verify の結果を人向け表示にするか JSON にするかを選びます。出力形式の指定は検証内容や対象 runtime を変えません。`--plan` を付けた成功結果は例外的に、既定の `human` でも整形済み JSON として表示されます。

## 使い方

```sh
strata runtime verify --profile four-gpu --output json
```

`--profile` は必須です。出力形式は `--json` でも JSON にできます。未ロードのモデルをロードして一トークン検査する場合は `--load` を明示します。実行前提の owner/instance ID を指定する使い方や plan との相互作用は [`--plan`](--plan.md)、[`--if-owner-id`](--if-owner-id.md)、[`--if-instance-id`](--if-instance-id.md) を参照してください。

## 値と既定値

`strata_cli/cli.py:216-225` で `--output` は `choices=("human", "json")`、既定値 `human` と定義されています。値のないフラグではなく、必ず `human` または `json` を一つ指定します。その他の値や必須 `--profile` の欠落は parser が拒否し、usage/error を表示して終了コード 2 になります。

verify parser には one-shot 用の `--json` と `--quiet` も追加されます（`strata_cli/cli.py:508-515`）。`--json` を指定すると `main()` が `output` を `json` に設定します（同 `:2232-2235`）。従って、通常実行では `--json` と `--output json` が同じ機械出力経路を選び、両方を指定した場合も `--json` が `--output human` より優先します。`--quiet` は人向け出力に作用し、JSON 出力には影響しません。

## 実行時の動作

CLI は `--output json` なら runtime action の結果辞書を `schema_version: 1` を付けて一行 JSON にします。人向け通常実行では profile、state、instance、API URL、起動構成の attestation、readiness 状態や error を表示します（`strata_cli/cli.py:1331-1373`）。結果の `ok` に応じて終了コード 0 または結果の `exit_code`（未設定なら 6）を返します。

`--plan` 付きで plan が成功すると、出力形式別の通常描画ではなく `_success()` を通ります。`--output json` なら `schema_version` と `ok: true` を含む一行 JSON、既定の `human` なら plan オブジェクトを整形した JSON です（`strata_cli/cli.py:1357-1358, 535-542`）。plan は現在の状態を照会して、検証の効果を示しますが、`would_verify` は `false` です（`strata_control/management.py:239-254`）。

通常の verify は runtime management 経由で owner host に要求され、完了結果は operation journal に記録されます（`strata_cli/cli.py:1345-1356`、`strata_control/management.py:255-270`）。検証は readiness 機能を使って API identity と launch attestation を照合します。モデルが既にロード済みの場合は一トークン生成を要求し、未ロード時は既定では `unloaded` として返します。`--load` を指定した場合は未ロードモデルでも生成要求を行います（`strata_control/readiness.py:84-143`）。この処理は `--output` の値に左右されません。

## 適用条件と副作用

`--output` は表示形式だけを選び、単独ではファイルを作成・変更しません。通常の runtime verify 自体は read-only の status 表示ではなく、ready な管理対象 runtime にローカル API 要求を行う検査です。readiness probe は telemetry の GET と chat completions の POST を行います。生成要求は固定入力 `hi`、`max_tokens: 1`、`temperature: 0` です。未ロードで `--load` を指定すればモデルのロードを伴う場合があります（`strata_control/readiness.py:101-127`）。生成テキストや credential は operation journal に保存しない旨が Terminal 文書に記載されています（`docs/TERMINAL.md:94`）。

`--plan` では status 問い合わせだけを行い、generation probe は実行しません。runtime が ready でない場合は plan が失敗します。`--if-owner-id` と `--if-instance-id` は通常実行の前提条件で、plan には指定できず、通常実行でも片方だけは拒否されます（`strata_control/management.py:239-270`）。

## 出力とエラー

- 通常の成功/失敗結果は `--output json` なら結果オブジェクトの JSON、`human` なら状態を含む行で表示されます。失敗時の終了コードは runtime 結果の `exit_code` で、未設定時は 6 です（`strata_cli/cli.py:1359-1373`）。
- plan が成功した場合は前述の専用形式です。ready runtime がないと `runtime_not_ready`、終了コード 6 の失敗結果になります（`strata_control/management.py:242-245`）。
- `wait` は runtime 層で有限の1〜600秒に制限されます。runtime verify API の既定は300秒です（`strata_cli/cli.py:218`, `strata_control/runtime.py:687-699`）。値の型変換エラーは parser、範囲外の値や management 例外は `_run()` のエラー処理に進み、JSON 指定時は構造化 error を stdout、人向けでは `strata: ...` を stderr に出します（`strata_cli/cli.py:527-532, 2166-2188`）。
- 人向け出力で `--quiet` を併用すると成功時の stdout を抑え、失敗時に捕捉した出力があれば stderr に表示します。JSON 出力は quiet の対象になりません（`strata_cli/cli.py:2236-2248`）。

## 根拠

- 索引のコマンド階層と予定リンク: `docs/cli/README.md:412-425`
- parser、`--output` の choices/default、verify 固有 option: `strata_cli/cli.py:216-225`
- one-shot `--json` / `--quiet` の追加、alias 適用、quiet 出力処理: `strata_cli/cli.py:508-515, 2232-2248`
- CLI の runtime dispatch、plan/通常出力、終了コード: `strata_cli/cli.py:1331-1373`
- JSON 成功出力と例外出力: `strata_cli/cli.py:527-542, 2166-2188`
- plan と実行の分岐、ready 条件、journal 呼び出し: `strata_control/management.py:235-270`
- runtime 層の wait/ID validation と RPC: `strata_control/runtime.py:687-699, 1172-1208`
- telemetry 確認、一トークン生成、未ロード分岐: `strata_control/readiness.py:84-143`
- probe と credential/journal の記録に関する利用者向け説明: `docs/TERMINAL.md:94`

調査対象は上記 commit のソースです。別 OS 上の実動作や外部 runtime/API の具体的応答はこの調査では実行していません。Strata の build、GPU 実行、性能測定、テストは行っていません。
