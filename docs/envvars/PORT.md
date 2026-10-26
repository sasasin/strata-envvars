# `PORT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata の Docker イメージに同梱される起動・補助スクリプト。

## 役割

Docker コンテナ内で Strata サーバーが待ち受けるポートを指定します。Docker の entrypoint はこの値を `strata launch --port` に渡し、healthcheck とコンテナ内の `strata` wrapper も接続先ポートとして使います。ホスト側に公開するポートは Docker の `-p` で別に指定します。

## 値と判定

| 状態 | entrypoint / healthcheck / wrapper の扱い |
|---|---|
| `PORT` 未設定 | `8080` |
| `PORT` が空文字 | `8080`（シェルの `${PORT:-8080}` による） |
| 空でない値 | 内容を変換・検証せず、entrypoint は `--port` の引数として渡す。healthcheck と wrapper は URL のポート部分に使う |

スクリプト側には数値 parse、範囲制限、別設定との優先順位判定はありません。非数値などを指定した場合の受理・エラーは `strata launch --port` 側に委ねられます。この調査では同梱スクリプトより先の CLI のポート引数 parse は確認できていません。

## 有効になる条件

- 通常の Docker 起動経路で entrypoint が既定の `launch` を開始するときに適用されます。コンテナへ `strata ...`、`sh` など別コマンドを渡した場合、entrypoint はそのコマンドを直接 `exec` するため、サーバー起動用の `PORT` 引数は構成しません。
- `docker/Dockerfile` は `PORT=8080` を環境変数の既定値として設定します。起動時に別の値を渡すとその値が使われます。
- `-p HOST_PORT:CONTAINER_PORT` の `CONTAINER_PORT` は `PORT` と一致させる必要があります。`PORT` を変えても Docker が公開ポートを自動で変更するわけではありません。
- コンテナ内 wrapper は `STRATA_URL` が未設定または空の場合に `http://127.0.0.1:${PORT:-8080}` を設定します。`STRATA_URL` が非空ならそちらを優先します。

## 実行時の詳細

entrypoint は起動時に `PORT="${PORT:-8080}"` を評価し、通常起動では `strata launch --no-tui --access lan --port "$PORT" ...` を組み立てて実行します。起動後の案内にも同じ値を表示します。環境変数をリクエストごとに再読する処理や、起動中にポートを変更する処理はこれらのスクリプトにはありません。

healthcheck は `http://127.0.0.1:${PORT:-8080}/v1/models` に最大4秒で HTTP GET し、HTTP 200 かつ応答 JSON の `data` が空でない場合に成功します。失敗時は `not healthy: ...` を標準エラーに出して終了コード1を返します。コンテナ内 wrapper は、既定の接続先 `STRATA_URL` に同じポートを使います。

## 根拠

- `docker/Dockerfile:104-114` — イメージ既定値 `PORT=8080` と `EXPOSE 8080`。
- `docker/entrypoint.sh:20,34,41-44,157-158,264-288` — 既定化、別コマンド経路、サーバー引数への受け渡し、起動案内。
- `docker/healthcheck.sh:1-17` — healthcheck の URL、判定と失敗時の出力。
- `docker/strata-wrapper.sh:1-10` — `STRATA_URL` が未指定の場合の接続先。
- `docs/DOCKER.md:115-129,167-169` — Docker 設定表と、コンテナ内ポートと公開ポートの説明。
