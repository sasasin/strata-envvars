# `--connection`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--connection` |
| 別名 | なし |
| 値 | 保存済み接続の名前（`NAME`）。小文字英字で始まり、小文字英字・数字・`_`・`-` を使う1〜64文字。 |

## 役割

`strata logs` が接続する Strata サーバーを、名前付きの保存済み接続から選びます。選んだ接続の URL、reverse-proxy prefix、認証情報を読む環境変数名を使って、サーバーの request activity を読み取ります。`logs` は read-only コマンドとして登録されています（`strata_cli/monitor_commands.py:63-72`）。

## 使い方

```sh
strata logs --connection staging
```

`staging` は事前に `strata connection create` で作成した接続名です。`--connection` と `--url` は同時に指定できません（`strata_cli/monitor_commands.py:20-25`、`strata_cli/connections.py:273-284`）。

## 値と既定値

- このオプションは `NAME` を1つ取ります。parser 自体には `choices` や既定値はありません（`strata_cli/monitor_commands.py:20-25`）。値は接続を解決するときに検査され、`[a-z][a-z0-9_-]{0,63}` に合わない名前は拒否されます（`strata_cli/connections.py:41-42,53-56,93-95`）。
- 省略時は、`--url` がなければ `STRATA_CONNECTION` 環境変数の値が保存済み接続名として使われます。環境変数もなく `--url` もない場合は `STRATA_URL`、それもなければ `http://127.0.0.1:8095` が接続先になります（`strata_cli/connections.py:273-291`）。
- `--url` と `--connection` の併用は parser 段階の排他指定ではなく、接続解決時に「どちらかを選ぶ」エラーになります（`strata_cli/connections.py:277-280`）。

## 実行時の動作

- CLI は `logs` parser を登録し、共通の monitor command handler に渡します（`strata_cli/cli.py:488-493,2119-2165`）。
- 明示した名前（または `STRATA_CONNECTION`）から保存済み接続を読み、保存された URL、prefix、credential environment variable 名を選択します。`--credential-env` を同時に指定した場合は、接続に保存された環境変数名をその指定で置き換えます（`strata_cli/connections.py:273-294`）。
- 保存済み接続を明示すると `strata logs` は実行中の `strata launch` 情報から接続先を自動検出しません。`running_launch()` は `--url` または `--connection` がない場合だけ調べられ、環境変数 `STRATA_URL` / `STRATA_CONNECTION` がある場合にも launch 情報を読まずに戻ります（`strata_cli/monitor_commands.py:36-46,195-199`）。
- 接続レコード自体に credential の値は含めず、指定された環境変数から実行時に値を取得します。その値が空または未設定なら認証ヘッダーを付けず、存在すれば `Authorization: Bearer ...` として送ります（`strata_cli/connections.py:1-4,273-302`、`strata_cli/monitor_commands.py:198-199`、`strata_cli/client.py:101-107`）。
- `logs` は解決した endpoint から snapshot を取得し、サーバーの `activity` を表示します。指定した接続はサーバーへの読み取り通信を発生させますが、`--connection` の処理で接続ファイルを書き換えることはありません（`strata_cli/logs.py:101-124`、`strata_cli/client.py:101-152`）。

## 適用条件と副作用

- 接続名に対応する保存済みレコードが必要です。接続ファイルは `STRATA_CONNECTION_DIR` があればその絶対パス、なければ POSIX では `${XDG_CONFIG_HOME:-~/.config}/strata/connections`、Windows では `%APPDATA%/Strata/connections` 以下から読みます。相対 `STRATA_CONNECTION_DIR` は拒否されます（`strata_cli/connections.py:72-95`）。
- レコードは通常ファイルで4 KiB以下であること、POSIX では所有者専用であること、schema/version、ファイル名と ID、URL、prefix、credential environment variable 名が有効であることを確認してから使われます（`strata_cli/connections.py:97-120,128-146`）。保存 URL は server root 形式で、非ローカル接続には HTTPS が必要です。prefix は単純な path segment のみ許可されます（`strata_cli/client.py:45-76`）。
- 接続先取得は telemetry API に限定され、HTTP redirect は追わず、JSON 以外の応答や2 MiBを超える応答を拒否します（`strata_cli/client.py:79-125`）。接続ファイルを選ぶ操作そのものはローカル読み取りです。

## 出力とエラー

- 保存名が不正、または `--url` と併用された場合はエラーコード2です。`--connection` に対応する接続がない、またはレコードが不正・読めない場合はエラーコード5です（`strata_cli/connections.py:47-56,128-146,273-280`）。通常表示では `strata: ...` を stderr に出し、JSON/JSONL 出力ではエラー object を stdout に出します（`strata_cli/monitor_commands.py:124-129,231-236`）。
- サーバーが request activity を提供しない場合もコード5、認証拒否はコード4、接続失敗はコード3です（`strata_cli/logs.py:105-108`、`strata_cli/client.py:117-125`）。

## 根拠

- parser 定義と logs 固有 option: `strata_cli/monitor_commands.py:20-25,63-72`
- CLI への登録と dispatch: `strata_cli/cli.py:488-493,2119-2165`
- 接続名・保存ファイルの検証と解決: `strata_cli/connections.py:41-44,53-56,72-114,128-146,273-302`
- URL/prefix の検証、request の認証・snapshot 取得: `strata_cli/client.py:45-76,79-152`
- logs の request activity 読み取り: `strata_cli/logs.py:101-151`

