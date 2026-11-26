# `PORT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`PORT` は Strata の通常のエンジンやホストアプリ本体が読む設定ではなく、Docker イメージの起動スクリプトがコンテナ内の待受ポートを受け取り、`strata launch --port` に渡す変数である。Docker 起動時には同じポートをヘルスチェックとコンテナ内 `strata` ラッパーの接続先にも使う。Dockerfile の既定値は `8080`。`tools/docker/entrypoint.sh` は launch の `--port` を常に明示するため、保存済み preset のポートより `PORT` が優先される（`tools/docker/Dockerfile:107-117`、`tools/docker/entrypoint.sh:49-50,184-185`、`terminal/strata_cli/launch/cmd.py:215-220,278-287`）。

別用途として、開発・デモ用の2つのローカル HTTP プロキシも同名を読み、それぞれの listen ポートに使う。これらは Strata サーバーの待受設定ではない（`app/host/scripts/slow-proxy.mjs:2-4,9-23`、`app/host/scripts/chat-growth-proxy.mjs:1-3,9-26`）。

Strata のホストアプリ本体は `PORT` ではなく `STRATA_PORT` を読む。したがって `PORT` を設定しても、そのホストアプリのポートは変わらない（`app/host/server/index.mjs:109-110,2563-2570`）。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 設定値の扱い |
|---|---|---|---|
| Docker entrypoint | `8080` | `8080`（シェルの `${PORT:-8080}` は未設定または null/空を既定値にする） | 文字列をそのまま `--port` に渡す。launch CLI が `int()` 変換し、1〜65535 の範囲を受理する。 |
| Docker healthcheck / `strata` ラッパー | `8080` | `8080` | シェル展開した文字列を URL のポート部分に使う。ここでは数値範囲検査をしない。ラッパーでは非空の `STRATA_URL` が設定されていればそちらが優先。 |
| `slow-proxy.mjs` | `18900` | `0`（`Number("")`） | `Number()` で数値化し、`127.0.0.1` の `server.listen` に渡す。 |
| `chat-growth-proxy.mjs` | `18790` | `0`（`Number("")`） | `Number()` で数値化し、`127.0.0.1` の `server.listen` に渡す。 |

Docker の launch CLI は Python `int()` で変換する。`8080` などの整数で `1` と `65535` を含む範囲が受理され、`0`、負数、`65536` 以上は範囲外として拒否される。整数に変換できない文字列も拒否される。たとえば `PORT=0` や `PORT=abc` は既定値へ戻らず、launch の引数エラーになる。CLI が出す文言は範囲外の場合 `port <値> does not exist. Use a number from 1 to 65535, for example 8080.`、整数変換失敗の場合 `'<値>' is not a port number. Use a number from 1 to 65535, for example 8080.`（`terminal/strata_cli/launch/cmd.py:53-60,136`）。

プロキシ側は空文字を既定値に置き換えない。空文字は数値 `0` になり、非数値文字列は `NaN` になる。Strata のコードは追加の検証や fallback をせず、その結果を `server.listen` に渡す（`app/host/scripts/slow-proxy.mjs:9-23`、`app/host/scripts/chat-growth-proxy.mjs:3,9-26`）。

## 有効になる条件

- Docker entrypoint の通常起動経路で有効。`docker run IMAGE strata ...` や `docker run IMAGE sh` のように別コマンドを指定した場合は、entrypoint は早期に `exec` し、launch のポート設定を行わない（`tools/docker/entrypoint.sh:68-71`）。
- entrypoint が設定する `PORT` は `strata launch --port` の明示値となり、Docker の preset に保存されたポートを上書きする。コンテナ外から接続するためのホスト側ポート公開・転送は別途コンテナランタイムの指定であり、この変数はコンテナ内ポートを選ぶ（`tools/docker/entrypoint.sh:23,184-185`）。
- Docker healthcheck はコンテナ内の `127.0.0.1:<PORT>/v1/models` を確認する。HTTP 応答があり、JSON の `data` が空でないときだけ終了コード `0`。起動中、接続失敗、応答失敗、モデル一覧が空の場合は終了コード `1` となり、例外時は `not healthy: <例外>` を stderr に出す（`tools/docker/healthcheck.sh:2-18`）。
- `strata` ラッパーは `STRATA_URL` が未設定または空のときだけ `PORT` を既定 URL `http://127.0.0.1:<PORT>` に反映する。非空の `STRATA_URL` があれば `PORT` は接続先を変えない（`tools/docker/strata-wrapper.sh:4-10`）。
- 2つの開発用プロキシはそれぞれ起動時に値を読み、loopback の listen ポートを決める。モデルプロキシは `TARGET`（既定 `http://127.0.0.1:18797`）へ転送し、チャット成長デモは `UP`（既定 `18791`）へ通常リクエストを転送する。どちらも GPU backend やモデルの状態を条件にしない（`app/host/scripts/slow-proxy.mjs:9-23`、`app/host/scripts/chat-growth-proxy.mjs:3,9-26`）。

## 実行時の詳細

Docker イメージは `PORT=8080` を環境既定値として設定する。entrypoint は起動時に `${PORT:-8080}` を一度展開し、通常起動ではその値を `strata launch --no-tui --access lan --port "$PORT"` に渡す。CLI は `--port` を整数に変換・検査し、プリセットの設定を読み込んだ後にコマンドラインの `a.port` を適用するため、この経路では環境値が保存済みポートに優先する。`PORT` 自体を起動後に変更しても、起動済みサーバーの待受ポートは変わらない（`tools/docker/Dockerfile:107-117`、`tools/docker/entrypoint.sh:49-50,184-185`、`terminal/strata_cli/launch/cmd.py:215-220,286-287`）。

ヘルスチェックは実行のたびにそのプロセスの `PORT` を URL に展開する。コンテナ内 `strata` ラッパーも起動ごとに URL を組み立てて `STRATA_URL` として子の Terminal に export する。開発用プロキシ2つは Node.js 起動時、モジュール評価時に `PORT` を `Number()` で一度読み、それぞれのサーバーに渡す（`tools/docker/healthcheck.sh:4-18`、`tools/docker/strata-wrapper.sh:5-10`、`app/host/scripts/slow-proxy.mjs:9-23`、`app/host/scripts/chat-growth-proxy.mjs:3,26`）。

## ログと測定値

Docker entrypoint は起動後に `Serving on port $PORT. Watch it: ...` を stdout に出す。launch が失敗した場合は launch の終了コードを受け取り、phase を `failed` にして `strata launch stopped with code <rc> (the lines above say why). ...` を stderr に出して終了する（`tools/docker/entrypoint.sh:305-316,326-327`）。ヘルスチェックの成功・失敗判定と例外ログは前節のとおり。プロキシは listen 完了時に `slow model on <port> ...` または `proxy on <port>` を stdout に出す（`app/host/scripts/slow-proxy.mjs:23`、`app/host/scripts/chat-growth-proxy.mjs:26`）。測定値の記載はない。

## 根拠

- Docker の既定値・entrypoint の解決と引き渡し: `tools/docker/Dockerfile:107-117`、`tools/docker/Dockerfile.src:147-151`、`tools/docker/entrypoint.sh:23,49-50,68-71,184-185,305-327`。
- CLI の parse、値域、preset と引数の優先順位: `terminal/strata_cli/launch/cmd.py:53-60,136,215-220,286-287`。
- healthcheck とコンテナ内ラッパー: `tools/docker/healthcheck.sh:2-18`、`tools/docker/strata-wrapper.sh:4-10`。
- 開発用プロキシ: `app/host/scripts/slow-proxy.mjs:2-4,9-23`、`app/host/scripts/chat-growth-proxy.mjs:1-3,9-26`。
- ホストアプリ本体は別名を使用: `app/host/server/index.mjs:109-110,2563-2570`。
