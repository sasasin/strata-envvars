# `--credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--credential-env` |
| 別名 | なし |
| 値 | 環境変数名（ASCII の英字または `_` で始まり、英数字・`_` を最大 128 文字） |

## 役割

サーバー認証情報を保持する環境変数の名前を指定します。CLI はその変数から値を読み、ログ取得に使う読み取り専用 telemetry リクエストの Bearer 認証情報として渡します。秘密値そのものをオプション引数には指定しません。

## 使い方

```sh
strata logs --url https://inference.example --credential-env STRATA_TELEMETRY_KEY
```

この例では、実行環境に `STRATA_TELEMETRY_KEY` を設定しておきます。保存済み接続と組み合わせる場合は `--url` の代わりに `--connection NAME` を指定できます。

## 値と既定値

値を一つ取ります。parser 自体には明示的な既定値がなく、省略時の credential 参照名は接続解決で決まります。`--connection` を選んだ場合は保存済み接続の `credential_env`、保存済み接続がない場合は `STRATA_API_KEY` です。`--credential-env NAME` を指定すると、どちらの参照名も `NAME` に置き換わります（`strata_cli/monitor_commands.py:20-25,63-66`, `strata_cli/connections.py:273-294`）。

名前は `[A-Za-z_][A-Za-z0-9_]{0,127}` に合致する必要があります。空文字、非 ASCII 文字、先頭が数字の名前、129 文字以上などは接続解決時に拒否されます（`strata_cli/connections.py:41-43,66-69`）。値を省略すると `argparse` の引数エラーになります。

## 実行時の動作

`strata logs` は共通接続 parser を使い、解決した参照名を `os.environ.get()` で読みます。環境変数が未設定または空なら、通常は認証情報なしで接続します。ただし `--url` と `--connection` のどちらも指定せず、起動中の Strata launch server が見つかった場合は、その起動情報に含まれる key が代替値になります。明示した環境変数に非空値があれば、その値が優先されます（`strata_cli/monitor_commands.py:195-202`）。

取得した値は `Endpoint` に渡され、値が truthy の場合に限り `Authorization: Bearer <値>` ヘッダーとして追加されます。`strata logs` は `Endpoint.snapshot()` を呼び、通常は `/v1/telemetry` から snapshot を取得します。そこで HTTP 404 の場合は `/metrics` と `/v1/status` に fallback します。いずれの接続先でも credential 値を URL に埋め込まず、ログ表示用の活動データを読み取ります（`strata_cli/client.py:101-108,134-152`, `strata_cli/logs.py:101-124`）。

## 適用条件と副作用

このオプションは `strata logs` の接続認証に適用され、ローカル設定ファイルを書き換えません。値は CLI プロセスの環境から読み取られ、認証が必要な場合は telemetry HTTP リクエストに送信されます。リモート URL は HTTPS が必要で、HTTP は localhost または loopback に限られます（`strata_cli/client.py:45-63`）。

省略時に使われる `STRATA_API_KEY` は従来の広い権限を持つキーとして文書化されています。読み取り専用用途では、サーバー側の `STRATA_TELEMETRY_KEY` に対応する別のクライアント環境変数を指定できます（`docs/TERMINAL.md:236`）。

## 出力とエラー

無効な環境変数名は接続解決エラーとなり、通常出力では `strata: ...` を stderr に出して終了コード 2 を返します。`--output json` または `--json` 使用時は、エラーコードとメッセージを含む JSON を stdout に出します（`strata_cli/monitor_commands.py:124-129,231-236`）。

認証が拒否されると「telemetry authentication or permission failed」、終了コード 4 になります。接続障害は既定で終了コード 3、redirect は最終 server root を使うよう促すエラー、未対応または不正な telemetry/activity は終了コード 5 です（`strata_cli/client.py:38-42,117-125,142-152`, `strata_cli/logs.py:25-33,105-108`, `strata_cli/monitor_commands.py:231-236`）。

## 根拠

- parser と共通接続引数: `strata_cli/monitor_commands.py:20-25,63-72`
- option 値の検証と接続・環境変数参照の優先順位: `strata_cli/connections.py:41-43,66-69,273-302`
- logs の接続解決と credential の引き渡し: `strata_cli/monitor_commands.py:195-202`
- HTTP 認証、snapshot endpoint、HTTP 失敗経路: `strata_cli/client.py:101-132,134-152`
- logs の snapshot 利用と活動データの出力: `strata_cli/logs.py:101-124`
- エラー出力・終了コードの受け渡し: `strata_cli/monitor_commands.py:124-129,231-244`
- telemetry 用 credential の利用案内: `docs/TERMINAL.md:236`
