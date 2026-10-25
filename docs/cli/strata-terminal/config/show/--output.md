# `strata config show --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--output` |
| 別名 | `--json`（機械形式を選ぶフラグ） |
| 値 | `human` または `json`。省略時は `human` |

## 役割

接続先、credential の参照先、その環境変数に値があるか、各設定値の由来など、`strata config show` が解決したクライアント接続設定の表示形式を選びます。`--output` は設定の解決方法を変更しません（`strata_cli/monitor_commands.py:96-103,132-139`）。

## 使い方

```sh
strata config show --output json
strata config show --output human
strata config show --json
```

## 値と既定値

- `--output` は `argparse` の `choices=("human", "json")` で、引数を1つ取り、既定値は `human` です。値の大文字小文字を変えた表記や他の値は parser に拒否されます（`strata_cli/monitor_commands.py:98-103`）。
- 同じ parser に `--json` が `store_true` フラグとして定義されています。値は不要で、指定すると機械形式が選ばれます。これは `--output json` と同じ表示形式を選びます（`strata_cli/monitor_commands.py:101-103,167-169`）。
- `--output` を複数回指定した場合の専用処理はありません。通常の `argparse` の同一引数処理に従います。

## 実行時の動作

`config show` は `connections.resolve()` で URL、path prefix、credential 環境変数名、credential の有無、timeout、設定値の由来を解決します。`--output human`（既定）では解決結果オブジェクトを JSON テキストとして整形して標準出力へ出します。`--output json` または `--json` では、`schema_version: 1` と `ok: true` を含む `effective` オブジェクトを標準出力へ出します（`strata_cli/monitor_commands.py:132-139,167-175`）。

解決時は、`--url` と `--connection` の同時指定を拒否します。保存済み接続 (`--connection`、または URL 未指定時の `STRATA_CONNECTION`) が選択されると、その保存済み URL・prefix・credential 環境変数名を使います。保存済み接続が選ばれない場合は `--url`、`STRATA_URL`、既定 URL `http://127.0.0.1:8095` の順で URL を決めます。`--credential-env` は選択された保存済み接続の credential 参照先も上書きします。timeout は指定時 `0` より大きく `30` 秒以下でなければならず、省略時は `3.0` 秒です（`strata_cli/connections.py:273-302`）。

`--effective` は同じ `show` parser に登録されていますが、現行実装では `store_true` の値を参照せず、`config` の処理は常に解決結果を表示します。したがって、`--effective` の有無による出力内容の切り替えはありません（`strata_cli/monitor_commands.py:98-103,132-139`）。

## 適用条件と副作用

- このオプションは `strata config show` の parser に属します。他のコマンドの同名 `--output` の値や挙動とは別です（`strata_cli/monitor_commands.py:96-103`）。
- `--quiet` を併用すると、人向け情報出力は `_local_command()` の標準出力リダイレクトで抑制されます。`--output json` / `--json` は機械形式の出力を選ぶため、quiet 抑制の対象にはなりません（`strata_cli/monitor_commands.py:167-175`）。
- `config show` はサーバーへ問い合わせず、接続設定をローカルで解決して表示します。保存済み接続の読込みはあり得ますが、この表示経路から設定ファイルを書き換える処理や credential 値の出力は確認できません。出力に含まれるのは credential 環境変数名と、その環境変数に値があるかを表す `credential_present` です（`strata_cli/monitor_commands.py:132-139`; `strata_cli/connections.py:273-302`）。

## 出力とエラー

- 成功時は終了コード `0` です。human 形式は解決オブジェクト、JSON 形式は `{"schema_version":1,"ok":true,"effective":...}` を標準出力へ出します（`strata_cli/monitor_commands.py:132-139`）。
- 無効な `--output` 値や値なし指定は `argparse` が拒否し、usage とエラーを標準エラーへ出して終了コード `2` とします（parser 定義: `strata_cli/monitor_commands.py:98-103`）。
- 解決時の `ConnectionError` / `ValueError` は human 形式なら `strata: <message>` を標準エラーへ、機械形式なら `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` を標準出力へ出します。timeout 範囲外や `--url` と `--connection` の併用は終了コード `2` です。保存済み接続の欠落・不正などは `ConnectionError` の終了コード（主に `5`）で返ります（`strata_cli/monitor_commands.py:124-129,231-236`; `strata_cli/connections.py:47-50,273-296`; `strata_cli/cli.py:2166-2173`）。

## 根拠

- `strata_cli/monitor_commands.py:96-103` — `config show` parser と `--output`、`--json`、`--quiet`、`--effective` の定義。
- `strata_cli/monitor_commands.py:124-139,167-175,231-240` — 出力形式の選択、解決処理、成功・例外出力。
- `strata_cli/connections.py:273-302` — URL・保存済み接続・credential 参照・timeout・由来の解決。
- `strata_cli/client.py:45-63` — server root URL の形式と remote URL の HTTPS 条件。
- `strata_cli/cli.py:491-494,2166-2188` — `strata` CLI への parser 登録と共通例外処理。

調査範囲は記載した checkout のソースコードです。別 platform の Release 配布物との挙動比較は行っていません。
