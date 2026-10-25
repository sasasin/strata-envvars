# `--credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--credential-env` |
| 別名 | なし |
| 値 | 認証情報を格納する環境変数の名前。ASCII の環境変数名（1〜128文字） |
| 既定値 | `STRATA_TELEMETRY_KEY` |

## 役割

保存する接続情報に、サーバー認証情報そのものではなく、その値を後で読む環境変数名を指定します。接続作成時に環境変数の値を読み取ったり、存在を検査したりはしません。`connection create` の parser は `--credential-env` に値を取らせ、既定値を `STRATA_TELEMETRY_KEY` にしています（`strata_cli/monitor_commands.py:75-83`）。

## 使い方

```sh
strata connection create staging \
  --url https://strata.example.com \
  --credential-env STRATA_STAGING_KEY
```

この例は `staging` という接続を保存し、後続利用時に `STRATA_STAGING_KEY` を参照する設定にします。値に認証情報を直接指定する形式ではありません。

## 値と既定値

値は環境変数名として検証され、`[A-Za-z_][A-Za-z0-9_]{0,127}` に一致する ASCII 名だけが受理されます。空文字、数字から始まる名前、128文字を超える名前、非 ASCII 文字などは拒否されます（`strata_cli/connections.py:41-42,66-69`）。parser 自体には型変換や選択肢制約がなく、接続レコード作成時に `credential_name()` が検証します（`strata_cli/monitor_commands.py:82`, `strata_cli/connections.py:221-226`）。

省略時は `STRATA_TELEMETRY_KEY` です。指定した環境変数が未設定または空でも、接続レコードは作成されます。作成処理では名前を検証して保存するだけで、環境変数の値を参照しません（`strata_cli/connections.py:66-69,221-242`）。

## 実行時の動作

`strata connection create` は指定名、URL、prefix、認証環境変数名を接続レコードにまとめて保存します。レコードの `credential_env` フィールドには変数名だけが入り、秘密の値は保存されません（`strata_cli/connections.py:221-228`）。接続記録は `STRATA_CONNECTION_DIR` が設定されていればその絶対パス、それ以外は Windows では `%APPDATA%/Strata/connections`（未設定時はユーザープロファイル下）、他の OS では `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）に `<name>.json` として作られます（`strata_cli/connections.py:72-94`）。

後で保存済み接続を使うと、そのレコードの `credential_env` が認証情報の参照先になります。`strata_cli/monitor_commands.py` は `connections.resolve()` の結果にある変数名を使って `os.environ` から値を読み、`Endpoint` に渡します（`strata_cli/connections.py:273-303`, `strata_cli/monitor_commands.py:195-199`）。値が空または未設定なら認証情報なしで接続し、値があればテレメトリー要求の `Authorization: Bearer <value>` に使います（`strata_cli/client.py:101-107`）。これは作成後の status/monitor/logs など接続利用時の動作です。

接続作成時に URL への通信は行いません（`strata_cli/monitor_commands.py:147-150`, `strata_cli/connections.py:221-242`）。保存先ディレクトリは owner-only として作成・検査され、接続ファイルは排他的に新規作成され、POSIX では mode `0600` が指定されます（`strata_cli/connections.py:83-90,228-242`）。同名のレコードは上書きしません。

この既定値 `STRATA_TELEMETRY_KEY` は、保存接続を使わない status/monitor/logs の resolver が使う `STRATA_API_KEY` とは異なります。保存接続側では作成時に選んだ参照名が後続利用に使われます（`strata_cli/monitor_commands.py:82`, `strata_cli/connections.py:280-301`）。

## 適用条件と副作用

- このオプションは `strata connection create` のスコープです。`strata connection` や他のサブコマンドの `--credential-env` とは別 parser です。索引のコマンド階層は [`docs/cli/README.md`](../../../README.md) を参照してください。
- 接続名は小文字英字で始まり、小文字英字・数字・`_`・`-` の最大64文字に制限されます。URL と prefix も同時に検証されます。URL は HTTP(S) のサーバールートで、非ローカルのリモート接続は HTTPS が必要です。prefix は別の URL path として保存します（`strata_cli/connections.py:41-63,221-226`; `strata_cli/client.py:45-76`）。
- 認証環境変数名の指定だけでは、環境変数の値の存在やサーバーによる受理は確認されません。認証要否・成否は後続の通信時に決まります（`strata_cli/connections.py:221-242,273-303`; `strata_cli/client.py:101-125`）。
- `--quiet` は成功時の人間向け出力を抑えますが、保存処理は行われます。`--json` または `--output json` は JSON 出力を選び、返る接続レコードにも環境変数名が含まれます（`strata_cli/monitor_commands.py:91-94,147-164,167-175`）。

## 出力とエラー

成功時は human 出力なら接続レコードと revision、JSON 出力なら `ok: true` を含む応答が標準出力に出ます。接続レコードに秘密の値は含まれません（`strata_cli/monitor_commands.py:147-164`）。

無効な環境変数名などの入力エラーは、通常は終了コード `2` で、人間向けでは `strata: ...` を標準エラーへ、JSON モードではエラーオブジェクトを標準出力へ出します（`strata_cli/connections.py:47-69`, `strata_cli/monitor_commands.py:124-129,231-240`）。接続名が既に存在する場合は同様に作成を拒否し、上書きしません（`strata_cli/connections.py:228-234`）。保存ディレクトリや接続ファイルの安全性・形式に関する `ConnectionError` はコード `5` になる場合があり、OS のファイル操作エラーはコード `6` として報告されます（`strata_cli/connections.py:72-90,97-120,128-146,228-242`; `strata_cli/monitor_commands.py:231-240`）。

## 根拠

- parser とオプションの既定値・スコープ: `strata_cli/monitor_commands.py:75-94`
- create の実行分岐と出力: `strata_cli/monitor_commands.py:140-164,167-175`
- 環境変数名の形式、保存先、作成処理: `strata_cli/connections.py:41-94,221-242`
- 保存済み接続から参照する名前の解決: `strata_cli/connections.py:273-303`
- 認証値を環境変数から読み HTTP Authorization header に設定する箇所: `strata_cli/monitor_commands.py:195-199`, `strata_cli/client.py:101-107`
- URL/prefix の制約と HTTP エラー: `strata_cli/client.py:45-76,101-125`
