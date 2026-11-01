# `STRATA_CONNECTION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`strata status`、`strata monitor`、`strata logs`、`strata config show`、および `strata models list --served` が接続する保存済みサーバー接続の名前を選びます。接続記録にはサーバー URL、任意のパス prefix、認証情報を格納した環境変数の名前が含まれます。`STRATA_CONNECTION` 自体には秘密情報や URL ではなく、接続記録の ID を設定します。接続記録は共通の `connections.resolve()` から読み込まれます（`strata_cli/connections.py:273-301`）。

## 値と判定

値は文字列として取得し、boolean や数値への変換はしません。`connection or ...` による真偽値判定の後、選ばれた名前は保存記録のファイル名として検証されます。

| 値 | 処理 |
|---|---|
| 未設定 | 接続記録を選ばず、後述の `STRATA_URL` または既定 URL を使う。 |
| 空文字 | Python では偽となるため、未設定と同様に接続記録を選ばない。 |
| 真値で有効な名前 | `[a-z][a-z0-9_-]{0,63}` 全体に一致する場合に読み込む。英小文字で始まり、以降は英小文字・数字・`_`・`-`、長さ 1〜64 文字。 |
| 真値で無効な名前 | 空白、大文字、スラッシュ、64文字超などは名前検証で拒否される。大文字小文字の正規化や trim はしない。 |
| 有効な名前だが記録がない | `connection '<名前>' is not saved; use strata connection create` の接続エラーになる。 |

名前の正規表現とエラーは `strata_cli/connections.py:41-56`、選択と記録の読込は `strata_cli/connections.py:273-285`、未保存記録のエラーは `strata_cli/connections.py:128-146` にあります。

## 有効になる条件と優先順位

`connections.resolve()` に URL 引数が渡されず、かつ `--connection` の引数が真値でないとき、真値の `STRATA_CONNECTION` が接続記録を選びます。その場合、記録の URL・prefix・credential-env 参照を使います。

| 条件 | 選択される接続先 |
|---|---|
| `--url` が指定される | `--url`。`STRATA_CONNECTION` は参照しない。 |
| `--connection NAME` が指定される | `NAME` の保存記録。`STRATA_CONNECTION` より優先。 |
| 上記がなく `STRATA_CONNECTION` が真値 | その名前の保存記録。`STRATA_URL` より優先。 |
| 接続記録の選択がない | `STRATA_URL` があればその値、なければ `http://127.0.0.1:8095`。 |

`--url` と `--connection` の両方が非 `None` なら `choose --url or --connection, not both` で拒否します。接続記録を選んだ後でも `--credential-env` が指定されれば認証情報の参照名だけは CLI 指定で上書きされます。これらの分岐は `strata_cli/connections.py:277-301` にあります。CLI の登録箇所は `strata_cli/monitor_commands.py:20-25,96-103`、`strata_cli/cli.py:141-152` です。

## 実行時の詳細

共通 resolver は呼び出しごとに `os.environ` を参照し、値をプロセス内で cache しません。`environment` 引数が渡されたときだけその辞書を使いますが、Strata の実際の各 CLI 呼び出しでは resolver にその引数を渡さないため、通常は `os.environ` が使われます（`strata_cli/connections.py:273-277`）。

monitor/status/logs では、明示的な `--url` または `--connection` がない場合、先に `running_launch()` が呼ばれます。ここでも `STRATA_URL` または真値の `STRATA_CONNECTION` があればローカル起動中サーバーの探索をスキップします。どちらも真値でないときは launch 情報を試し、見つかった URL を resolver に渡します（`strata_cli/monitor_commands.py:36-46,195-199`）。空の `STRATA_CONNECTION` はこの判定でも探索を妨げません。`config show` と `models list --served` は、それぞれ resolver に渡して選択を行います（`strata_cli/monitor_commands.py:132-139`、`strata_cli/cli.py:564-573`）。

resolver は選んだ記録から credential-env 名を得ます。status/monitor/logs はその名前の環境変数の値を `Endpoint` に渡し、served model の一覧も同様に値を渡します。`config show` は値そのものではなく、参照名と値が truthy かどうかを `credential_present` として返します（`strata_cli/connections.py:299-301`、`strata_cli/monitor_commands.py:198-199`、`strata_cli/cli.py:569-573`）。

接続名が不正、または保存記録が見つからない場合、monitor 系のコマンドは接続エラーを捕捉し、通常出力では stderr に `strata: <エラー>`、JSON 出力ではエラー JSON を出して終了コードを返します。名前エラーの既定終了コードは 2、保存記録の欠落は 5 です（`strata_cli/connections.py:47-50,128-146`、`strata_cli/monitor_commands.py:124-129,231-240`）。通常の `strata` CLI も `ValueError` を捕捉し、`strata: <エラー>` を stderr に出して `exit_code`（なければ 2）を返します（`strata_cli/cli.py:2165-2173`）。

## 根拠

- 読み取り・優先順位・既定 URL・CLI credential-env 上書き: `strata_cli/connections.py:273-301`
- 接続名の許容形式、記録読み込みと欠落時エラー: `strata_cli/connections.py:41-56,128-146`
- monitor/status/logs の起動中サーバー探索抑止と endpoint 生成: `strata_cli/monitor_commands.py:36-46,195-199`
- `config show` と `models list --served` の resolver 呼び出し: `strata_cli/monitor_commands.py:132-139`、`strata_cli/cli.py:564-573`
- 接続エラーの出力・終了経路: `strata_cli/monitor_commands.py:124-129,231-240`、`strata_cli/cli.py:2165-2173`
- 利用者向け説明（優先順位と用途）: `docs/TERMINAL.md:30-44`
