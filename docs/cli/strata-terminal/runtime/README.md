# `strata runtime`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime` とそのサブコマンド |
| 主な実装 | `strata_cli/cli.py`、`strata_control/management.py`、`strata_control/runtime.py` |

## 役割

保存済み profile に基づいて Strata のローカル推論サーバーを管理します。`runtime start` は現在のターミナルが閉じた後も動作するバックグラウンドサービスとして起動し、`runtime stop` まで稼働します。前景で動作し、ターミナル終了とともに停止する `strata serve` とは実行モードが異なります。`runtime` の直下ではサブコマンドが必須です。

起動、状態確認、API と生成の再検証、停止、残存プロセスの cleanup、保存済み設定による再起動を提供します。profile を作成・編集する機能はなく、`--profile` には既に保存済みの profile 名を指定します。

## 代表的な使い方

```sh
# 既存 profile の起動内容を表示する（起動しない）
strata runtime start --profile four-gpu --plan --output json

# profile をバックグラウンドで起動し、状態を確認する
strata runtime start --profile four-gpu
strata runtime status --profile four-gpu --output json

# API と1トークン生成を再検証する。未ロードのモデルは既定ではロードしない
strata runtime verify --profile four-gpu --wait 300

# 現行の起動設定を比較してから、profile を再起動する
strata runtime restart --profile four-gpu --plan --output json
strata runtime restart --profile four-gpu

# 所有中のインスタンスを停止する
strata runtime stop --profile four-gpu

# 所有者を失った後に残った Strata のサーバー／エンジンを整理する
strata runtime cleanup
```

実際の profile 名に置き換えてください。`start` と `restart` はサーバー起動とエンジン実行を伴います。`--plan` は起動・停止・検証・再起動の各操作で確認に使えますが、`status` と `cleanup` には plan モードがありません。cleanup は孤立した Strata プロセスを終了し得るため、対象範囲を絞る場合は `--profile NAME` を指定します。

## 実行モードとサブコマンド

| サブコマンド | 主な動作 |
| --- | --- |
| `start` | 保存済み profile の起動計画を組み立て、ローカル owner host を介してサーバーを起動します。起動待ちの既定値は300秒です。 |
| `status` | 指定 profile の所有状態を表示します。CLI の status は直近の起動または明示的な verify の結果を示し、継続的な engine liveness 検査ではありません。 |
| `verify` | 所有中の API を確認し、1トークン生成を行います。既定では未ロードモデルをロードせず、`--load` を指定した場合はロードして検証します。 |
| `stop` | 所有中サーバーを drain して停止します。`--plan` では現行 owner と instance を表示します。 |
| `cleanup` | owner が失われた状態で残る、Strata が起動したサーバーと engine を確認して終了します。稼働中の所有インスタンスや、記録と照合できないプロセスには触れません。 |
| `restart` | 現在の instance を drain し、保存済み profile の設定で起動し直します。`--plan` は現在と保存済みの launch 内容を比較します。失敗時は以前の起動を戻す処理を試みます。 |

全サブコマンドの引数と値の詳細は [CLI オプション索引](../../README.md) の `strata-terminal` → `strata runtime` を参照してください。特に source config の変更を伴う restart は、plan と候補 SHA-256 を使う明示的な手順が必要です。

## 主な動作と副作用

- `start` は profile と run config から起動計画を作り、必要な engine component の事前確認を行います。起動 host とサーバーのログ、owner state を runtime ディレクトリに作成し、engine を起動します。managed 起動ではサーバーへ `STRATA_NO_ACQUIRE=1` を渡すため、この経路は不足ファイル取得・インストールを行いません。
- `start` は ready-file の instance ID を確認し、API 到達性・起動設定との一致を検査した後、モデルがロード済みなら1トークン生成で readiness を確認します。遅延ロード設定のモデルは、`verify --load` を使わない限り未ロードのままになり得ます。
- `restart` は通常、異なる source config への切替や同じ config の編集を拒みます。切替・移行を許可する場合は、plan で確認した revision や SHA-256 を使う明示的な指定が必要です。失敗時の復旧用に、移行では private runtime directory に設定ファイルの snapshot を作る場合があります。
- `stop` と `cleanup` は管理対象のサーバー／engine に停止処理を行います。owner を失った残存プロセスは、保存記録の PID、起動時刻、コマンドラインなどを照合できたものだけが対象です。確認できないものは終了せず、失敗結果に含めます。
- POSIX では private Unix socket と process group、Windows では token 保護された loopback TCP と job object 等を使う実装です。runtime state は既定でユーザー state directory の `strata/runtime`、または `STRATA_RUNTIME_DIR` に保存されます。環境変数の詳細は [Terminal CLI の説明](../../../TERMINAL.md) を参照してください。

## 出力と注意点

`--output human` が既定です。`--output json` では `schema_version` を含む JSON を stdout に出します。操作結果の `ok` に応じた終了コードを返し、runtime 操作の失敗は通常その結果に含まれる `exit_code`（未指定時は6）を使います。`start`、`restart`、`verify` の失敗時には、CLI が取得できる場合に engine log の手掛かりを stderr に追加します。

`start --plan`、`verify --plan`、`stop --plan` は読み取り専用の確認経路です。成功時は plan を出力し、実行しません。`restart --plan` も現在と候補の状態を比較します。plan は状態を予約しないため、実行時点で profile、source、owner または instance が変わっていれば拒否されることがあります。

`status` の `ready` は直近の成功した起動・verify 状態であり、その後の稼働を継続監視した結果ではありません。現在の API と生成経路を再確認する場合は `verify` を実行してください。1トークン確認はスモークチェックであり、継続性能や回答品質を保証しません。multi-GPU workload はこの runtime 経路で qualification されていません。

CLI parser の値検査に失敗した場合は usage/error 経路になります。runtime 操作内の検証失敗、待ち時間超過、owner/instance の不一致などはエラー結果と非ゼロ終了コードになります。具体的な範囲・条件は各オプション文書を参照してください。

## 根拠

- `strata_cli/cli.py:40-45,197-254` — トップレベル parser、runtime の説明、サブコマンドと option scope。
- `strata_cli/cli.py:1331-1373,2119-2193` — runtime の dispatch、human/JSON 出力、戻り値、エラー処理。
- `strata_control/management.py:188-336` — start/status/verify/stop/restart の plan、validation、journal および runtime への委譲。
- `strata_control/runtime.py:81-129,444-455` — 対応 transport、state directory、状態報告と stale 判定。
- `strata_control/runtime.py:518-599,614-699,702-740` — 起動、停止、cleanup、verify、restart の制御と待ち時間・失敗条件。
- `strata_control/runtime.py:840-900,904-917,1043-1110` — server 起動、ログ・owner 記録、readiness 検証、restart rollback。
- `strata_cli/cli.py:233-237`、`strata_control/runtime.py:670-684` — cleanup の parser、対象範囲、失敗時の返却。
- `docs/TERMINAL.md:61-94` — foreground/managed runtime の使い分け、代表例、実装上の注意点。
- `docs/CLOSING.md:13-55` — background runtime の終了・残存プロセス整理。

この文書は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5` の checkout と同 commit 内の利用者向け資料を根拠にしています。Release 配布物や各 OS の実機 qualification は確認していません。
