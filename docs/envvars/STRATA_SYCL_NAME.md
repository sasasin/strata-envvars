# `STRATA_SYCL_NAME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`sycl/serve/strata-sycl.sh` が起動する Docker コンテナの名前を指定します。これは SYCL エンジンが読む設定ではなく、serve の `exe` として使う Strata 所有のシェルラッパーの設定です。調査対象リポジトリ内の候補名への全参照はこのラッパーのコメントと読み取りだけで、エンジン本体の読み取りはありません（`sycl/serve/strata-sycl.sh:9,21`）。

## 値と判定

| 環境値 | ラッパーが使う値 |
|---|---|
| 未設定 | `strata-sycl-serve` |
| 空文字 | `strata-sycl-serve` |
| 非空文字列 | その文字列をそのまま使用 |

`${STRATA_SYCL_NAME:-strata-sycl-serve}` という Bash の既定値展開です。ラッパーは値の形式・文字種・長さを検証せず、変換もしません。値を `docker rm -f` と `docker run --name` の引数に渡します。したがって名前として受理されるかは Docker 側の処理であり、Strata は独自の無効値 fallback や警告を設けていません（`sycl/serve/strata-sycl.sh:21-22,42`）。

## 有効になる条件

- `serve/server.py --engine strata` の設定で `exe` に `sycl/serve/strata-sycl.sh` を指定し、そのラッパーが起動される場合にだけ使われます。Intel 用構成の説明と設定例もこの起動方法を示しています（`docs/INTEL.md:118-127`）。
- serve の設定に `env` があると `child_env()` がサーバー環境を複製した後に設定値を文字列化して上書きします。そのため設定の `env.STRATA_SYCL_NAME` がサーバープロセスから継承した同名値より優先されます。専用 CLI 引数による設定や、エンジン本体での読み取りはありません（`serve/server.py:3747-3760,9191-9194,9277-9279`）。
- ラッパーは `STRATA_SYCL_*` をコンテナへ転送する環境変数群から除外しています。`STRATA_SYCL_NAME` はコンテナ内のエンジンに渡されず、ラッパー自身のコンテナ名選択に使われます（`sycl/serve/strata-sycl.sh:29-38`）。

## 実行時の詳細

ラッパーの各起動時に環境変数を一度展開し、その値で同名の残存コンテナに `docker rm -f` を試みます。この削除コマンドの失敗は出力を捨てて無視し、その後 `docker run --name "$name"` を実行します。シェルは `set -euo pipefail` で動作するため、後者が失敗すればラッパーは失敗終了します。値はプロセス内に cache されず、起動ごとに環境から評価されます（`sycl/serve/strata-sycl.sh:17,21-22,42`）。

serve は設定済み環境をラッパープロセスへ渡し、標準エラーをエンジンログへ接続します（`serve/server.py:1077-1079`）。ラッパーがコンテナ起動に失敗して `READY` を出さず終了した場合、serve は子プロセス終了として扱い、ログ末尾などを含む `EngineDied` を生成します（`serve/server.py:1097-1111,1143-1153`）。Docker が特定の値を拒否する条件やエラー文言は Docker 側の挙動なので、ここでは Strata の挙動として規定しません。

## 根拠

- `sycl/serve/strata-sycl.sh:9,21-22,42`: 変数の説明、未設定・空文字時の既定値、先行する削除試行、コンテナ名引数。
- `sycl/serve/strata-sycl.sh:29-38`: `STRATA_SYCL_*` の転送除外。
- `serve/server.py:3747-3760,9191-9194,9277-9279`: 設定 `env` の反映とラッパーへの環境引き渡し。
- `serve/server.py:1077-1079,1097-1111,1143-1153`: ラッパー起動、READY を受けない終了の処理、起動失敗の観測経路。
- `docs/INTEL.md:118-127`: SYCL サーバーでラッパーを使う構成例。
