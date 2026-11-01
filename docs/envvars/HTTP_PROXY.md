# `HTTP_PROXY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数処理は対象外。

## 役割

Strata 自身は `HTTP_PROXY` を読み取って値を解釈する処理を持ちません。サーバーが起動するエンジン子プロセスには通常、親プロセスの環境をコピーして渡します。そのため strict offline が無効なら、親環境に `HTTP_PROXY` があればその値が渡り、なければ未設定のままです。strict offline が有効なら、子エンジンの環境では空文字に上書きされます（`strata_control/offline.py:47-60`, `serve/server.py:3747-3760,3765-3777`）。

一方、Strata のローカル HTTP 通信 helper は `ProxyHandler({})` で opener を作り、loopback 宛てにそれを使います。このコード経路は `HTTP_PROXY` の値を参照しません（`strata_control/loopback.py:13-14,17-28`）。

## 値と判定

`HTTP_PROXY` の値に対する parse、空文字判定、数値変換、境界検査、無効値 fallback はありません。値の扱いは子エンジンを起動する状況で次のように異なります。

| 状況 | 子エンジンに渡す `HTTP_PROXY` |
|---|---|
| strict offline 無効、設定ファイルの `env` にキーなし | 親プロセスの環境をそのまま引き継ぐ。親で未設定なら未設定、空文字なら空文字、その他の値ならその値 |
| strict offline 無効、設定ファイルの `env` にキーあり | 設定値を `str()` にした値で親環境を上書き |
| strict offline 有効 | `OFFLINE_ENV` の適用により空文字。親環境や設定ファイルの値より優先 |

この変数自体は Strata の起動条件や既定値を決めません。設定ファイルの `env` は `child_env()` で他の環境をコピーした後に適用され、offline ポリシーはさらにその後に適用されます。したがって strict offline が有効な場合、設定ファイルから `HTTP_PROXY` を設定しても子エンジンには空文字が渡ります（`serve/server.py:3750,3759-3760,3765-3777`）。

## 有効になる条件

- 通常の単一エンジン起動では `child_env()` の戻り値が `StrataEngine` に渡されます（`serve/server.py:9191-9194,9278-9279`）。replica と split の各エンジンも同じ `child_env()` を使います（`serve/server.py:8704-8710,8768-8777`）。
- offline の指定は `serve --offline` CLI 引数、保存済み profile、run config の順で選ばれ、CLI で `--offline` を指定した値が優先されます。どれにも指定がなければ既定値は `false` です（`strata_cli/cli.py:745-765`）。CLI で有効になった場合はサーバー起動引数に `--offline` が追加されます（`strata_cli/cli.py:802-803`）。サーバー側はこのフラグを `store_true` で受け取ります（`serve/server.py:9000-9001`）。
- offline 有効時、MCP server、`before_load`、または strict offline と両立しない profile 設定があるとサーバーは `ap.error()` で起動を拒否します（`serve/server.py:9173-9184`）。これは `HTTP_PROXY` の値による判定ではありません。
- `strata_control.offline.child_environment()` にも環境全体のコピーと offline 用の変数設定・削除がありますが、Strata の本番コードからの呼び出しは確認できませんでした。エンジン起動経路で使われるのは `serve/server.py` の `child_env()` です（同 helper の定義: `strata_control/offline.py:122-136`）。

## 実行時の詳細

管理 runtime は親の `os.environ` をコピーして serve プロセスを起動するため、その段階では `HTTP_PROXY` を変更しません（`strata_control/runtime.py:854-877`）。serve プロセスの `child_env()` も最初に `os.environ` をコピーします。そこへ設定ファイルの `env` を適用し、offline が有効なら `OFFLINE_ENV` を最後に適用します。これにより offline 時は設定ファイルが `HTTP_PROXY` を再設定しても空文字が優先されます（`serve/server.py:3747-3777`）。replica / split 起動でも同じ処理が各エンジン環境に適用されます（`serve/server.py:8688-8710,8757-8777`）。

`OFFLINE_ENV` モジュールの import に失敗した場合の fallback は `STRATA_OFFLINE`、`HF_HUB_OFFLINE`、`TRANSFORMERS_OFFLINE` のみを設定し、`HTTP_PROXY` は空にしません（`serve/server.py:3768-3777`）。通常の環境でモジュールが利用可能な場合は `OFFLINE_ENV` 全体が適用されます。

`strata_control.loopback.urlopen()` はモジュール読み込み時に空の `ProxyHandler` を渡した opener を作成し、loopback URL に限ってその opener を使用します。Strata のコード上、この helper が渡された `HTTP_PROXY` の値を再評価する処理や、同変数について専用のログ・終了・失敗経路はありません（`strata_control/loopback.py:13-28`）。

## 根拠

- `strata_control/offline.py:47-60`: offline 子環境の変数一覧。`HTTP_PROXY` の設定値は空文字。
- `serve/server.py:3747-3777`: 子環境作成、環境設定の適用順、offline 時の上書きと import fallback。
- `serve/server.py:9000-9001,9173-9194,9274-9279`: CLI フラグ、offline の事前拒否、通常・replica・split エンジンへの環境受け渡し。
- `strata_cli/cli.py:745-765,802-803`: CLI / profile / run config の優先順位とサーバー引数への転送。
- `strata_control/runtime.py:854-877`: 管理 runtime が親環境を serve 子プロセスへコピーする箇所。
- `strata_control/loopback.py:13-28`: loopback 通信で空の proxy handler を用いる helper。
