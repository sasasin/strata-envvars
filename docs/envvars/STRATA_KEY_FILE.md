# `STRATA_KEY_FILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

Docker image の entrypoint、healthcheck、`strata` wrapper が共有する API key ファイルのパスを指定します。entrypoint は `strata launch` が使うキーをこのパスへ保存し、healthcheck と wrapper は条件を満たすと同じファイルからキーを読みます。この変数を読む箇所は Docker 用 shell script に限られ、Strata の C++/Python アプリ本体が直接読む箇所はありません（`docker/entrypoint.sh:32,293-295`, `docker/healthcheck.sh:4-6`, `docker/strata-wrapper.sh:5-8`）。

## 値と判定

3 script すべてで `${STRATA_KEY_FILE:-/data/state/api-key}` と展開します。したがって未設定または空文字なら `/data/state/api-key`、空でない値ならその文字列をパスとして使います。値の形式・存在・権限を事前検証する共通処理や文字列変換はありません。相対パスもシェルにそのまま渡されます（`docker/entrypoint.sh:32`, `docker/healthcheck.sh:4`, `docker/strata-wrapper.sh:5`）。

この変数はキー入力元ではありません。entrypoint はまず `API_KEY` が空でなければそれを使い、そうでなければ `API_KEY_FILE` が指定されている場合にそのファイルから CR/LF を除いて読みます。どちらもなければ `strata launch` にキーを生成させます（`docker/entrypoint.sh:162-167,226,278-281`）。その後、成功した起動のキーを `STRATA_KEY_FILE` のパスに保存します（下記）。

## 有効になる条件

- entrypoint の通常の `run` / `serve` 起動経路では、起動処理後にキー保存先として使います。`docker run IMAGE strata ...` や別コマンドなど、通常起動以外の引数は先に `exec` されるため、キー保存処理には進みません（`docker/entrypoint.sh:53-56,293-295`）。
- Docker healthcheck は `API_KEY` が空の場合に限り、指定ファイルが読み取り可能ならその内容を Bearer key として `/v1/models` に送ります。`API_KEY` が空でない場合はファイルを読みません（`docker/healthcheck.sh:5-10`）。Dockerfile はこの script を healthcheck に登録しています（`docker/Dockerfile:128`）。
- `strata` wrapper は `STRATA_API_KEY` が空の場合に限り、指定ファイルが読み取り可能なら内容を `STRATA_API_KEY` に設定してから Terminal を起動します。既に `STRATA_API_KEY` が空でなければファイルを読みません（`docker/strata-wrapper.sh:5-10`）。この wrapper は image 内の `/usr/local/bin/strata` に置かれます（`docker/Dockerfile:88-89`）。

## 実行時の詳細

entrypoint は起動時に保存先を `KEY_FILE` shell 変数へ展開します。サーバー起動が成功した後、`umask 077` の subshell で `strata launch --show-key --preset "$PRESET"` の stdout をそのパスへリダイレクトし、stderr は捨てます。失敗は `|| true` で無視され、ファイルが存在しないか空なら削除します。保存に失敗した場合の専用警告や終了はありません。キーが未指定だった場合には、別途「Strata がキーを作成した」と stderr に警告しますが、保存成功を確認したメッセージではありません（`docker/entrypoint.sh:293-299`）。

healthcheck は各実行でパスとキーを評価します。読めるファイルがなく、かつ `API_KEY` も空ならキーなしで HTTP request を作ります。HTTP 応答が 200 かつ JSON の `data` が truthy の場合だけ exit 0、それ以外は exit 1 です。例外は stderr に `not healthy: ...` と出します（`docker/healthcheck.sh:4-17`）。wrapper も起動のたびにファイルを調べます。両 script ともファイル内容から末尾改行を除去するコマンド置換を使います（`cat` による wrapper 読み込みは `docker/strata-wrapper.sh:6-8`）。

## 根拠

- 全参照は `docker/entrypoint.sh:32`, `docker/healthcheck.sh:4`, `docker/strata-wrapper.sh:5`。`rg -n --hidden --glob '!.git/**' 'STRATA_KEY_FILE' .` で確認した完全一致参照はこの3箇所です。
- Docker image への組み込みは `docker/Dockerfile:87-89,128,133`。
- `docs/DOCKER.md:113-138,159-170` は `/data` volume 内の state と API key、および `API_KEY` / `API_KEY_FILE` を説明していますが、`STRATA_KEY_FILE` の変更可能性は記載していません。上記のパス指定と shell script の挙動は現行ソースから確認したものです。
