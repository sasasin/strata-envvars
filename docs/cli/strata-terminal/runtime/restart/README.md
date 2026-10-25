# `strata runtime restart`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/management.py`、`strata_control/runtime.py` |
| 対象 | ローカル owner host が所有する saved profile の稼働 instance |

## 役割

保存済み profile とその run config から候補の起動内容を組み立て、現在の owned instance を停止して候補を起動し直します。profile の設定変更だけでは稼働中モデルは再起動されないため、変更を適用する場合は明示的にこのコマンドを実行します。所有者の異なる任意のプロセスを再起動するコマンドではありません（`strata_cli/cli.py:197-205,238-254`、`strata_control/runtime.py:1049-1059`）。

## 基本的な使い方

profile を編集した後、まず変更内容と稼働 instance を確認し、その後に実行します。

```sh
strata profile set four-gpu parallel=4 --plan
strata profile set four-gpu parallel=4
strata runtime restart --profile four-gpu --plan --output json
strata runtime restart --profile four-gpu
```

`--plan` は現在の instance と保存済み profile の候補を比較します。実行例では `--output json` を付けて、owner ID、instance ID、profile revision、source digest を含む確認結果を得られます。profile の編集と restart は別操作です（`docs/TERMINAL_QUICKSTART.md:53-62`）。

## 実行モードと主な動作

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 計画・確認 | `strata runtime restart --profile NAME --plan --output json` | 現在と候補の launch、差分、owner/instance ID、profile revision、source SHA-256 を返します。drain・停止・起動は行いません。 |
| 再起動 | `strata runtime restart --profile NAME` | ready 状態の owned instance を停止し、保存済み profile の候補で起動して readiness を待ちます。 |
| JSON 結果 | 上記に `--output json` を追加 | 結果を JSON で stdout に出力します。`--json` は同じ parser で登録される `--output json` alias です。 |

restart は既存 runtime が `ready` でない場合や候補の preflight が失敗した場合、drain 前に拒否します。停止は POSIX では子 server に SIGTERM、Windows では owner pipe の EOF を送り、停止 deadline を超えると Strata が起動した子プロセス群を終了させます。server は通常の停止要求を drain 経路に通し、設定された shutdown timeout 内に完了しない inference request をキャンセルします。停止後に候補 source の内容が preview 時から変わっていないかを再確認してから起動します（`strata_control/runtime.py:990-1012,1049-1093`、`serve/server.py:8219-8223,8673-8686`）。

新しい instance が ready になれば成功結果に `restarted: true` と前の instance ID が含まれます。候補の起動に失敗した場合、旧 source の内容が利用可能なら旧 launch を再起動して rollback を試みます。rollback の成否は `rolled_back` と state に反映され、rollback ができなければ `state: failed` になります（`strata_control/runtime.py:1093-1130`）。

## source の切替・移行

候補 run config が現在のものと異なる場合、通常の restart は安全側に拒否されます。source config の**パスを切り替える**場合は `--allow-source-switch`、同じ source file の**内容を変更して使う**場合は `--allow-source-migration` が明示的に必要です。switch 先が別の通常ファイルであること、旧 source が rollback に使えることなども確認されます。旧 launch の内容自体が変更されていて rollback 用の退避が必要な場合、owner-private snapshot を drain 前に保存します。元ファイルは上書きしません（`strata_control/runtime.py:793-821,1057-1084`）。

source switch/migration を許可する実行には `--if-source-sha256` で plan に表示された候補 digest を渡す必要があります。候補 digest、profile revision、owner ID、instance ID が plan 後に変わった場合は実行を拒否します。owner/instance の precondition を指定する場合は両方必要です（`strata_cli/cli.py:241-254`、`strata_control/management.py:292-333`、`strata_control/runtime.py:702-731,1064-1073`）。

## 注意点

- `--profile` は必須です。通常は保存済み profile 名を指定し、その profile が参照する run config から起動候補を作ります（`strata_cli/cli.py:238-254`、`strata_control/profiles.py:150-166,382-388`）。
- 主な時間指定は `--wait`（再起動全体、既定 1000 秒、受理範囲 1–1800 秒）と `--startup-wait`（新 instance の readiness 待ち、既定 300 秒、受理範囲 1–600 秒）です。数値以外や範囲外の値は validation error になります（`strata_cli/cli.py:245-246`、`strata_control/management.py:305-306`、`strata_control/runtime.py:709-711`）。
- plan は instance、profile、source を予約しません。実行までに状態が変わる可能性があるため、出力された revision/digest/ID を precondition として渡す運用ができます。source switch/migration 時は候補 digest が必須です（`strata_control/runtime.py:1132-1164`、`strata_control/management.py:299-316`）。
- `--quiet` は runtime restart parser に共通追加されますが、restart handler 自体はこの値を参照しません（`strata_cli/cli.py:508-515,1331-1373`）。
- リリース配布物、Windows 実機、実モデル/GPU の restart 時間や rollback の所要時間はこのソース調査では検証していません。

## 出力とエラー

Human 出力では profile 名、state、instance ID、API URL、launch verification の状態、およびエラー名を表示します。JSON 出力は `schema_version` と管理処理の結果を stdout に出します。restart 失敗時の human mode では CLI が追加で engine log の場所や末尾行を stderr に案内する経路があります（`strata_cli/cli.py:1331-1373,1376-1388`）。

CLI は処理結果の `ok` に応じて終了コード 0 または結果の `exit_code`（未指定時 6）を返します。parser/値検証エラーは usage/error 経路、restart 実行中の stale precondition や readiness/停止失敗は管理結果のエラーになります。Ctrl-C 時は「処理結果が不明の可能性がある」旨を返します（`strata_cli/cli.py:2166-2193`）。個々の失敗での端末出力文言は human/JSON mode により異なります。

## 関連文書

- [CLI 索引](../../../README.md) — `strata runtime restart` のオプション一覧と各文書へのリンク。
- [`strata runtime` の概要](../README.md)
- [`strata profile set` の概要](../../profile/set/README.md)
- Strata checkout の `docs/TERMINAL_QUICKSTART.md` — profile 変更と restart の利用例。

## 根拠

- `strata_cli/cli.py:197-254,508-515` — runtime/restart parser、時間の既定値、common `--json` / `--quiet` 登録。
- `strata_cli/cli.py:1331-1373,2166-2193` — runtime action 呼出し、出力・終了コード、CLI error 経路。
- `strata_control/management.py:292-336` — restart plan/execution の validation、precondition、journal 経由の呼出し。
- `strata_control/runtime.py:702-740,793-821,990-1012,1043-1164,1225-1263` — runtime API、source change 条件、stop/drain、起動・rollback、plan 結果。
- `serve/server.py:8219-8223,8673-8686` — 通常停止時の drain と deadline 後の request cancellation。
- `strata_control/profiles.py:62-64,135-166,382-388` — profile revision、run config 検証、profile/source の解決。
- `docs/TERMINAL_QUICKSTART.md:53-62` — 利用者向け profile 編集と restart の手順。
