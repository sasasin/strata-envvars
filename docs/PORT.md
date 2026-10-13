# `PORT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有のソースコードで、Docker entrypoint、セットアップ、HTTP サーバーの起動経路を含む。

## 役割

Linux コンテナの HTTP API サーバーが listen するポートを指定する。Strata の Python サーバーが `PORT` 環境変数を直接読む実装はなく、`docker-entrypoint.sh` が環境変数を `setup.py` の `--port` 引数に渡す。Dockerfile の health check も `PORT` を使って `/health` を確認する。

## 値と判定

entrypoint はシェルの `${PORT:-8080}` を使う。このため環境変数が未設定または空文字なら `8080` に置き換わり、空でない値はそのまま `--port` に渡される。

| `PORT` | entrypoint が渡す値 | 結果 |
|---|---:|---|
| 未設定 | `8080` | 既定ポート |
| 空文字 | `8080` | 既定ポート |
| 整数として読める文字列 | その文字列 | `setup.py` の argparse が `int` に変換し、起動時に指定ポートを使う |
| 整数に変換できない文字列 | その文字列 | argparse の引数エラーで該当する `setup.py` が終了する |
| `0` | `0` | setup.py 内の `a.port or ...` で偽と判定され、初回セットアップでは `8080`、既存モデルの起動では保存済み config のポート（なければ `8080`）が使われる |

Strata 側でポート範囲を検査・clamp する処理は確認できない。負数や整数として受理される範囲外の値を指定した場合の bind エラーの詳細は、ここで調べた Strata のコードだけからは特定できない。

## 有効になる条件

- Docker イメージの entrypoint が起動する経路で適用される。entrypoint は毎回 `--port "$PORT"` を `setup.py` に渡すため、既存モデルの config に保存済みの値より起動時の `PORT` が優先される。
- 初回セットアップでは `PORT` が `--setup` に渡され、setup.py が生成する config の `port` に記録される。その直後の起動でも同じ `PORT` が渡される。
- `PORT=0` は truthy な値ではないため、setup.py の選択ロジックで既定値または既存 config の値に置き換わる。
- `HOST` は別の環境変数である。初回セットアップ時には host として設定されるが、`PORT` の値判定には関与しない。
- Dockerfile の `EXPOSE 8080` は固定のまま。`PORT` を変えても Docker のポート公開設定は変わらないため、コンテナ内ポートに合わせた `-p host_port:container_port` の指定が必要になる。

## 実行時の詳細

entrypoint は初回（または `REINSTALL=1`）の setup コマンドに `--port "$PORT" --no-start` を渡して config を作成し、その後の起動コマンドにも `--port "$PORT"` を渡す。setup.py は `--port` を `type=int` として解析し、既存 config を使う起動ではこの引数を `start()` に渡す。`start()` は `serve/server.py` を `--port` 付きで起動する。サーバーはその整数を `Server((host, port), ...)` に渡し、ready ログにも同じポートを表示する。

Dockerfile の HEALTHCHECK は entrypoint とは別に、`http://127.0.0.1:${PORT:-8080}/health` を curl する。未設定または空文字の場合はこちらも `8080` を確認する。ポートを変更する場合は health check の接続先とコンテナのポート公開先が一致するように設定する。

## 根拠

- `docker-entrypoint.sh:19-35`: コンテナ用の既定値を `${VAR:-default}` で設定し、`PORT` は `8080` を既定とする。
- `docker-entrypoint.sh:76-87,102-106`: 初回 setup と通常起動の両方で `PORT` を `--port` に渡す。
- `Dockerfile:25-28,107-108,114-117`: `PORT` を entrypoint が読む設定として列挙し、`EXPOSE` は `8080` 固定、health check は `PORT` を使う。
- `setup.py:4851,4979,4995-4996,5019-5028`: `--port` は `type=int`。セットアップ済み config からポートを引き継ぐ場合があり、ポート値は `a.port or 8080` で選ばれ、起動時は引数が `start()` に渡る。
- `setup.py:4314-4343,5733-5735`: `start()` は引数または config のポートをサーバーの `--port` に設定し、新規 config に `port` を記録する。
- `serve/server.py:6047-6052,6312,6570-6576`: サーバーは integer の `--port` を `Server` に渡し、ready URL を表示する。サーバー自身による `PORT` の直接読み取りはない。
- `docs/INSTALL.md:100-111,126-128`: Docker の既定起動例、config に記録される設定、既定の `0.0.0.0:8080` を説明する。Dockerfile とソースの既定値に食い違いは見つからなかった。
