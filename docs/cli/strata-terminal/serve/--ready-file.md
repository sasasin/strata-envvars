# `strata serve --ready-file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--ready-file` |
| 別名 | なし |
| 値 | 作成する JSON ファイルのパス。絶対パスが必要 |

## 役割

API サーバーが bind され、モデル状態が決まった時点で、その instance を識別する JSON ファイルを作成します。起動スクリプトやローカルの管理プロセスが起動結果を知るための補助情報です。ファイルだけでは現在もサーバーが稼働中である証明にならず、利用側は instance ID を稼働中サーバーの telemetry と照合する必要があります。

## 使い方

```sh
strata serve --profile ./run-config.json --ready-file /home/alice/.local/state/strata/ready.json
```

`--profile`（alias `--config`）には既存の run config を指定します。指定したファイルがなければ起動後に作られるのではなく、起動前に親ディレクトリと出力先を検証し、API 起動後に ready record を書きます。例の出力先は、事前に作成した他ユーザーが読めない専用ディレクトリ内に置いてください。

## 値と既定値

- 値は必須で、省略時は ready file を作りません。オプションに短縮 alias はありません。
- パスは絶対パスでなければなりません。親ディレクトリは事前に存在するディレクトリである必要があります。相対パス、存在しない親ディレクトリは拒否されます。
- 出力先が既に存在する場合や dangling symlink の場合も拒否され、上書きしません。再利用する場合、残存ファイルが stale でないか確認し、確認後に利用者側で削除してください。
- 指定パスは `pathlib.Path` として扱われますが、`resolve()` による正規化は行われません。親ディレクトリへの書き込み可否などは実際の作成時に判明します。

## 実行時の動作

CLI はサーバー引数を組み立てる際に `serve.ready.preflight()` を呼び、検証済みパスを `serve.server` の `--ready-file` に渡します。`--plan` を指定した場合もこの事前検証は行いますが、計画を表示して終了するため ready file は作成されません。`--ready-file` の値は設定ファイルや環境変数からは補われません。

API の bind 後、実際に割り当てられた port、instance ID、サーバー PID、API URL、bind host/port、model ID、model state、API state、作成時刻、schema version を含む JSON を作成します。model state は通常 `ready`、遅延ロード構成では `unloaded` です。ready file 自体に API key や認証情報は含まれません。

作成は排他的な新規作成で行い、POSIX では mode `0600` を指定します。Windows ではアクセス制御が親ディレクトリの ACL を継承するため、private な親ディレクトリを使ってください。書き込みが例外で中断したときは作成途中のファイルを削除します。通常の停止処理では、ファイル内の instance ID と PID が現在のサーバー自身に一致する場合に限り削除します。強制終了など停止処理を通らない終了ではファイルが残ることがあります。

## 適用条件と副作用

このオプションは `strata serve` の foreground 起動に対して任意で使います。未指定ならこの記録の作成・削除処理はありません。ready file は起動後の API bind に続いて書かれるため、プロセスがファイルを書けないと起動は失敗します。

ready file は起動 instance の手掛かりです。ファイル内の PID を使ってプロセスを操作してはいけません。古いファイルが残った場合は、記録された instance ID を live `/v1/telemetry` と照合して stale であることを確認してから、再利用前に削除してください。

## 出力とエラー

- 相対パス、親ディレクトリ不在、既存パスなどの事前検証エラーは `ValueError` になります。通常の human/json 出力では CLI の共通エラー処理で報告され、終了コードは既定で `2` です。`--output jsonl` では `failed` イベントで報告します。
- 実際のファイル作成で `OSError` が発生すると stderr に `[strata] could not write ready file (<例外型>)` を出し、server は終了コード `6` を返します。作成に失敗した場合はサーバーの HTTP server、engine、関連リソースを閉じます。
- `--plan` はパス検証エラーを報告し得ますが、ready record は書きません。

## 根拠

- `strata_cli/cli.py:46-67` — `strata serve` parser。`--ready-file` は値を取るオプションで、default・alias は宣言されていません。
- `strata_cli/cli.py:782-826` — launch plan の組み立て、パス事前検証、server への引き渡し、plan 内の表示値。
- `strata_cli/cli.py:915-955, 2166-2183` — plan 時の終了、foreground 起動、および値・OS エラーの CLI 報告。
- `serve/ready.py:16-46` — 絶対パス・親ディレクトリ・既存ファイル検査、排他的作成、JSON 書き込み、所有 instance のみ削除。
- `serve/server.py:8156-8159, 8255-8258` — server parser と再度行う事前検証。
- `serve/server.py:8615-8622, 8645-8662` — API bind 後の実ポート取得、ready record の構成と公開。
- `serve/server.py:8651-8660, 8703-8713` — 公開失敗時の終了コード・cleanup と handled stop 時の削除。
- `docs/TERMINAL.md:230` — 利用者向けの ready file 説明（ソース実装の補足）。

調査範囲は上記 commit の checkout にある Terminal CLI と server 実装です。Windows 上の実際の ACL 設定や異常終了時のファイルシステム挙動はこの調査では実行確認していません。
