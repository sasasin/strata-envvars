# `strata runtime verify --plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True` |

## 役割

対象 profile の管理下にあるローカル runtime が現在 `ready` かを確認し、verify を実行した場合の対象 instance と検証内容を表示します。`--plan` 自体は検証処理を実行しません。

## 使い方

```sh
strata runtime verify --profile local --plan
```

`--profile` は必須です。モデルが未ロードの場合の計画を確認する例:

```sh
strata runtime verify --profile local --plan --load
```

## 値と既定値

- `argparse` の `store_true` で定義され、値は不要です。省略時は計画表示を行わず、通常の verify 実行に進みます。
- `--plan` の既定値は `False` です。`--load` は別フラグで既定値 `False`、`--wait` は `300` 秒が既定です。通常実行時の `--wait` は `1..600` 秒に制限されます。
- `--if-owner-id` / `--if-instance-id` は実行前提条件であり、いずれかを `--plan` と同時に指定すると拒否されます。確認後に実行を固定する場合は、両 ID を通常実行時に渡します。

## 実行時の動作

- `--plan` 分岐は `runtime.status(profile)` を呼び出します。状態が成功 (`ok`) で `ready` であり、owner ID と instance ID が有効な 32 桁小文字 hex のとき、profile、状態、ID、モデル状態、`load` 値、`would_load`、`would_verify: false`、`probe: one_token_generation` を含む計画を返します。
- `would_load` は `--load` が指定され、現在の `model_state` が `unloaded` のときだけ `true` です。ここではロードしません。また、`would_verify: false` のとおり、API 検証や一トークン生成を行いません。
- 成功した plan は CLI の `_success` 経路で出力します。`--output human` が既定で、`_success` に専用の human 文面が渡されないため、plan オブジェクトを整形した JSON として表示します。`--output json` では `schema_version` と `ok: true` を含む一行 JSON です。
- このフラグはサーバー起動・停止・profile 保存を行いません。ただし plan を作るために status を読むので、管理下 runtime が稼働中なら owner host へローカル制御要求を送り、status を問い合わせます。

## 適用条件と副作用

- 管理下 instance が `ready` である必要があります。未管理・停止中なら `runtime.status` は `stopped` を返し、古い owner host なら `stale` を返すため、計画は成功しません。
- 状態が ready でないと `runtime_not_ready`、終了コード `6` の失敗結果になります。ready でも owner ID または instance ID が欠落・不正な場合は、`runtime verification needs an owned ready instance` のエラーになります。
- `--plan` と `--if-owner-id` / `--if-instance-id` は併用できません。これらの前提条件を片方だけ通常実行に渡すこともできず、両方が必要です。実行時には plan 時の owner / instance と一致しない場合、状態変更後の実行として終了コード `6` で拒否します。
- verify を実際に実行すると、稼働中の API へ telemetry GET を送り、モデルがロード済みなら chat completions POST で `max_tokens: 1` の生成を試します。`--load` を指定し未ロードならロードを伴う可能性があります。これらは `--plan` では行いません。

## 出力とエラー

- 成功時は `--output human` なら整形済みの plan JSON、`--output json` なら `schema_version` と `ok`、`plan` を含む一行 JSON を stdout に出力し、終了コード `0` です。
- 対象 runtime が ready でない場合、human 出力では状態と `runtime_not_ready` を表示し、JSON では `ok: false` 等を出力します。コマンドは結果の `exit_code`（`6`）を返します。
- `--plan` と ID 前提条件の併用、profile 名の不正、ローカル制御要求の失敗などは `ProfileError` として処理されます。未管理・停止中では「runtime is not managed or is stopped」（終了コード `3`）、制御待ち timeout は終了コード `8` など、失敗段階に応じたエラーになります。

## 根拠

- `strata_cli/cli.py:216-225` — verify parser、必須 profile、`--plan` の `store_true`、他オプションと既定値。
- `strata_cli/cli.py:527-542` — error の stdout / stderr 形式と `_success` の human / machine 出力形式。
- `strata_cli/cli.py:1331-1373` — runtime action 呼び出し、成功 plan の出力、human / JSON 出力と終了コード。
- `strata_control/management.py:235-270` — plan と通常実行の分岐、状態・ID 条件、ID 前提条件の検査。
- `strata_control/runtime.py:444-455` — status が stopped / stale / owner host 経由の状態を返す処理。
- `strata_control/runtime.py:687-699,1172-1208` — 通常 verify の値検証、制御要求、instance の ready 検査と検証結果。
- `strata_control/readiness.py:84-143` — 実行時の telemetry 確認、未ロード時の挙動、一トークン生成 probe。plan ではこの関数に到達しない。
