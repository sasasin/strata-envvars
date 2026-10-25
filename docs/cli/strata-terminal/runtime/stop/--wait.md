# `strata runtime stop --wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒単位の浮動小数点数。有限値で 1〜600 秒 |

## 役割

owner host に停止要求を送る際の待ち時間を指定します。`strata runtime stop` は保存済み profile が管理するローカル instance を drain して停止します。この `--wait` は推論要求の drain 時間そのものではなく、CLI が owner host から停止処理の応答を待つ時間です。

## 使い方

```sh
strata runtime stop --profile my-profile --wait 120
```

`--profile` は必須です。停止を実行せず owner と instance を確認する `--plan` も指定できます。

## 値と既定値

- 省略時は `330` 秒です。
- 明示値は `float` に変換され、management 層で有限値かつ 1〜600 秒であることを検証します。`0`、範囲外、`nan`、`inf` は受け付けません。
- 同じ引数を複数回指定した場合の argparse の通常規則では最後の値が使われます。
- `--plan` を併用した場合も値の範囲検証は行われますが、plan の取得は停止要求を実行しません。

## 実行時の動作

parser は `--wait` を `float` として受け取り、既定値 330 を設定します。`_runtime` は `wait` を `management.runtime_action` に渡し、同関数は `--wait` を RPC timeout と runtime 停止関数の timeout の両方に渡します。通常経路では `strata_control.runtime.stop` が owner host へ `stop` RPC を送り、応答待ちにこの秒数を使います。

停止要求を受けた owner host は子 server を停止します。POSIX では `SIGTERM` を送り、Windows では owner pipe を閉じます。server は新規推論受付を止めて、実行中の要求を drain します。drain の猶予は server 起動時に設定された `--shutdown-timeout` に従い、期限後は owner host が子プロセスを強制終了する場合があります。そのため `--wait` を延ばしても drain 上限自体は延びません。停止処理後、CLI は人向け出力または `--output json`（別名 `--json`）で結果を表示します。

`--plan` を付けると現在の owner ID・instance ID を含む plan を返し、`would_drain` と `would_stop` はどちらも `false` です。`--if-owner-id` / `--if-instance-id` は plan 後の identity 変化を検出する実行前提条件であり、値が現在の状態と異なれば停止しません。

## 適用条件と副作用

- 対象は Strata が管理するローカル runtime instance です。停止時には server が新規推論を受け付けなくなり、処理中要求は drain されます。drain が起動時の shutdown timeout 内に終わらない場合、server は残った Strata 所有要求をキャンセルして終了処理を続けます。
- owner host が失われている場合、通常 RPC の前に記録済みの残存 server/engine process を識別して終了する回復経路があります。識別できない残存 process は終了対象にせず、失敗として返されます。
- stop plan は実行前提条件 ID を受け付けません。`--if-instance-id` だけを指定した場合は現在状態の照合を行わず RPC に渡し、owner host 側で instance ID を検査します。

## 出力とエラー

- 値が範囲外または有限数でない場合は `ProfileError` となり、通常出力ではエラー文、JSON 出力では `ok: false` を含む JSON が返り、終了コードは 2 です。
- owner host への応答待ちが切れると `runtime operation wait expired; inspect runtime status`（終了コード 8）になります。停止処理の完了状態は不明なため、runtime status で確認します。
- control が利用できない場合は終了コード 3、plan 後に owner または instance が変わった場合や停止に失敗した場合はソースが返すエラーと終了コード（通常 6 または 8）が結果に反映されます。
- server の drain deadline が切れた場合は残存する Strata 所有要求をキャンセルして終了処理に進みます。runtime host の停止 deadline も切れた場合は子 process tree を kill し、`server_stop_deadline_expired` と終了コード 8 を返します。

## 根拠

- parser、既定値、`--plan`・ID 前提条件: `strata_cli/cli.py:226-232`
- one-shot parser への `--json` / `--quiet` 追加: `strata_cli/cli.py:508-515`
- CLI から管理層への引数転送と plan 結果の出力: `strata_cli/cli.py:1331-1373`
- 管理層の有限値・範囲検証、plan 分岐、停止 RPC への転送: `strata_control/management.py:113-117`, `strata_control/management.py:271-291`
- owner / instance の plan 内容と停止処理: `strata_control/runtime.py:602-640`
- RPC timeout、timeout 時のエラー: `strata_control/runtime.py:402-430`
- owner host の ID 検査と stop 処理: `strata_control/runtime.py:1209-1224`
- child server の停止、timeout 時の kill: `strata_control/runtime.py:990-1012`
- server の drain 開始・待機・要求キャンセル: `serve/server.py:4031-4055`, `serve/server.py:8673-8687`
- 現行 CLI のエラー変換と終了コード: `strata_cli/cli.py:2119-2193`

調査は上記 revision の checkout に含まれるソースに基づきます。OS ごとの停止シグナルの違いはコードで確認しましたが、実機での停止動作、release 配布物、個別環境における owner host の応答時間は検証していません。
