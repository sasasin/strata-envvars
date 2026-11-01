# `HTTPS_PROXY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリがこの変数を読む動作は対象外。

## 役割

Strata 自身が `HTTPS_PROXY` の値を読み取って通信先を決める実装は見つかりませんでした。Strata の Python サーバーは、`serve --offline` のときにエンジンなどの子プロセスへ渡す環境を作り、この名前を空文字で上書きします。オフラインでない起動では、親プロセスの値を子へ引き継ぎます。したがって、この変数に関する Strata の動作は子プロセス環境の転送・上書きです。

## 値と判定

Strata は値を parse・検証せず、`OFFLINE_ENV` の辞書値をそのまま設定します。

| 条件 | 子プロセスに渡す `HTTPS_PROXY` |
|---|---|
| `--offline` を指定 | 空文字 `""`。親環境で未設定、空、または値ありのいずれでも空文字に上書き |
| `--offline` なし、親環境に設定あり | 親の文字列を引き継ぐ。ただし設定の `env` に同名キーがあれば設定値が優先 |
| `--offline` なし、親環境に未設定 | 未設定のまま。ただし設定の `env` に同名キーがあればその値を設定 |

オフライン時は設定 `env` の同名キーよりも `OFFLINE_ENV` が優先されます。文字列の形式、大文字小文字、URLとしての妥当性について検査や変換はありません。小文字の `https_proxy` も同じ辞書で空文字に設定されます。

## 有効になる条件

- `serve` サーバーを起動し、CLI の `--offline` を指定したときに限り、サーバーが作る子プロセス環境で空文字への上書きが行われます。`--offline` は `argparse` の `store_true` オプションで、既定は無効です（`serve/server.py:9000-9001`）。
- `--offline` 起動では、MCP サーバーまたは `before_load` コマンドがプロファイルにある場合、起動前に `ap.error` で拒否します。また、ネットワーク画像など strict offline と両立しないプロファイル要件も拒否します（`serve/server.py:9172-9184`）。
- 対象は Strata engine、設定された画像 encoder、replica engine、split engine へ渡す環境です。設定が `env` に指定した値を通常起動では反映し、オフライン時はポリシー環境を最後に適用します（`serve/server.py:3747-3777, 3931-3946, 8704-8711, 8770-8777, 9191-9194, 9223-9224`）。
- `strata_control.offline` を import できない例外経路では、server は最低限の offline marker を設定しますが、`HTTPS_PROXY` を空にする処理は含まれません（`serve/server.py:3768-3777`）。通常のアプリ構成では同梱のポリシーモジュールを使います。

## 実行時の詳細

`child_env()` は呼び出し時に `os.environ` を辞書へコピーし、設定の `env` を反映した後、`offline=True` なら `OFFLINE_ENV` を適用します。作成された辞書を `StrataEngine` が `subprocess.Popen(..., env=env)` に渡します（`serve/server.py:3747-3777, 1017-1019, 1074-1079`）。replica / split では各 engine 用に `child_env()` を呼びます。画像 encoder は engine の環境を受け取り、GPU 可視性の指定がある場合だけその辞書を複製・調整するため、`HTTPS_PROXY` は保たれます（`serve/server.py:3931-3946, 8704-8711, 8770-8777, 9223-9224`）。

Strata は `HTTPS_PROXY` の値を起動後に再読込する cache を持ちません。サーバープロセスの環境を起動後に変えても、すでに起動済みの子の環境は変わりません。`StrataEngine` は起動時の引数と環境を `self.spawn` に保存して再起動にも使うため、同じ server プロセス内での engine 再起動もその保存済み環境を使います（`serve/server.py:1017-1019`）。設定内容の更新も起動済み子の環境には遡及しません。

ソース上、この名前について Strata のログ、警告、終了・失敗分岐はありません。オフラインモードの説明は `docs/TERMINAL.md:234` にあり、MCP・`before_load` とリモート画像を拒否すると記載されています。`strata_control/offline.py:17-20, 44-61` は子環境へ proxy 変数を設定する方針と辞書定義を記述しています。同ファイルの `child_environment()` は通常時に marker を除去する helper ですが、調査対象内での呼び出しはテストのみです。サーバーの本番経路は `serve/server.py:3747-3777` で独自に環境を構成します。外部ライブラリ等が空文字をどう解釈するかは本調査では扱いません。

## 根拠

- `strata_control/offline.py:44-61`: `HTTPS_PROXY` と `https_proxy` を空文字にした `OFFLINE_ENV` 定義。
- `strata_control/offline.py:122-136`: 共通 helper の親環境コピーと辞書更新。調査対象ではテストから呼ばれる。
- `serve/server.py:3747-3777`: 親環境・設定 `env`・offline policy の順に子環境を構成する処理と import fallback。
- `serve/server.py:9000-9001, 9172-9184`: CLI の opt-in と offline profile の事前拒否。
- `serve/server.py:1017-1019, 1074-1079`: engine の起動情報と `Popen` への環境受け渡し。
- `serve/server.py:8704-8711, 8770-8777, 9191-9194, 9223-9224`: replica / split / 通常 engine / vision encoder の環境構成と受け渡し。
- `serve/server.py:3931-3946`: vision encoder が engine 環境を引き継ぐ処理。
- `docs/TERMINAL.md:234`: `serve --offline` の利用者向け説明。
