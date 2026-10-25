# `--if-owner-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--if-owner-id` |
| 別名 | なし |
| 値 | owner ID（32 文字の小文字 16 進文字列） |

## 役割

停止前に、現在のプロファイルの owner ID が確認済みの値と一致することを要求します。`runtime stop --plan` が返す `owner_id` を使い、確認後に別の実行個体へ入れ替わっていた場合の停止を防ぐための実行前条件です。stop の parser はこの値を省略可能としており、未指定なら owner ID による照合は要求されません（`strata_cli/cli.py:226-232`）。

## 使い方

まず `strata runtime stop --profile my-profile --plan` で表示される `owner_id` と `instance_id` を確認し、実行時には両方を指定します。

```sh
strata runtime stop --profile my-profile --if-owner-id 0123456789abcdef0123456789abcdef --if-instance-id fedcba9876543210fedcba9876543210
```

上記 ID は形式例です。実際には同じプロファイルの plan 結果に表示された値を使ってください。stop の plan は owner ID と instance ID を返し、`would_drain` と `would_stop` はともに `false` です（`strata_control/runtime.py:602-611`）。

## 値と既定値

値は引数文字列として受け取り、stop 処理で 32 文字の `[0-9a-f]` か検証されます。不正な形式は `ProfileError` となります。値に追加の正規化はありません。省略時は `None` で、owner ID の比較と stop RPC による owner 条件は行われません（`strata_control/management.py:142-147,271-291`; `strata_control/runtime.py:614-632`）。

## 実行時の動作

`strata_cli/cli.py` は `--if-owner-id` を `management.runtime_action()` の `if_owner_id` に渡します。stop 経路では、plan 指定時はこの条件値を使えず、指定すると `stop plan cannot include execution preconditions` で拒否されます。通常実行では現在の runtime status を読み、owner ID が一致しない場合は `owner_changed_after_stop_plan`（終了コード 6）を返します。一致すれば、期待 owner ID を operation journal に記録し、runtime stop 呼び出しへ渡します（`strata_cli/cli.py:1347-1353`; `strata_control/management.py:271-291`）。

stop では `--if-instance-id` との併用も重要です。management 層は owner ID を指定したとき、現在の instance ID と引数の instance ID も比較します。そのため `--if-owner-id` だけを指定すると、通常の instance ID が存在する実行個体では `None` との不一致になり `instance_changed_after_stop_plan`（終了コード 6）となります。plan に表示された2つの ID を組にして指定してください（`strata_control/management.py:279-284`）。

停止待ちの `--wait` は既定値 330 秒で、実行時に 1〜600 秒の有限値として検証されます。この値が `--if-owner-id` の照合規則を変えることはありません（`strata_cli/cli.py:226-232`; `strata_control/management.py:113-117,271-274`）。

host 側でも受け取った owner ID の形式と、実行中 host の `owner_id` を照合し、相違時は stop を行わず `owner_changed_after_stop_plan` を返します。任意で instance ID も照合されます（`strata_control/runtime.py:1209-1224`）。

## 適用条件と副作用

照合対象は指定したプロファイルの Strata が所有するローカル runtime です。条件が一致して停止が進むと、Windows では owner pipe を閉じ、POSIX では子プロセスへ `SIGTERM` を送ります。終了期限を超えた場合はその子プロセスツリーを強制終了し、ready file を削除します（`strata_control/runtime.py:990-1012,1025-1038`）。外部の任意プロセスを owner ID だけで停止する機能ではありません。

## 出力とエラー

owner/instance の不一致は stop を行わず終了コード 6 の失敗結果になります。不正な owner ID は管理層の入力検証で拒否されます。stop 本体では停止期限超過が `server_stop_deadline_expired`（終了コード 8）、正常終了以外が `server_stop_failed` として返ります。成功時の人間向け出力はプロファイル名と state を表示し、`--output json` の場合は JSON 結果を標準出力へ出します（`strata_cli/cli.py:1360-1373`; `strata_control/runtime.py:990-1012,1209-1224`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:226-232`
- CLI から管理層への引き渡し: `strata_cli/cli.py:1347-1353`
- stop の検証・plan 条件・owner/instance の事前照合・journal と runtime 呼び出し: `strata_control/management.py:142-147,271-291`
- runtime API の値検証と RPC: `strata_control/runtime.py:614-632`
- host 側の照合と停止実行: `strata_control/runtime.py:1209-1224`
- drain/終了・期限超過時の強制終了・ready file 削除: `strata_control/runtime.py:990-1012,1025-1038`

調査範囲は上記 checkout のソースです。同一 revision の CLI `--help` や Release 配布物との照合は行っていません。
