# `STRATA_TELEMETRY_KEY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有のサーバーと CLI コード。外部 HTTP ライブラリの内部動作は対象外。

## 役割

サーバーでは、読み取り専用の `GET /v1/telemetry` に対する任意の認証キーです。推論 API キーとは別の値を設定すると、monitor 用クライアントに推論・管理 API の資格情報を渡さずに telemetry だけを読ませられます。このキー単独では他の API endpoint の認証を通過しません。

同じ名前は `strata monitor` / `strata status` の資格情報環境変数の慣例、保存 connection 作成時の既定参照、およびベンチマーク CLI の telemetry 資格情報としても使われます。保存 connection には秘密値ではなく環境変数名が保存されます。

## 値と判定

サーバーは起動時に `os.environ.get("STRATA_TELEMETRY_KEY") or cfg.get("telemetry_read_key", "")` を評価します。したがって環境変数が未設定または空文字なら設定ファイルの `telemetry_read_key` に fallback し、どちらもなければキーなしです。空白だけの環境値は truthy なので設定値を上書きしますが、trim 後に空キーと判定され、起動時にエラーで終了します。

| 入力 | サーバーでの扱い |
|---|---|
| unset、環境変数 `""`、設定値なし | telemetry 専用キーなし |
| 通常の文字列 | 前後空白を除去してキーとして登録 |
| カンマ区切り文字列 | `key_list()` がカンマで分割し、各要素の前後空白と空要素を除いて複数キーとして照合 |
| 空白のみ、または `","` のようにキー要素がない文字列 | `api_key_of()` が `ValueError`。stderr に `[strata] invalid telemetry_read_key: an API key was given but it is empty` を出して起動関数が `2` を返す |
| 推論キーと同じ値（カンマ区切りの各キーを含む） | stderr に `[strata] telemetry_read_key must differ from every inference API key` を出して起動関数が `2` を返す |

`none` は推論キーで「キーなし」を表す特別値ですが、telemetry 用の `explicit_no_key()` 判定には渡されないため、ここでは通常の文字列キーです。環境変数は文字列として扱われ、数値変換や大文字小文字変換はありません。設定ファイル側は文字列のほか、`api_key_of()` が受け付ける文字列リストも処理します。

CLI の monitor/status は保存 connection または `--credential-env` が選んだ環境変数を読みます。`STRATA_TELEMETRY_KEY` は connection 作成 (`strata connection create`) の既定の資格情報名ですが、直接 URL/既定接続での monitor/status の既定参照は `STRATA_API_KEY` です。ベンチマークの `--telemetry-credential-env` は既定で未指定のため、指定時にはその環境変数を使い、未指定なら推論用 `--credential-env` の値を telemetry にも使います。Desktop benchmark は `STRATA_TELEMETRY_KEY` が空または未設定なら `STRATA_API_KEY` を使います。

## 有効になる条件

- `/v1/telemetry` でキーが必要になるのは、サーバーに推論 API キーまたは telemetry キーの少なくとも一方が設定されている場合です。両方なければ endpoint は認証なしで通ります。
- 推論キーがある場合、`/v1/telemetry` は推論キーまたは telemetry キーのどちらでも認証します。telemetry キーのみがある場合はそのキーが必要です。
- それ以外の認証対象 `/v1/*` は通常の `_authorized()` を通り、推論キーだけを受け付けます。telemetry キーだけでは推論 API や `/metrics` の認証を通りません。
- HTTP の資格情報は `Authorization: Bearer ...` を優先し、値が Bearer 形式ならその後ろを trim します。それ以外の場合は `x-api-key` header を使います。
- CLI 側は `Endpoint` に設定された値を資格情報として送ります。保存 connection の資格情報参照は `--credential-env` で上書きできます。

## 実行時の詳細

サーバーでは `main()` の初期化中に一度環境を読み、`svc.telemetry_key` に保存します。起動後にプロセス環境を書き換えても反映されません。設定値の parse 失敗や推論キーとの重複はサーバー起動を止めます。

HTTP handler の `_authorized_telemetry()` は `GET /v1/telemetry` の分岐から呼ばれます。認証に失敗すると HTTP 401 と JSON エラー `{"type":"authentication_error","message":"missing or wrong telemetry key"}` を返します。認証成功時は `svc.metrics()` と `svc.v1_status()` を使って snapshot を作り、`source` を `server-v1` にして返します。通常の `_authorized()` が使われる endpoint は telemetry key を照合しません。

CLI の connection 作成時は `credential_env` という参照名だけを保存します。monitor/status は endpoint 作成時に `os.environ.get(resolved["credential_env"])` を読み、`Endpoint` は値がある場合 `Authorization: Bearer <値>` を設定します。資格情報の実値は connection 設定や `config` 表示に含めず、表示されるのは参照名と有無です。monitor の実行中は endpoint 作成時の値を使います。

## 根拠

- サーバーのキー保持、読み取り、エラー・重複検査: `serve/server.py:3749, 7424-7465, 8268-8275`。
- `/v1/telemetry` と通常 endpoint の認証の違い、および 401 応答: `serve/server.py:6138-6157, 6214-6223`。
- monitor/status の credential 引数、connection 作成時の既定名、参照の優先順位と有無表示: `strata_cli/monitor_commands.py:20-25, 75-83, 132-150`; `strata_cli/connections.py:221-226, 273-302`。
- monitor が選択済みの環境変数を読み endpoint に渡す処理: `strata_cli/monitor_commands.py:195-199`。
- `Endpoint` が Bearer header を設定する処理: `strata_cli/client.py:85-106`。
- ベンチマーク CLI の telemetry 資格情報指定と fallback、および Desktop benchmark の環境変数 fallback: `strata_cli/cli.py:310-312, 1213-1216`; `strata_control/benchmarking.py:215-217`。
- `docs/DETAILS.md` にこの変数の説明は見つからなかったため、役割と挙動は上記ソースを根拠とした。
