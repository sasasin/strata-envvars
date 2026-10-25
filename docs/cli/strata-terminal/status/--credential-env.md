# `strata status --credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--credential-env` |
| 別名 | なし |
| 値 | サーバー資格情報を格納した環境変数の名前（`NAME`） |

## 役割

ステータス取得時に参照するサーバー資格情報の環境変数名を指定します。資格情報そのものをコマンドライン引数に渡さず、指定した変数から読み取ります。`strata status` は一度だけ読み取り専用のテレメトリ snapshot を取得します。

## 使い方

```sh
strata status --url https://strata.example --credential-env STRATA_API_KEY
```

この例では `STRATA_API_KEY` の値を使用します。`--url` を省略する場合や保存済み接続を使う場合の接続先の選択は、`--credential-env` とは別に解決されます。

## 値と既定値

- 値は環境変数の**名前**です。parser は `NAME` を必須引数として受け取りますが、名前や対応する環境変数の存在は parser では検査しません（`strata_cli/monitor_commands.py:20-25`）。
- 実行時には ASCII の環境変数名 `[A-Za-z_][A-Za-z0-9_]{0,127}` として検証します。1〜128文字で、先頭は英字または `_`、続きは英数字または `_` に限られます。空文字、非 ASCII 文字、ハイフンを含む名前などは無効です（`strata_cli/connections.py:41-42,66-69`）。
- このオプション自体の既定値はありません（`strata_cli/monitor_commands.py:20-25`）。省略時は、保存済み接続が選ばれた場合にはその `credential_env` 参照を使います。保存済み接続がない場合の参照名は `STRATA_API_KEY` です（`strata_cli/connections.py:277-294`）。
- 重複指定時の特別な処理はありません。`argparse` の通常の単一値引数として扱われるため、最後に指定した値が残ります。

## 実行時の動作

`strata status` の parser は `--credential-env` を含む共通接続オプションを登録し、実行時に指定値を `connections.resolve()` へ渡します（`strata_cli/monitor_commands.py:20-33,195-199`）。保存済み接続の credential 参照より明示指定が優先されます。環境変数の値を読み、空でない値があれば `Authorization: Bearer <値>` ヘッダーとしてリクエストに付けます（`strata_cli/connections.py:281-294,299-302`、`strata_cli/monitor_commands.py:196-199`、`strata_cli/client.py:101-107`）。

変数が未設定または空なら、この指定だけを理由にエラーにはならず、通常は認証ヘッダーを付けません。例外として、`--url` と `--connection` のどちらも指定されず、ローカルで `strata launch` が管理する稼働中サーバー情報を見つけた場合、指定した変数が空であればそのローカル起動情報に含まれる key が fallback として使われます（`strata_cli/monitor_commands.py:36-46,195-199`）。

`status` は取得した snapshot を human 表示または JSON で出力します。`--credential-env` は問い合わせ先を選びません。URL や保存済み接続との選択、および接続先の URL 検証は別の処理です（`strata_cli/connections.py:277-301`、`strata_cli/monitor_commands.py:203-213`）。

## 適用条件と副作用

- 資格情報は読み取り専用の status 取得に使われ、コマンドが資格情報を保存する処理はありません。接続管理側も資格情報の値ではなく、環境変数名の参照を記録する設計です（`strata_cli/connections.py:1-5,97-114`）。
- HTTP リクエストはまず `/v1/telemetry` に行き、404 の場合に `/metrics` と `/v1/status`、または `/v1/status` のみに fallback します（`strata_cli/client.py:134-152`）。資格情報は各リクエストで環境変数から得た値を Bearer header に付ける際に使われます（`strata_cli/client.py:101-107`）。
- オプション値が示す環境変数が未設定でも、ローカル起動情報の fallback がない限り、認証なしのリクエストを試みます。サーバー側で認証が必要なら認証エラーになります。

## 出力とエラー

- 無効な環境変数名は `connections.resolve()` の検証で拒否され、エラーメッセージ `credential reference must be an ASCII environment variable name`、終了コード 2 になります（`strata_cli/connections.py:66-69,299-302`、`strata_cli/monitor_commands.py:231-236`）。
- サーバーが 401 または 403 を返すと認証・権限エラーとして終了コード 4 になります。その他の HTTP エラー、接続失敗、timeout、JSON 応答の不正も `ClientError` として処理されます（`strata_cli/client.py:117-132`）。
- 人間向けのエラーは標準エラー出力に `strata: <message>` の形式で出ます。`--output json` または `--json` の場合は JSON エラーを標準出力に出します（`strata_cli/monitor_commands.py:124-129,231-236`）。

## 根拠

- `strata_cli/cli.py:488-493` — `status` parser の登録。
- `strata_cli/monitor_commands.py:20-33` — `--credential-env` の parser 定義と `status` への適用。
- `strata_cli/monitor_commands.py:195-213` — 接続解決、環境変数の読み出しと fallback、snapshot と出力。
- `strata_cli/connections.py:41-42,66-69,277-302` — 環境変数名の形式、保存済み接続との優先関係、既定参照名。
- `strata_cli/client.py:101-125,134-152` — Bearer header、HTTP 失敗、snapshot 取得経路。
