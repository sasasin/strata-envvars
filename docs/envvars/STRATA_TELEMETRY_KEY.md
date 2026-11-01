# `STRATA_TELEMETRY_KEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 側の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

## 役割

サーバーでは `/v1/telemetry` 用の読み取り専用キーを設定します。推論用 `api_key` と異なるキーにすると、端末モニターや telemetry を使うベンチマークへ推論キーを渡さずに済みます。サーバーはこの値を起動時に `svc.telemetry_key` へ設定し、`/v1/telemetry` の認証で推論キーとともに照合します。推論・管理用の他のルートでは、このキーを認証キーとして使いません（`serve/server.py:7006-7025,7123-7128,9366-9374`）。

クライアント側では、環境変数の値を直接読む経路に加え、保存接続や `--credential-env` の参照先にこの名前を指定する経路があります。保存接続の既定参照名は `STRATA_TELEMETRY_KEY` ですが、通常の直接 URL 接続では既定の参照名は `STRATA_API_KEY` です（`strata_cli/connections.py:221-225,273-303`; `strata_cli/monitor_commands.py:20-25,75-83`）。

## 値と判定

| 使用箇所 | 未設定 | 空文字 | その他の値 |
|---|---|---|---|
| サーバー起動 | `cfg["telemetry_read_key"]` があればそれを使用し、なければ空文字（キーなし） | 同じく設定値へフォールバック | 設定ファイルの値より環境変数を優先。文字列は `api_key_of()` で前後空白を除去 |
| Desktop のプロファイルベンチマーク | `STRATA_API_KEY` を telemetry にも使う | 同上 | 環境変数値を telemetry endpoint に使用 |
| 通常 CLI の接続・serving benchmark | `--credential-env` 等で選んだ別名の環境変数を読む。直接 URL の既定は `STRATA_API_KEY` | 空文字はクライアント credential として falsy | `--credential-env STRATA_TELEMETRY_KEY` または保存接続にこの名前を設定した場合に読む。serving benchmark は `--telemetry-credential-env STRATA_TELEMETRY_KEY` 指定時に読む |

サーバーの `os.environ.get("STRATA_TELEMETRY_KEY") or cfg.get("telemetry_read_key", "")` は、未設定と空文字を同じ扱いにして設定値へフォールバックします。環境値が空白だけの場合は truthy なので設定値へはフォールバックせず、`api_key_of()` が空キーとして `ValueError` を出します。文字列のカンマ区切りは複数キーとして扱われ、各キーの前後空白を除いて空要素を捨てます。空文字／未設定はキーなしです（`serve/server.py:8358-8367,8385-8399,9368-9374`）。

環境変数値と設定ファイル値は文字列として扱われ、数値変換、真偽値判定、長さ制限はこの読み取り箇所にはありません。設定後に telemetry key のキー集合が推論 `api_key` のキー集合と一つでも重複すると、サーバーは stderr に `telemetry_read_key must differ from every inference API key` と出して起動処理からコード 2 で戻ります（`serve/server.py:9372-9374`）。値が空白だけなど `api_key_of()` で不正なら、stderr に `[strata] invalid telemetry_read_key: ...` を出してコード 2 で戻ります（`serve/server.py:9368-9371`）。

## 有効になる条件

- サーバー側の設定は `serve` のサービス初期化中に行われます。環境変数が空でなく、かつ有効なキーなら、`telemetry_read_key` 設定値より環境変数を優先します。推論 API キーとの重複は許されません（`serve/server.py:9366-9374`）。
- `/v1/telemetry` は、推論キーも telemetry キーもない場合は認証なしで通ります。どちらかが設定されている場合、`Authorization: Bearer ...`（または `x-api-key`）の値が推論キーまたは telemetry キーに一致する必要があります（`serve/server.py:7016-7025`）。
- このキーを受け付けるのは `/v1/telemetry` の認証分岐です。通常の `_authorized()` を使う他 API の認証を、このキーが代替する実装はありません（`serve/server.py:7006-7014,7123-7128`）。
- `strata status`、`strata monitor`、`strata logs` および served `models list` は、`--credential-env` で選んだ環境変数を読むため、この名前を指定できます。保存接続は `--credential-env` の既定値がこの名前です。直接 URL または暗黙の既定接続では `STRATA_API_KEY` を選ぶため、この環境変数を自動選択しません（`strata_cli/monitor_commands.py:20-25,75-83,195-203`; `strata_cli/connections.py:273-303`; `strata_cli/cli.py:568-573`）。
- 端末 client は読み取った credential を telemetry endpoint の Bearer authorization に設定します。認証応答 401/403 は `telemetry authentication or permission failed` として扱われ、status/monitor/logs の CLI は既定の `ClientError.exit_code` である 3 を返します（`strata_cli/client.py:38-42,117-123`; `strata_cli/monitor_commands.py:231-236`）。
- `strata bench run` の serving suite では `--telemetry-credential-env` を明示したときだけ、その名前の環境変数を telemetry endpoint に渡します。省略時は推論 credential を telemetry にも使います。標準 `standard-v1` はこのオプションを拒否します（`strata_cli/cli.py:312-313,1183-1188,1215-1225,1241-1248`）。Desktop の保存プロファイルベンチマーク経路は `STRATA_TELEMETRY_KEY` を直接読み、未設定または空なら `STRATA_API_KEY` にフォールバックします（`strata_control/benchmarking.py:215-217`）。

## 実行時の詳細

サーバーはサービス設定時に一度だけ環境を読み、正規化後の値を `svc.telemetry_key` に保持します。処理中にプロセス環境が変わった場合に再評価するコードはこの経路にはありません（`serve/server.py:4253,9366-9374`）。`/v1/telemetry` への GET では認証成功後に現在のメトリクスと status をまとめてバージョン付き telemetry 応答として返します（`serve/server.py:7123-7128`）。認証失敗時は HTTP 401 と JSON の `missing or wrong telemetry key` を返します（`serve/server.py:7016-7025`）。

CLI の接続参照は値そのものではなく環境変数名を保存します。`connections.resolve()` は選択された参照名に対応する値の有無を `credential_present` に反映し、`monitor_commands.run()` は実際に値を読みます。`--credential-env` は保存接続の参照名を上書きします。起動中の `strata launch` から URL が自動選択される場合は、選択した環境変数値が空なら launch 情報の key にフォールバックします（`strata_cli/connections.py:273-303`; `strata_cli/monitor_commands.py:36-46,195-199`）。クライアントの monitor 経路は起動済みのサーバーへ接続するだけで、サーバーの `STRATA_TELEMETRY_KEY` を子プロセスに転送する実装ではありません。

bench CLI の serving suite は `--credential-env` と `--telemetry-credential-env` の各指定名をコマンド実行時に `os.environ.get()` し、別々の endpoint credential として渡します。専用 telemetry credential を指定しない場合は推論キーを再利用します（`strata_cli/cli.py:1215-1225`）。Desktop profile benchmark は別経路で、固定名 `STRATA_TELEMETRY_KEY` を読み、未設定または空文字なら `STRATA_API_KEY` を使います（`strata_control/benchmarking.py:215-217`）。

## 根拠

- サーバーの key helper と環境読み取り、重複検査: `serve/server.py:8358-8399,9366-9374`
- telemetry 専用認証と endpoint: `serve/server.py:7006-7025,7123-7128`
- monitor/status/logs の動的な credential 参照と接続: `strata_cli/connections.py:66-69,221-225,273-303`; `strata_cli/monitor_commands.py:20-25,75-83,195-203,231-236`
- served `models list` の動的読み取り: `strata_cli/cli.py:568-573`
- CLI serving benchmark と標準 suite の条件: `strata_cli/cli.py:312-313,1183-1188,1215-1225,1241-1248`
- Desktop profile benchmark の値と fallback: `strata_control/benchmarking.py:215-217`
- Strata の利用者向け説明は、読み取り専用キー、推論キーとの分離、`/v1/telemetry` 専用認証を `docs/TERMINAL.md:236` で説明しています。ここでは説明の補足としてのみ参照し、挙動の根拠は実装箇所に置きました。
