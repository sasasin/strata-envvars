# `E2E_GGUF2`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

これは通常の Strata エンジン設定ではなく、Strata 同梱の `apps/host/scripts/agent-lost-e2e.mjs` が使う E2E 起動用の環境変数である。既存サーバーを指定せずスクリプトがサーバーを起動するとき、値を `--ple-gguf` の引数に渡し、指定の第 2 GGUF shard を設定する。エンジン側では同 CLI オプションが PLE テーブルの GGUF パスとして格納される（`apps/host/scripts/agent-lost-e2e.mjs:58-71`、`sycl/src/program/generate.cpp:1885`）。

## 値と判定

スクリプトの共通 helper は `process.env[name] ?? fallback` を返す。したがって未設定時のみ既定パスになり、空文字を含む設定済み文字列はそのまま使われる。数値変換や文字列形式の検査はなく、`existsSync` でパスが存在するかを確認する。ファイル種別や拡張子は検査しない（`apps/host/scripts/agent-lost-e2e.mjs:29-31,58-66`）。

| 条件 | unset | 設定時に有効になる値 | 無効・失敗になる値 |
|---|---|---|---|
| `E2E_BASE_URL` が空（既存サーバーを使わず起動） | `HOME/models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` | `existsSync` が存在を確認できる任意のパス文字列。値は `--ple-gguf` に渡る | 空文字や存在しないパスは `missing: <値>` を stderr に出して終了コード 2。存在しても通常ファイルでないパスなど、後段の engine が受け付けない場合の扱いは `E2E_GGUF2` 自体の判定ではない |
| `E2E_BASE_URL` が空でない（既存サーバーを使用） | 読み取られず適用なし | なし | 値による検査・失敗なし |

大文字小文字や空白の正規化、全体 parse、範囲・負値判定はない。値中の空白もパス文字列の一部として扱われ、引数配列の一要素として渡される。`E2E_ENGINE_ARGS` があれば別途その文字列を分割した引数が後ろに追加されるが、重複オプション時の優先順位はこのスクリプトでは定めていない（`apps/host/scripts/agent-lost-e2e.mjs:66-71`）。

## 有効になる条件

- `apps/host/scripts/agent-lost-e2e.mjs` を実行し、`E2E_BASE_URL` が空であること。非空ならスクリプトは既存サーバーに接続する経路を選び、この変数を参照しない（`apps/host/scripts/agent-lost-e2e.mjs:34,58,86`）。
- 自動起動経路では指定または既定の `E2E_GGUF2` パスが存在すること。存在しなければサーバー起動前に終了コード 2 となる（`apps/host/scripts/agent-lost-e2e.mjs:66-67`）。
- 自動起動経路でエンジンが `--ple-gguf` オプションを受け付けること。`generate.cpp` は同オプションの次の引数を `o.ple_gguf` に保存する（`sycl/src/program/generate.cpp:1885`）。

## 実行時の詳細

環境値はスクリプト実行中、既存サーバーかを判定した後の自動起動ブロックで一度 `g2` に読み込まれる。未設定時は `HOME` 配下の既定 shard パスを組み立てる。値は `pack`、`g1`、`mtp`、engine 実行ファイルとともに `existsSync` で確認され、成功すれば生成する `server.json` の `args` に `--ple-gguf`, `g2` として追加される。その後 `serve/server.py` が `--config` でこの設定を受け取り、Strata engine 起動に使う（`apps/host/scripts/agent-lost-e2e.mjs:29-31,58-79`; `serve/server.py:3882-3889,9514-9522`）。プロセス起動後に親環境の値を変更して反映する仕組みはなく、`E2E_BASE_URL` 経由では子 engine を起動しない。

エンジン側で `--native` が指定され、`--ple-gguf` が空なら自動探索を試み、それでも PLE shard が決まらない場合は `strata generate: --native requires --ple-gguf (the PLE key is native too), and no shard of the model holds per_layer_token_embd.weight` を stderr に出して終了コード 2 にする。今回のスクリプトは非空パスを `--ple-gguf` に渡すため、この未指定時の探索・失敗条件を直接は通らない（`sycl/src/program/generate.cpp:2513-2527`）。

## ログと測定値

パスの存在確認に失敗した場合は `missing: <パス>` を stderr に出して終了コード 2 となる（`apps/host/scripts/agent-lost-e2e.mjs:66`）。起動したサーバーが ready にならない場合、スクリプトは `the engine did not become ready` を stderr に出して終了コード 4 とする（`apps/host/scripts/agent-lost-e2e.mjs:87-93`）。これはこの環境変数だけを原因とする診断ではない。測定値の記載はない。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:29-31,58-71,77-93` — env helper、条件付き読み取り、既定パス、存在確認、engine 引数への設定、起動後の失敗表示。
- `serve/server.py:3882-3892,9514-9522` — config の引数を engine 起動引数として扱う経路。
- `sycl/src/program/generate.cpp:1885,2513-2527` — `--ple-gguf` のパース、未指定時の探索とエラー。
