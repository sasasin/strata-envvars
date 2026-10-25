# `strata runtime stop --if-instance-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--if-instance-id` |
| 別名 | なし |
| 値 | `INSTANCE_ID`。実行時に 32 桁の小文字16進数 ID として検証される |

## 役割

停止対象プロファイルの現在の runtime instance ID が指定値と一致する場合に限り、通常の owner host 経由の停止要求を実行します。`--plan` で停止対象を確認し、その計画に表示された instance ID を実行時の前提条件として渡す用途です。別の instance に入れ替わっていた場合は停止を拒否します。

## 使い方

```sh
strata runtime stop --profile work --plan
strata runtime stop --profile work --if-instance-id 0123456789abcdef0123456789abcdef
```

2 行目の ID は例示用です。実際には同じ profile の `--plan` 結果に表示された `instance_id` を指定します。`--plan` と `--if-instance-id` は同時に使えません。

## 値と既定値

- parser は値を取る引数として登録し、parser 層では書式を制約しません。省略時は `None` で、instance ID による一致確認は行われません（`strata_cli/cli.py:226-232`、`strata_cli/cli.py:1345-1356`）。
- 実処理では値がある場合、32 文字の小文字16進数でなければ拒否します。大文字、短い値、空文字、非16進文字を含む値は不正です（`strata_control/management.py:273-274`、`strata_control/runtime.py:620-625`）。
- `--if-owner-id` との同時指定は必須ではありません。stop 処理は instance ID 単独でも受け付け、owner ID が与えられた場合に限り先行する状態確認で owner と instance の両方を比較します（`strata_control/management.py:279-291`）。
- 停止の待機時間は別オプション `--wait` の既定値 330 秒で、1〜600 秒が有効です（`strata_cli/cli.py:226-232`、`strata_control/management.py:271-272`）。

## 実行時の動作

`strata runtime stop` は `--if-instance-id` を `management.runtime_action()` に渡します。計画モードでは instance ID などを含む `runtime.plan_stop()` の結果を表示しますが、計画に前提 ID を付けることはできません。停止実行では値を検証し、owner ID が併記されていれば現在状態の両 ID を比較した後、journal に `runtime.stop` 操作を記録し、期待 instance ID として runtime 側に渡します（`strata_cli/cli.py:1345-1358`、`strata_control/management.py:271-291`、`strata_control/runtime.py:602-611,614-632`）。

owner host が応答する通常経路では、host が受け取った ID の形式を再検証し、現在の instance ID と異なれば `instance_changed_after_stop_plan`（終了コード 6）を返します。一致すれば停止処理に進みます（`strata_control/runtime.py:1209-1224`）。オプションを省略した場合はこの instance 一致条件を渡さず、プロファイルの管理対象 instance に停止要求を出します。

## 適用条件と副作用

- `--plan` は停止を行いません。owner が確認できる `ready`、`starting`、`failed` 状態を対象とし、計画には owner ID、instance ID、profile revision と `would_drain: false`、`would_stop: false` が含まれます（`strata_control/runtime.py:602-611`）。
- ID が一致して停止に進むと、POSIX では server child に `SIGTERM`、Windows では owner pipe を閉じて EOF を送ります。終了待ちに失敗すると子プロセスツリーを強制終了し、ready file を削除します（`strata_control/runtime.py:990-1012`）。停止要求は `--wait` の範囲で待ち、通常の server 停止自体は host の shutdown timeout に加えて最大 8 秒を待ちます（`strata_control/runtime.py:614-632,990-1012`）。
- **owner host が失われている場合、この ID 条件は適用されません。** `runtime.stop()` は通常の RPC より先に `_stop_lost()` を呼び、owner host がないと判断した場合は記録済みプロセスを回収します。この経路には expected instance ID が渡されません。したがって、このオプションは owner host が稼働中の通常停止では instance の入れ替わりを防ぎますが、host 消失時の孤児プロセス回収を条件付きにするものではありません（`strata_control/runtime.py:614-632,643-667`）。

## 出力とエラー

- 通常の人間向け出力は `<profile>: <state>` と、結果に応じて instance ID、API URL、エラーを含みます。`--output json` または alias の `--json` では結果オブジェクトを JSON で出力します（`strata_cli/cli.py:1357-1373`）。
- 不正な ID 形式は入力エラー（終了コード 2）になります。実行中の instance と不一致の場合は `instance_changed_after_stop_plan` で停止せず、終了コード 6 になります。owner host が失われた場合の回収失敗は未終了・識別不能プロセスの情報を返し、停止失敗時は終了コード 6 です（`strata_control/runtime.py:620-625,643-667,1212-1224`）。
- `ProfileError` などの値エラーは、通常は `strata: <message>` を stderr に出して該当終了コードを返します。JSON 出力時は `ok: false` とエラー情報を出力します（`strata_cli/cli.py:527-532,2166-2173`）。

## 根拠

- `strata_cli/cli.py:226-232` — `runtime stop` parser と option、関連する `--wait`、`--plan`、`--if-owner-id` の定義。
- `strata_cli/cli.py:1331-1373` — option を管理関数へ渡す処理と結果表示。
- `strata_control/management.py:188-198,271-291` — stop の値検証、plan 時の制約、owner/instance 前提条件の確認、journal と runtime 呼び出し。
- `strata_control/runtime.py:602-640` — plan 内容、stop の timeout/ID 検証と RPC 呼び出し。
- `strata_control/runtime.py:643-667` — owner host 不在時に行う孤児プロセス回収経路。
- `strata_control/runtime.py:990-1012,1209-1224` — server の停止処理、instance ID 一致確認、停止失敗経路。
