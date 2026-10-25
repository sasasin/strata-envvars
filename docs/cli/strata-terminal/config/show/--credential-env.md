# `--credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--credential-env` |
| 別名 | なし |
| 値 | `NAME`。サーバー資格情報を格納する環境変数の名前 |

## 役割

接続設定の表示時に、サーバー資格情報を探す環境変数名を指定します。`strata config show` は接続先や資格情報の参照元を解決して表示しますが、このオプションで指定した環境変数の秘密値そのものは表示しません（`strata_cli/connections.py:299-302`）。

## 使い方

```sh
strata config show --credential-env STRATA_API_KEY
```

JSON形式で参照名と資格情報の有無を確認する例です。

```sh
strata config show --credential-env STRATA_API_KEY --output json
```

## 値と既定値

- 値は必須です。parser は値を `NAME` として受け取り、既定値を設定していません（`strata_cli/monitor_commands.py:98-103`）。
- parser 自体は文字列の形式検証をしません。実行時に `credential_name()` が `[A-Za-z_][A-Za-z0-9_]{0,127}` に一致する ASCII の環境変数名か検証します。先頭は英字または `_`、全体は1〜128文字です。空文字、ハイフンを含む名前、128文字を超える名前などは拒否されます（`strata_cli/connections.py:41-42,66-69`）。
- このオプションを省略した場合、保存済み接続が選ばれていればその接続レコードの `credential_env` を使います。保存済み接続が選ばれていない場合の既定名は `STRATA_API_KEY` です（`strata_cli/connections.py:277-291`）。

## 実行時の動作

- `strata config show` の parser は `--credential-env` を `_connection()` 経由で登録し、実行時に `connections.resolve()` へ渡します（`strata_cli/monitor_commands.py:20-25,96-103,132-139`）。
- `--credential-env NAME` を指定すると、保存済み接続または既定の資格情報参照名を上書きし、出力の `origins.credential_env` は `flag` になります（`strata_cli/connections.py:292-294`）。
- `--connection NAME` または環境変数 `STRATA_CONNECTION` で保存済み接続が選択される場合、その接続に保存された参照名が使われます。明示した `--credential-env` はその参照名を上書きします。明示 `--url` があると `STRATA_CONNECTION` による自動選択は行われません。また `--url` と `--connection` の同時指定はエラーです（`strata_cli/connections.py:277-285`）。
- 接続が選択されず `--credential-env` もない場合、参照名は `STRATA_API_KEY` です。接続先 URL は `--url`、`STRATA_URL`、既定の `http://127.0.0.1:8095` の順で決まり、資格情報参照名とは別に解決されます（`strata_cli/connections.py:285-291`）。
- 表示結果には `credential_env` と、実行環境内でその変数が空でない値を持つかを示す `credential_present`（真偽値）が含まれます。資格情報の値は表示されません（`strata_cli/connections.py:299-302`）。このコマンドの処理は設定を解決して出力するだけで、サーバーへのリクエストは行いません（`strata_cli/monitor_commands.py:132-139`）。
- `--effective` は同じ parser にありますが、`config show` はフラグの有無にかかわらず `connections.resolve()` の結果を表示します（`strata_cli/monitor_commands.py:98-103,132-139`）。

## 適用条件と副作用

- 指定した環境変数名は、`strata` プロセスの環境で参照されます。変数が未設定または空文字の場合、`credential_present` は `false` になります（`strata_cli/connections.py:276,299-302`）。
- `--connection` または `STRATA_CONNECTION` が選ばれると、保存済み接続ファイルを読み込み検証します。接続ファイルの欠落や不正、権限・形式の問題は表示処理の失敗になります（`strata_cli/connections.py:128-146,277-285`）。
- URL も同時に解決されるため、URL がサーバールート形式でない場合や、リモート HTTP などの安全条件に合わない場合は失敗します（`strata_cli/connections.py:298-300`; URL の条件は `strata_cli/client.py:45-63`）。
- 設定表示ではネットワークアクセスや設定ファイルの書き込みを行いません。保存済み接続を使う場合はそのレコードを読み込みます（`strata_cli/monitor_commands.py:132-139`; 読み込みは `strata_cli/connections.py:128-146`）。

## 出力とエラー

- 通常は解決済み設定を整形 JSON として標準出力へ出します。`--output json` または `--json` では `schema_version` と `ok` を含む機械可読形式になります（`strata_cli/monitor_commands.py:101-103,124-139,167-175`）。
- `--quiet` は通常形式の標準出力を抑制します。JSON モードでは `quiet` が無効になるため、JSON 出力は抑制されません（`strata_cli/monitor_commands.py:167-175`）。
- 不正な環境変数名や URL などの値エラーは終了コード `2` になり、保存済み接続の欠落・不正など `ConnectionError` が明示する失敗はその終了コード（通常 `5`）になります。通常形式では `strata: ...` を標準エラーへ、JSON モードではエラーオブジェクトを標準出力へ出します（`strata_cli/connections.py:47-50,66-69,128-146`; `strata_cli/monitor_commands.py:124-129,231-236`）。

## 根拠

- parser 定義とコマンド登録: `strata_cli/monitor_commands.py:20-25,96-113`、トップレベル CLI への登録 `strata_cli/cli.py:488-493`。
- 値の形式検証、既定値、優先順位、表示フィールド: `strata_cli/connections.py:41-42,66-69,273-302`。
- `config show` の実際の解決・表示と失敗出力: `strata_cli/monitor_commands.py:124-139,167-175,231-240`。
- URL の検証条件: `strata_cli/client.py:45-63`。

