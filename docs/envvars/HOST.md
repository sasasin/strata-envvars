# `HOST`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`HOST` は現行 Docker イメージのサーバー bind address を設定しない。Docker entrypoint は旧イメージ由来の設定名として `HOST` を検査し、値が空でなければ「旧イメージの設定であり、ここでは無視する」という警告を stderr に出す。現在のコンテナ起動で listen address を設定する用途には使えない（`docker/entrypoint.sh:80-83,170-170`）。

## 値と判定

| 環境の状態 | entrypoint の判定 | 結果 |
| --- | --- | --- |
| 未設定 | `eval "v=\${$legacy:-}"` が空値にする | 警告なし |
| 空文字 | `:-` により空値になる | 警告なし |
| 空でない任意の文字列 | `[ -n "$v" ]` が真 | `[!] HOST is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` を stderr に出す |

値の形式検証、アドレス変換、範囲制限はない。空かどうかだけを調べ、値自体は起動設定に渡さない（`docker/entrypoint.sh:80-83`）。

## 有効になる条件

この検査は Docker entrypoint の通常起動経路で実行される。引数が `run` または `serve` の場合、あるいは引数なしの場合は後続の初期化へ進む。先頭引数がそれ以外（例: `sh` や `strata ...`）なら entrypoint は先に `exec` するため、この警告ループには到達しない（`docker/entrypoint.sh:53-56,80-83`）。

通常のホストアプリ `apps/host/server/index.mjs` は bind address を `process.env.STRATA_BIND ?? '127.0.0.1'` から決めて `serving.init` と `server.listen` に渡す。ここで `HOST` は参照されない。Docker entrypoint は標準起動時に `strata launch --no-tui --access lan --port "$PORT" ...` を組み立てており、旧 `HOST` 値をこの引数列へ転送しない（`apps/host/server/index.mjs:101-102,244,2285`; `docker/entrypoint.sh:170`）。

## 実行時の詳細

警告ループは `/data` の準備後、コンテナ起動時に一度実行される。`warn` は `[!] ` を付けた一行を標準エラーへ出力し、処理は継続する。従って `HOST` が設定されていても、それ自体では終了や起動拒否にならず、bind address にも影響しない（`docker/entrypoint.sh:37-39,58,80-83`）。

この調査では `HOST` を読む Strata 所有コードとして上記 entrypoint の動的参照を確認した。`apps/host/server/index.mjs` の `HOST` はローカル変数であり、環境変数名ではない。なお同ファイルの bind 設定名は `STRATA_BIND` である。

## 根拠

- `docker/entrypoint.sh:53-56` — 一部のサブコマンドは警告処理より前に `exec` される。
- `docker/entrypoint.sh:37-39,80-83` — `HOST` を含む旧設定名を動的に環境から取得し、空でない場合に stderr 警告を出す。
- `docker/entrypoint.sh:170` — 標準起動コマンドに `HOST` を転送しない。
- `apps/host/server/index.mjs:101-102,244,2285` — ホストアプリの bind address は `STRATA_BIND` 由来のローカル定数 `HOST` から設定される。
