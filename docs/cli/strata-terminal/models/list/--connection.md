# `--connection`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--connection NAME` |
| 別名 | なし |
| 値 | 保存済み接続の名前。parser 上は文字列で、既定値はない |

## 役割

`--served` と組み合わせ、保存済みの読み取り専用接続を使って Strata サーバーへ問い合わせます。返るのはそのサーバーの現在のインスタンスが報告するモデルだけで、ローカルにインストールされた全モデルの一覧ではありません（`strata_cli/cli.py:143-151,564-585`）。

## 使い方

```sh
strata models list --served --connection work
```

`work` は `strata connection create` などで保存した接続名です。接続オプションを使うときは `--served` を指定します。

## 値と既定値

- `--connection` は値を1つ取ります。parser 自体に既定値や選択肢はありません（`strata_cli/cli.py:148-151`）。
- 実行時に接続名は小文字 ASCII の `a-z` で始まり、続く文字は `a-z`、`0-9`、`_`、`-`、全体で最大64文字という形式で検証されます（`strata_cli/connections.py:41,53-57`）。保存先は接続名に対応する JSON ファイルです。ファイルがない場合や内容・権限が不正な場合は接続エラーになります（`strata_cli/connections.py:72-94,97-114,128-146`）。
- `--url` と同時には使えません。両方指定した場合は実行時に `choose --url or --connection, not both` で拒否されます（`strata_cli/connections.py:273-280`）。
- `--connection` を省略し、`--url` も省略した場合に `--served` が選ぶ接続は、環境変数 `STRATA_CONNECTION`、次に `STRATA_URL`、最後に `http://127.0.0.1:8095` の順です。`STRATA_CONNECTION` が選ばれると保存接続の URL・prefix・credential 参照を使います（`strata_cli/connections.py:273-303`）。
- 保存接続が持つ credential 環境変数名は `--credential-env NAME` で上書きできます。`--timeout` があれば要求 timeout に使われ、指定値は 0 より大きく30秒以下でなければなりません（`strata_cli/connections.py:273-303`）。

## 実行時の動作

`--served` 分岐では保存接続を読み込み、記録された credential 環境変数名から実際の資格情報を環境より取得して `Endpoint` を作り、snapshot を要求します。接続ファイルには資格情報の値ではなく環境変数名が保存されます（`strata_cli/cli.py:564-585`; `strata_cli/connections.py:97-114,273-303`）。

クライアントは `/v1/telemetry` を優先し、404 の場合に `/metrics` と `/v1/status`、さらに `/v1/status` 単独の互換経路を使います。HTTP リダイレクトは追跡せず、応答は JSON であることとサイズ上限2 MiBを検査します（`strata_cli/client.py:101-132,134-152`）。結果のモデル配列には報告されたモデル ID、ロード状態、インスタンス ID が含まれ、互換性は `unverified` とされます（`strata_cli/cli.py:573-585`）。

## 適用条件と副作用

- `--connection` は `--served` 用です。`--served` を付けずに `--connection`（または `--url`、`--credential-env`、`--timeout`）を渡すと、終了コード2で `connection options require --served` になります。`--installed` と `--served` は parser 上で相互排他です（`strata_cli/cli.py:143-151,586-588`）。
- `--served` と `--install-dir` の併用も終了コード2で拒否されます（`strata_cli/cli.py:565-568`）。
- 接続ファイルは読み取り、サーバーの読み取り専用 telemetry/status 系 HTTP endpoint にアクセスします。このオプションの処理は接続設定やモデルを変更しません（`strata_cli/cli.py:568-585`; `strata_cli/client.py:101-152`）。
- 接続 URL はサーバールートである必要があり、リモート接続は HTTPS が必要です。HTTP は localhost / loopback に限られます。保存接続の URL と prefix も読み込み時に検証されます（`strata_cli/client.py:45-63,66-76`; `strata_cli/connections.py:97-114`）。

## 出力とエラー

成功時は既定の human 出力、または `--output json` による JSON 出力を行います。サーバーがモデル ID を報告しない場合は human 出力に `No model ID reported by this server` と表示されます（`strata_cli/cli.py:152,573-585`; 成功出力: `strata_cli/cli.py:535-540`）。

無効な接続名、未保存の接続、接続ファイルの読み取り・検証失敗は `ValueError` 系の接続エラーとして処理されます。形式・競合エラーは通常終了コード2、ファイルや保存値の問題はコード5です。HTTP 認証・権限拒否はコード4、それ以外の接続失敗は通常コード3、非互換 telemetry schema はコード5です。エラーは human 形式では stderr、JSON 形式では標準出力にエラーオブジェクトとして出ます（`strata_cli/connections.py:47-50,128-146,273-296`; `strata_cli/client.py:38-42,117-152`; `strata_cli/cli.py:2166-2188,527-532`）。

## 根拠

- `strata_cli/cli.py:141-152` — `models list` の parser、相互排他スコープ、`--connection` 宣言。
- `strata_cli/cli.py:564-588` — `--served` での接続解決、snapshot 取得、ローカル一覧との適用条件。
- `strata_cli/connections.py:41-57,72-114,128-146,273-303` — 名前規則、保存ファイル検査、接続値と優先順位の解決。
- `strata_cli/client.py:45-63,101-152` — URL 検証、HTTP 要求、認証・通信失敗、snapshot の互換経路。
- `strata_cli/cli.py:527-540,2166-2188` — human / JSON の成功・失敗出力とエラーコード伝播。
