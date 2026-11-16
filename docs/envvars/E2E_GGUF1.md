# `E2E_GGUF1`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

同梱の `apps/host/scripts/agent-lost-e2e.mjs` が、自前のモデルサーバーを起動する場合に `--native` へ渡す GGUF shard 1 のパスを指定する E2E 用環境変数。通常の Strata エンジン起動時にエンジン自身が読む設定ではない。`E2E_BASE_URL` が非空なら既存サーバーを使うため、この変数は読み取られず、モデルパスにも使われない（`apps/host/scripts/agent-lost-e2e.mjs:30,34,58-60`）。

## 値と判定

`env(name, fallback)` は `process.env[name] ?? fallback` を返す。未設定 (`undefined`) のみ既定値に置き換わり、明示的な空文字はそのまま使われる。値を boolean や数値として parse せず、パス文字列として `existsSync` に渡す。したがって `1`、`true`、`0anything` も文字列どおりのパスであり、そこに存在するパスなら通り、存在しなければ失敗する。空白除去、大文字小文字変換、パス正規化、通常ファイルかどうかの検査はこの箇所では行わない（`apps/host/scripts/agent-lost-e2e.mjs:30,60,66`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `E2E_BASE_URL` が空または未設定で、スクリプトが自前サーバーを起動 | `join(HOME, 'models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf')` を既定値として使う | `existsSync` が真となるパス文字列。例: `1`（カレントディレクトリに `1` というパスが存在する場合） | 空文字、`0`、`true` など、それぞれに対応するパスが存在しない場合 |
| `E2E_BASE_URL` が非空 | 読み取りなし | 該当なし | 該当なし |

`HOME` 自体も `process.env.HOME ?? ''` で取得されるため、`HOME` が未設定なら上記の既定値は `join('', 'models/...')` となる。既定のモデルパスは `E2E_GGUF1` が設定されていない場合に限って使われる（同 `:31,60`）。

## 有効になる条件

- `E2E_BASE_URL` が空または未設定であること。非空の場合は既存サーバーを使い、自前サーバー設定ブロック全体を通らない（`apps/host/scripts/agent-lost-e2e.mjs:34,58`）。
- 自前サーバー起動経路では、選ばれたパスが `existsSync` で存在すると判定されること。存在しない場合は `missing: <パス>` を stderr に出して終了コード `2` で終了する（同 `:66`）。
- スクリプトが必要とする `STRATA_HARNESS_DIR` も設定されていること。未設定なら `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード `2` となるが、これは `E2E_GGUF1` 固有の判定ではない（同 `:44`）。
- この変数に backend、OS、build macro、モデル種別による分岐はない。スクリプトが書く設定では選択パスを `--native` の値にし、server 起動時に `serve/server.py` が `cfg["args"]` から engine 引数を組み立てる（同 `:67-72`; `serve/server.py:3882-3888,9521-9522`）。

## 実行時の詳細

`E2E_GGUF1` はスクリプトの自前サーバー設定ブロック内で一度取得され、`g1` に保存される。各リクエストや turn ごとの再読込、キャッシュ更新の仕組みはない。取得後に `existsSync` で存在確認し、`server.json` の `args` 配列へ `['--native', g1]` として書き込む。スクリプトはその設定ファイルを `serve/server.py --engine strata --config ...` に渡し、Python server は設定の `args` を engine 引数に使う（`apps/host/scripts/agent-lost-e2e.mjs:60,66-78`; `serve/server.py:3882-3888,9521-9522`）。

同じ引数列には `E2E_PACK` 由来の `--pack` と `E2E_GGUF2` 由来の `--ple-gguf` も含まれるが、これらが `E2E_GGUF1` の値を上書きする処理はこのスクリプトにはない。`E2E_ENGINE_ARGS` は空白で分割して後ろへ追加される（同 `:59-72`）。この文書の対象コードから確認できるのはパスの選択・存在確認・設定ファイルへの引き渡しまでであり、GGUF の読み込みや外部ライブラリ側の解釈は Strata のこの環境変数の挙動として扱わない。

## ログと測定値

選択したパスが存在しないときは stderr に `missing: <パス>` を出して終了コード `2` となる。存在する場合、`E2E_GGUF1` の値そのものについて成功ログや理由ログは出さない。Strata の `docs/DETAILS.md` にこの変数または `agent-lost-e2e.mjs` の測定値に該当する記述は見つからなかった。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:30-44` — env helper、`HOME`、既存サーバー判定、Harness 必須判定。
- `apps/host/scripts/agent-lost-e2e.mjs:58-78` — E2E_GGUF1 の既定値、存在確認、`--native` への設定と server 起動。
- `serve/server.py:3882-3888,9521-9522` — config `args` の engine 引数化と engine 起動への引き渡し。
