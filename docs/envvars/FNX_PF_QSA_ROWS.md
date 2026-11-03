# `FNX_PF_QSA_ROWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`src/split` の prefill で QSA の block selection にまとめる行数を指定します。既定値は 256 行です。値は prompt path の scratch 領域サイズにも使われます。通常の Strata engine 全体の設定ではなく、独立した `strata-split` エンジンの設定です。同エンジンはビルド時 opt-in で、Linux CUDA または HIP 向けです（`src/split/CMakeLists.txt:1-7,92-106`）。

## 値と判定

| 環境値 | 結果 |
|---|---|
| 未設定 | `qsa_pf_rows` は 256 のまま |
| 空文字 | 無効値として例外 |
| 数値文字列 | base 10 の `strtol` で変換。変換でき、文字列末尾まで消費され、値が `MAXT` 以上かつ `MAXT` の倍数なら採用 |
| 無効値 | 例外 `FNX_PF_QSA_ROWS: a positive multiple of 16, not '<値>'` |

このビルドの `MAXT` は 16（`src/split/src/model.hpp:43`）。したがって `16`, `32`, `256` は条件を満たし、`0`, `15`, `17`, `-16`, `16x`, 空文字は拒否されます。`strtol` の base は 10 で、先頭空白や `+` は変換関数が受け付けますが、変換後に未消費文字が残れば拒否されます。`errno` は確認せず、`long` 値を検証した後 `int` にキャストします。`int` に収まる上限の検査はありません（`src/split/src/prefill.cu:667-674`）。

## 有効になる条件

- `strata-split` の prompt prefill で QSA の block selection を行う経路で使われます。通常の decode 行選択には使われません（`src/split/src/prefill.cu:1214-1229`）。
- `FNX_PF_ATTN_DEC` が無効なら、この値が `AR`（QSA selection の行グループ幅）になります。有効なら `AR = attn_rows()` となり、block selection のグループ幅にはこの値を使いません。ただし `FNX_PF_QSA_ROWS` の読み取りと検証、ならびに scratch サイズ計算はそのまま行われます（`src/split/src/prefill.cu:667-674,768,1219-1226`）。
- `FNX_PF_QSA_ROWS` 自体に CLI 引数や別設定による優先順位・fallback はありません。未設定時だけ既定値 256 です。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が呼ばれ、各カード用の `attn_set` で読み取ります。`attn_set` は arena の大きさを測る dry pass と実際の領域割り当て pass の両方で実行されるため、値はカードごとにその両 pass で評価されます。static cache はありません。値は `qsa_pf_rows` に保存され、score scratch は `max(attn_rows(), qsa_pf_rows) * (max_ctx_ / 4)` 個の float で確保されます（`src/split/src/engine.cu:274-275`; `src/split/src/prefill.cu:625-627,658-675,690-705`）。

prefill の各 QSA layer で indexer の出力から `qsa_index` を実行した後、`AR` 行ずつ `qsa_select` を呼びます。`FNX_PF_ATTN_DEC` が無効な場合、`AR` は本変数の値です。ループの各グループでは先頭行に対応する制御情報と行数 `Tg` を渡します。有効な selection 値が変えるのはこの grouping と scratch 容量です（`src/split/src/prefill.cu:1214-1229`）。

設定値が不正なら `attn_set` が `std::runtime_error` を投げ、Engine 構築は失敗します。`fnx_run` の実行経路では最上位 catch が stderr に `fnx_run: <例外文>` を出し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 根拠

- 変数の読み取り、変換、検証、既定値の反映、scratch 確保: `src/split/src/prefill.cu:373,625-675`
- Engine 構築から prefill buffer 割り当てへの呼び出し: `src/split/src/engine.cu:274-275`
- `FNX_PF_ATTN_DEC` による grouping 分岐と `qsa_select`: `src/split/src/prefill.cu:768,1214-1229`
- `MAXT=16`: `src/split/src/model.hpp:43`
- `strata-split` の対象 backend と opt-in build: `src/split/CMakeLists.txt:1-7,92-106`
