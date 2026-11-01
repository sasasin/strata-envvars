# `STRATA_READ_KEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_READ_KEY` という名前をコード中で固定して読む処理はありません。Strata の読み取り専用 CLI は、認証情報を格納する環境変数名を `--credential-env` または保存済み connection の `credential_env` によって選び、その名前を使って `os.environ` から値を取得します。その参照名として `STRATA_READ_KEY` を指定した場合、この環境変数の値がサーバー認証用 credential として使われます。したがって、名前だけを設定しても自動では選択されず、コマンド引数または connection 設定が必要です。

## 値と判定

値自体は文字列として取得し、数値・真偽値への変換や内容の形式検査はありません。認証ヘッダーを作る `Endpoint` では値が truthy の場合だけ `Authorization: Bearer <値>` を設定します。未設定と空文字はどちらもヘッダーを設定しません。空白だけの文字列は truthy なので、そのままヘッダーに渡されます。値の長さや境界を Strata 側で制限する処理は確認できません。

| 状態 | 読み取り結果・処理 |
|---|---|
| `STRATA_READ_KEY` 未設定 | 選択された名前がこの名前なら `os.environ.get(...)` は `None`。通常の endpoint では認証ヘッダーなし。 |
| 空文字 | endpoint には空文字が渡り、truthy 判定で認証ヘッダーなし。monitor/status/logs の自動検出サーバー経路では、空文字も fallback 条件に入り、起動情報の key があればそちらを使う。 |
| 非空文字 | 文字列を変換せず endpoint に渡す。endpoint は Bearer 認証ヘッダーにそのまま設定する。 |
| 環境変数名として無効 | 保存 connection では ASCII 名 `[A-Za-z_][A-Za-z0-9_]{0,127}` に合わない名前を拒否する。`--credential-env` を受ける monitor 系では同じ検査が行われる。bench 系は Python の `str.isidentifier()` で検査し、対象名 `STRATA_READ_KEY` は許可される。 |

根拠: `strata_cli/connections.py:41-43,66-69,273-302`; `strata_cli/client.py:101-107`。

## 有効になる条件

- `strata status`、`strata monitor`、`strata logs` では `--credential-env STRATA_READ_KEY` を指定するか、保存 connection の `credential_env` にその名前を登録します。connection が選択されず `--credential-env` もない場合の既定参照名は `STRATA_API_KEY` です。明示した `--credential-env` は保存済み connection の参照名より優先します。`STRATA_URL` / `STRATA_CONNECTION` はサーバー選択に使われますが、credential 参照名とは別です。`monitor_commands` はまずプロセス環境から credential を取り、環境値が未設定または空なら、自動検出した実行中 Strata の起動情報に key がある場合それを fallback として使います。明示 URL / connection 指定時など自動検出結果がない場合、この fallback はありません。
- `strata models list --served` は同じ connection 解決を使い、選択された credential 名（明示指定、saved connection、既定 `STRATA_API_KEY` の順）を環境から読みます。自動検出 key への fallback はありません。`--credential-env` は `--served` と併用する必要があります。
- `strata bench run` では `--credential-env` の既定値は `STRATA_API_KEY` で、明示すれば `STRATA_READ_KEY` を使えます。通常の serving suite はこの値を API endpoint に渡し、`--telemetry-credential-env` がなければ telemetry endpoint にも同じ値を使います。standard suite も明示した参照名を読みますが、profile を指定して環境値が未設定または空の場合、profile の API key を fallback として使う分岐があります。

根拠: `strata_cli/monitor_commands.py:20-25,36-46,195-199`; `strata_cli/connections.py:273-302`; `strata_cli/cli.py:148-151,565-573,586-588,312-313,1183-1185,1215-1218,1249-1267`。

## 実行時の詳細

環境変数名は CLI 実行時に解決されます。monitor/status/logs は `connections.resolve()` が既定・saved connection・CLI override の優先順位で名前を決めた後、同じコマンド処理中に `os.environ.get(resolved["credential_env"])` で値を読みます。`connections.resolve()` の `config show --effective` 相当は値を `credential_present` の真偽値にだけ反映し、credential の値は出力しません。connection の作成・保存時も credential 値ではなく環境変数名だけを保存します。process 内 cache はありません。

非空の値は `strata_cli.client.Endpoint.get()` で Bearer header に設定され、許可された読み取り endpoint（`/v1/telemetry`、`/v1/status`、`/metrics`、`/health`）へのリクエストに使われます。`status` / `monitor` / `logs` は `Endpoint` を共有し、served model 一覧と benchmark も同じ endpoint に値を渡します。認証失敗（HTTP 401/403）は `ClientError` の終了コード 4 になり、monitor 系 CLI は `strata: telemetry authentication or permission failed` を stderr に出します。リダイレクト、その他の HTTP エラー、接続失敗も `ClientError` となり、monitor 系では stderr にエラーを出して終了します。credential 値そのものをログや config 出力に出す実装は確認できません。

根拠: `strata_cli/connections.py:273-302`; `strata_cli/monitor_commands.py:195-199,231-240`; `strata_cli/cli.py:570-573,1215-1225,1253-1271`; `strata_cli/client.py:101-129,134-152`。

## 根拠

- 候補名の全体検索では、文字列 `STRATA_READ_KEY` の本番コード中の固定参照は見つかりません。テストにこの名前を `--credential-env` / connection 設定へ渡す例がありますが、実装上の読み取りは任意の環境変数名を扱う helper とその呼び出し側によるものです。
- 保存 connection は環境変数名のみを検証・保持し、`resolve()` が選択した名前の環境値の有無を `credential_present` として示します（`strata_cli/connections.py:66-69,97-114,221-242,273-302`）。
- `monitor_commands` は解決した名前を `os.environ.get()` に渡して endpoint を作ります（`strata_cli/monitor_commands.py:195-199`）。served model 列挙も同様です（`strata_cli/cli.py:565-573`）。
- endpoint は truthy な credential のみを Bearer header に設定し、認証失敗をエラーへ変換します（`strata_cli/client.py:101-129`）。
- bench コマンドも CLI から選ばれた環境変数名で値を取得します（`strata_cli/cli.py:1215-1218,1253-1267`）。

調査対象リポジトリの開始時状態は `main...origin/main` で未コミット変更なしでした。`STRATA_READ_KEY` 固有の読み取りではなく、利用者が読み取り用 credential の参照名としてこの名前を選べる仕組みです。
