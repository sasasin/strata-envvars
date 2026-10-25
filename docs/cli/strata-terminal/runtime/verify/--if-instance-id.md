# `--if-instance-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--if-instance-id INSTANCE_ID` |
| 別名 | なし |
| 値 | 実行中 instance の ID。小文字16進数32文字 |
| 既定値 | 未指定（`None`）。ただし `--if-owner-id` と一緒に指定する必要がある |

## 役割

`--plan` で確認した instance が変わっていないことを条件に、managed runtime の検証を実行するための前提条件です。`--if-owner-id` と対で使います。ID が現在の runtime と一致しなければ検証を開始せず、計画後に対象が入れ替わった場合の誤操作を防ぎます。

## 使い方

まず計画を表示し、JSON の `plan.owner_id` と `plan.instance_id` を次の実行へ渡します。

```sh
strata runtime verify --profile my-profile --plan --output json
strata runtime verify --profile my-profile \
  --if-owner-id OWNER_ID_FROM_PLAN \
  --if-instance-id INSTANCE_ID_FROM_PLAN
```

`OWNER_ID_FROM_PLAN` と `INSTANCE_ID_FROM_PLAN` は、最初のコマンドの出力からコピーする値です。`--plan` 自体は検証を実行せず、`--plan` といずれかの実行前提 ID を同時に渡すこともできません。

## 値と既定値

- parser は値を `INSTANCE_ID` として受け取り、既定値は未指定です。専用の argparse `type` 変換はありません。
- runtime 管理層で `[0-9a-f]{32}` に照合します。大文字、桁数違い、空文字は無効です。重複指定に独自処理はなく、通常の argparse `store` と同様に最後の値が使われます。
- `--if-owner-id` がない場合、または `--plan` と同時に指定した場合は拒否されます。`--if-owner-id` の値も同じ32文字形式でなければなりません。
- 関連する `--wait` は秒数の浮動小数値で、既定値は300、実行時の許容範囲は1〜600秒です。instance 条件が一致した後の probe に適用されます。

## 実行時の動作

CLI はこの値を `runtime_action()` に渡します。実行時はまず現在の状態を取得し、指定した owner ID と instance ID がそれぞれ一致するか比較します。不一致なら `owner_changed_after_verify_plan` または `instance_changed_after_verify_plan` で終了します。一致後も、runtime host が要求を処理するときに owner と現在の instance ID を再確認し、instance ID の変化を検出した場合は同じく失敗します。

ID が一致し、instance が ready なら、runtime host は ready file の子プロセス PID と instance ID を照合してから API を検証します。通常の runtime verify は `/v1/telemetry` で instance・launch attestation・model の対応を確かめ、ロード済みモデルには最大1 token の chat completion を送り、1 token 以上の生成を確認します。モデルが未ロードで `--load` がなければ API identity の確認で止まり、生成準備完了とは扱いません。これらは `--if-instance-id` 単体の副作用ではなく、前提条件を通過した `runtime verify` の動作です。

## 適用条件と副作用

- 前提 ID は `runtime verify --plan` の結果から取得します。plan は ready な owned instance を必要とし、owner ID と instance ID を返します。
- ID の比較に失敗した場合、検証 API 呼び出しには進みません。比較に成功した場合、verify はローカル runtime host への要求、telemetry の HTTP GET、およびロード済みモデルへの HTTP POST を伴います。`--load` を付ければ未ロードモデルを生成チェックのためにロードします。
- 成功・失敗した実行は operation journal 経由で処理されます。`--if-instance-id` は instance の指定・切替を行わず、対象を固定する比較条件です。

## 出力とエラー

- ID の形式違反、owner ID との片側指定、または `--plan` との併用は CLI のエラー経路に入り、通常出力では stderr、`--output json` では JSON エラーを出して終了コード2になります。
- plan 後に owner または instance が変わった場合は終了コード6です。human 出力では profile/state と error が表示され、JSON 出力では結果オブジェクトに error と `exit_code` が含まれます。
- instance が ready でない、ready file が現在の子プロセス/instance と一致しない、API・telemetry・生成チェックが失敗した場合も runtime verify は失敗します。具体的な probe error は readiness 検査が返す値によります。

## 根拠

- `strata_cli/cli.py:216-225` — `runtime verify` parser、`--if-instance-id` の値名、help、ほかの verify option。
- `strata_cli/cli.py:1331-1373` — parser 値を runtime action へ渡す経路、human/JSON 出力と終了コード。
- `strata_control/management.py:142-147` — instance/owner ID の32文字小文字16進 validation。
- `strata_control/management.py:235-270` — plan 時の前提 ID 禁止、ready instance の ID 取得、owner/instance のペア必須と実行前比較、journal 経由の verify。
- `strata_control/runtime.py:687-699` — verify の値検証と runtime host RPC への前提 ID の転送。
- `strata_control/runtime.py:1172-1208` — host 側の再検証、instance/ready file の照合、readiness verify の呼び出し。
- `strata_control/readiness.py:84-143` — telemetry と launch attestation の照合、未ロード時の分岐、1 token 生成と応答検査。
- `strata_cli/cli.py:527-533, 2166-2188` — human/JSON エラー出力と例外時の終了コード処理。

調査時に確認した Strata checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main` で未コミット変更なしでした。索引には本オプションのリンクがあり、指定 parser 定義と一致しています。
