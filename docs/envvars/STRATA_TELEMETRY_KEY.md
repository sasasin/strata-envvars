# `STRATA_TELEMETRY_KEY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

サーバーでは、設定 `telemetry_read_key` に代わる read-only 認証キーとして起動時に読み込まれ、`GET /v1/telemetry` だけで推論キーとは別に受け付けられます。推論キーが設定されていないサーバーでも、この変数にキーを設定すると telemetry endpoint に認証を要求します。キーを推論キーと重複させる設定は起動失敗です。[`terminal/serve/server.py:9588-9594`](../../../../Niko1221/Strata/terminal/serve/server.py#L9588)

Strata の管理 CLI では、readiness probe と Desktop の serving benchmark が telemetry への要求にこの環境変数を使います。`strata connection create` の既定 credential 名もこの名前ですが、その場合は実行時に保存済み接続の credential reference を使います。[`terminal/strata_control/readiness.py:55-64`](../../../../Niko1221/Strata/terminal/strata_control/readiness.py#L55) [`terminal/strata_control/benchmarking.py:214-218`](../../../../Niko1221/Strata/terminal/strata_control/benchmarking.py#L214) [`terminal/strata_cli/connections.py:221-226`](../../../../Niko1221/Strata/terminal/strata_cli/connections.py#L221)

## 値と判定

サーバーは `os.environ.get("STRATA_TELEMETRY_KEY") or cfg.get("telemetry_read_key", "")` を `api_key_of` に渡します。Python の真偽値判定のため、未設定と空文字は設定ファイルへ fallback します。空白だけの非空文字列は設定ファイルを上書きしてから trim され、空キーとして拒否されます。値は数値等へ変換されず文字列として扱われます。`api_key_of` は前後の空白を除去し、空白だけの値（またはカンマ区切り部分がすべて空の値）を `ValueError` にします。カンマ区切りの複数キーは `key_list` で分割し、各要素の前後空白を除去します。大文字小文字は値の比較で区別されます。[`terminal/serve/server.py:9588-9594`](../../../../Niko1221/Strata/terminal/serve/server.py#L9588) [`terminal/serve/server_parts/http_api.py:211-219,238-252`](../../../../Niko1221/Strata/terminal/serve/server_parts/http_api.py#L211)

| サーバー側の条件 | 環境変数 unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `telemetry_read_key` が設定済み | 設定値を使う | `read-key`（設定値より優先） | `""`（設定値へ fallback）、空白のみ（起動時エラー） |
| `telemetry_read_key` 未設定 | 空キーになり、telemetry 専用キーなし | `read-key` | `""`（専用キーなし）、空白のみ（起動時エラー） |

`"0"`、`"1"`、`"true"`、`"false"`、`"0anything"` はすべて特別な真偽値ではなく、そのままキー文字列です。空文字のみが false となり fallback します。環境変数の値が設定ファイル値より優先されますが、`STRATA_API_KEY` や CLI の `--api-key` が作る推論キーより優先される関係ではなく、独立の telemetry キーです。両方に同じキーが含まれる場合はエラーになります。[`terminal/serve/server.py:9568-9594`](../../../../Niko1221/Strata/terminal/serve/server.py#L9568)

## 有効になる条件

- サーバーで `GET /v1/telemetry` を提供する経路で使われます。OS、GPU backend、build macro による分岐はありません。値を読むのはサーバー初期化時です。[`terminal/serve/server.py:9588-9594,7405-7410`](../../../../Niko1221/Strata/terminal/serve/server.py#L9588)
- 設定ファイルの `telemetry_read_key` があれば、環境変数に非空文字列があるときだけ環境変数側が優先します。未設定または空文字なら設定値が有効です。
- 有効な telemetry キーを推論キー (`STRATA_API_KEY`、設定 `api_key`、`api_keys` 等) のどれかと同じにすると、サーバーは標準エラーへ `[strata] telemetry_read_key must differ from every inference API key` と出し、終了コード 2 を返します。キーの形式エラーも標準エラーに `[strata] invalid telemetry_read_key: ...` を出して 2 を返します。[`terminal/serve/server.py:9588-9594`](../../../../Niko1221/Strata/terminal/serve/server.py#L9588)
- 推論キーも telemetry キーもない場合、`/v1/telemetry` はキーなしで通ります。どちらかが存在すると、telemetry handler は推論キーまたは telemetry キーの一致を要求します。誤り・欠落時は HTTP 401 と `missing or wrong telemetry key` が返ります。[`terminal/serve/server.py:7296-7305`](../../../../Niko1221/Strata/terminal/serve/server.py#L7296)
- 推論用の `--api-key` / `STRATA_API_KEY` とは別枠です。telemetry キーは `/v1/telemetry` の認証に限られ、他 endpoint の認証関数に渡されません。[`terminal/serve/server.py:7283-7294,7296-7305,7405-7410`](../../../../Niko1221/Strata/terminal/serve/server.py#L7283)
- CLI の `strata bench run` serving suite では `--telemetry-credential-env` を指定しないと推論 credential を telemetry 要求にも使い、指定時は指定名の環境変数を使います。`STRATA_TELEMETRY_KEY` を使う例が docs にあります。[`terminal/strata_cli/cli.py:340-341,1247-1281`](../../../../Niko1221/Strata/terminal/strata_cli/cli.py#L340)
- 保存接続では `connection create` の `--credential-env` 既定値が `STRATA_TELEMETRY_KEY` です。通常の URL 接続は既定で `STRATA_API_KEY` を参照し、`--credential-env` は参照名を上書きします。設定表示は参照先の値の有無だけを表示し、値は出しません。[`terminal/strata_cli/monitor_commands.py:75-83`](../../../../Niko1221/Strata/terminal/strata_cli/monitor_commands.py#L75) [`terminal/strata_cli/connections.py:275-303`](../../../../Niko1221/Strata/terminal/strata_cli/connections.py#L275)

## 実行時の詳細

サーバー初期化中に一度読み取り、`svc.telemetry_key` に保存します。リクエストごと・モデル状態ごとの再読込や cache 更新経路はありません。稼働中にプロセス環境を書き換えても、このサーバーの認証値は変わりません。`GET /v1/telemetry` では Authorization Bearer（または `x-api-key`）の値を取り出し、推論キーと telemetry キーのいずれかに一致すればスナップショットを返します。[`terminal/serve/server.py:4262,7296-7305,7405-7411,9588`](../../../../Niko1221/Strata/terminal/serve/server.py#L4262)

readiness verifier は `STRATA_API_KEY` が空でない場合はそれを telemetry request にも使い、推論キーがない場合に限って `STRATA_TELEMETRY_KEY`（空または未設定なら config の `telemetry_read_key`）を使います。したがって環境変数に telemetry キーがあっても、異なる `STRATA_API_KEY` が存在すると verifier は telemetry キーへ fallback しません。[`terminal/strata_control/readiness.py:48-64,105-115`](../../../../Niko1221/Strata/terminal/strata_control/readiness.py#L48)

Desktop serving benchmark は `STRATA_API_KEY` を通常 endpoint に、`STRATA_TELEMETRY_KEY or STRATA_API_KEY` を telemetry endpoint に設定します。値は設定構築時に読みます。[`terminal/strata_control/benchmarking.py:214-221`](../../../../Niko1221/Strata/terminal/strata_control/benchmarking.py#L214)

## ログと測定値

起動時のエラー以外に、この変数の値や設定有無を表示する通常ログはありません。認証失敗は `/v1/telemetry` から HTTP 401 と JSON エラーで観測できます。測定値に関する環境変数ではありません。[`terminal/serve/server.py:7296-7305,9588-9594`](../../../../Niko1221/Strata/terminal/serve/server.py#L7296)

## 根拠

- `terminal/serve/server.py:4262,7283-7305,7405-7411,9568-9594`
- `terminal/serve/server_parts/http_api.py:211-219,238-268`
- `terminal/strata_control/readiness.py:42-64,96-125`
- `terminal/strata_control/benchmarking.py:205-221`
- `terminal/strata_cli/cli.py:340-341,1247-1281`
- `terminal/strata_cli/monitor_commands.py:20-25,75-83`
- `terminal/strata_cli/connections.py:221-226,275-303`
- `tools/release_grid/usage/usage_suite.py:764-779` (`--key-env` で任意の環境変数名を指定する汎用クライアント経路。既定は `STRATA_API_KEY`)
