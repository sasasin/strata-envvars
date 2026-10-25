# `--connection`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--connection` |
| 別名 | なし |
| 値 | 必須の接続名 `NAME`。保存済み接続の ID 規則に従う |

## 役割

保存済みの接続を選び、その接続を使った有効なクライアント設定を表示します。このコマンドは設定をローカルで解決するもので、サーバーへの接続確認は行いません。

## 使い方

```sh
strata config show --connection office
```

JSON 出力にする場合:

```sh
strata config show --connection office --json
```

## 値と既定値

- parser は `--connection NAME` として値を1つ要求します。値自体は parser では検証せず、指定された接続を読み込む段階で検証します（`strata_cli/monitor_commands.py:20-25, 96-103, 132-139`）。
- 接続名は小文字の `a-z` で始まり、その後に小文字英字、数字、`_`、`-` を最大63文字まで使えます（全体で1〜64文字）。規則外の名前は `strata_cli/connections.py:41, 53-56` で拒否されます。
- `--connection` を省略した場合、`--url` もなければ環境変数 `STRATA_CONNECTION` が選択候補になります。どちらも指定されない場合は保存済み接続を使わず、`STRATA_URL`、または既定 URL `http://127.0.0.1:8095` が使われます（`strata_cli/connections.py:44, 273-291`）。
- `--url` と `--connection` の同時指定はエラーです（`strata_cli/connections.py:277-279`）。
- 空文字列を明示した場合、解決処理は真偽値で選択するため、`STRATA_CONNECTION` が設定されていればそちらが使われ、なければ保存済み接続は選ばれません（`strata_cli/connections.py:276-280`）。

## 実行時の動作

指定名の接続 JSON ファイルを読み込み、そこに記録された URL、path prefix、認証値を格納する環境変数名を有効設定として返します。認証値そのものは接続レコードには保存せず、結果には参照先環境変数に値が存在するかを示す `credential_present` が含まれます（`strata_cli/connections.py:1-4, 128-146, 273-303`）。

通常の出力は有効設定の JSON 表現です。`--json` または `--output json` を使うと `schema_version`、`ok`、`effective` を含む機械可読形式になります。`--quiet` は通常出力を抑制しますが、JSON モードでは抑制されません（`strata_cli/monitor_commands.py:101-103, 132-139, 167-175`）。

認証環境変数名は `--credential-env NAME` で上書きできます。`--timeout` もこのコマンドで解決され、未指定時は3秒、明示値は0より大きく30秒以下である必要があります（`strata_cli/monitor_commands.py:20-25, 100`; `strata_cli/connections.py:292-303`）。

`--effective` も同じ parser にありますが、設定表示の実装は常に `connections.resolve()` を実行するため、このフラグの指定有無による動作差はありません（`strata_cli/monitor_commands.py:96-103, 132-139`）。

## 適用条件と副作用

- 選択した接続のファイルをローカルから読み取ります。接続ディレクトリは `STRATA_CONNECTION_DIR`、Windows では `APPDATA`、その他の環境では `XDG_CONFIG_HOME`（未設定時はホームの `.config`）から決まります。`STRATA_CONNECTION_DIR` を指定する場合は絶対パスが必要です（`strata_cli/connections.py:72-90, 93-95`）。
- ファイルは通常ファイルで4 KiB以下、POSIX では所有者専用であることが要求されます。接続データのスキーマ、ID、URL、prefix、認証環境変数名も検証されます（`strata_cli/connections.py:97-121, 128-146`）。
- コマンドは接続先へのネットワーク要求を行いません。`strata config` はローカルコマンドとして直接設定解決に進み、監視コマンド用の Endpoint や snapshot の処理経路には入りません（`strata_cli/monitor_commands.py:132-139, 167-175`）。

## 出力とエラー

- 指定名の接続が存在しない、読み取れない、権限・形式・内容が不正な場合は `ConnectionError` になります。未保存の接続は exit code 5 で拒否され、他のレコード検証エラーもコード5として扱われます（`strata_cli/connections.py:128-146`）。
- `--url` との併用、無効な接続名、無効な timeout などの入力エラーは既定で exit code 2 です。人間向けモードでは `strata: ...` を stderr に出し、JSON モードでは `ok: false` とエラーコード・メッセージを stdout に出します（`strata_cli/connections.py:47-56, 277-296`; `strata_cli/monitor_commands.py:124-129, 231-240`）。
- 接続設定を表示する成功経路は stdout に出力し、終了コード0を返します（`strata_cli/monitor_commands.py:132-139`）。

## 根拠

- parser 定義とコマンド階層: `strata_cli/monitor_commands.py:20-25, 96-103`
- オプション値を渡して設定を解決し、結果を出力する箇所: `strata_cli/monitor_commands.py:132-139, 167-175`
- 接続名・保存レコードの読み込みと検証: `strata_cli/connections.py:41-56, 97-121, 128-146`
- URL/環境変数/既定値の選択、timeout と出力項目の解決: `strata_cli/connections.py:273-303`
- URL の安全性と remote URL の HTTPS 条件: `strata_cli/client.py:45-63`
