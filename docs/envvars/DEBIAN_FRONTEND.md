# `DEBIAN_FRONTEND`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata の実行時設定としてこの名前を読む箇所は見つからない。サーバーの `child_env()` は親プロセスの環境全体を辞書へコピーして engine 子プロセスに渡すため、親環境に `DEBIAN_FRONTEND` があれば、その値も通常は一緒に渡る。Strata 自身は値を判定せず、この変数に応じて engine の処理を分岐しない（`terminal/serve/server.py:4007-4010,4027-4028,4037-4062`、engine 起動時の受け渡しは `terminal/serve/server.py:833-835`）。

ソース中の名前の直接参照は、CI の `apt-get install` に付けた一時的な環境値と Dockerfile の `ENV` 宣言である。これらはパッケージ導入用の設定であり、Strata のアプリケーションコードによる読み取りではない（`.github/workflows/backends.yml:74,104,137,141`、`tools/docker/Dockerfile:29,72`、`tools/docker/Dockerfile.src:33,113,128`、`engine/sycl/tools/Dockerfile:5`）。

## 値と判定

Strata は `DEBIAN_FRONTEND` というキーを指定して値を取得・parse しない。engine 用環境を作る際に `dict(os.environ)` で環境を複製し、`cfg["env"]` に同じキーがあれば `str()` にした設定値で上書きする（`terminal/serve/server.py:4010,4027-4028`）。そのため、この転送経路に限れば次のとおり。

| 条件 | unset | 設定時に転送される値 | 上書き・無効化 |
|---|---|---|---|
| サーバーの Strata engine 子プロセス | 親環境にキーがなければキーなし | 親環境の値を辞書コピーでそのまま引き継ぐ。空文字もキーが存在する値として残る | 設定の `env` に同名キーがあれば `str()` 変換後の値で上書き |

`1` / `0`、`true` / `false`、大文字小文字、空白、数値形式などを Strata は検証しない。Strata が値を無効と判断して fallback する規則もない。値の意味を子プロセスや外部プログラムがどう扱うかは、この Strata 側の転送処理からは断定できない。

## 有効になる条件

- サーバー実行で Strata engine 子プロセスを起動するとき、親プロセス環境にキーが存在すれば転送対象になる。通常の `--engine strata` 経路では `child_env()` の結果を engine 起動に渡す（`terminal/serve/server.py:9391-9394,833-835`）。
- 同じキーを設定の `env` に指定した場合は、その設定値が親プロセスから引き継いだ値より優先される（`terminal/serve/server.py:4027-4028`）。
- この処理に OS / backend による `DEBIAN_FRONTEND` 固有の条件はない。`child_env()` は GPU 可視性、オフライン設定、ライブラリ検索パス等の別キーを条件付きで変更するが、`DEBIAN_FRONTEND` を名前指定して変更する分岐はない（`terminal/serve/server.py:4011-4026,4037-4053`）。
- Dockerfile での宣言はコンテナのビルド／実行環境側に設定するもの（`tools/docker/Dockerfile:29,72`、`tools/docker/Dockerfile.src:33,113,128`）。それ自体は Strata の値判定を有効化しない。

## 実行時の詳細

`child_env()` が呼ばれるたびに、その時点の `os.environ` を辞書へコピーして子プロセス用環境を構成する。`quiet_crash_env()` と `arena_env()` は渡された辞書の特定キーだけを必要に応じて設定し、他のキーを除去しない（`terminal/serve/server.py:4010`、`terminal/strata_control/childenv.py:27-33,58-64`）。構成済み辞書は `StrataEngine` から `popen()` に渡される（`terminal/serve/server.py:833-835`）。よって起動済み子プロセスの環境は、その起動時に作られた辞書の値であり、親の環境変更を同じプロセスへ後から反映する Strata の処理はない。

## ログと測定値

`DEBIAN_FRONTEND` の値に関する専用ログ、警告、終了コード、fallback はない。engine の起動自体が `OSError` で失敗した場合は通常の起動失敗経路に入るが、ソース上でこの環境変数を原因として扱う処理はない（`terminal/serve/server.py:833-840`）。測定値は該当しない。

## 根拠

- `.github/workflows/backends.yml:74,104,137,141` — CI の `apt-get install` コマンドに `DEBIAN_FRONTEND=noninteractive` を付ける。
- `tools/docker/Dockerfile:29,72`、`tools/docker/Dockerfile.src:33,113,128` — Docker build stage に環境変数を宣言する。
- `engine/sycl/tools/Dockerfile:5` — SYCL 開発イメージの `apt-get install` に値を付ける。
- `terminal/serve/server.py:4007-4062,833-835,9391-9394` — server が engine 子プロセスの環境を作成し、起動時に渡す。
- `terminal/strata_control/childenv.py:27-33,58-64` — 環境辞書の helper は個別の別キーを処理し、他のキーを保つ。
