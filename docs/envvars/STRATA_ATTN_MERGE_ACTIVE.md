# `STRATA_ATTN_MERGE_ACTIVE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL 版の QSA attention で、各 query の選択幅に含まれる chunk だけを読む merge kernel を選ぶ。通常の merge kernel は `n_chunks` 全体を走査するが、この経路では `steps` に入った幅から必要な chunk 数を求め、そこまでだけを merge する。変わるのは merge の走査範囲であり、QSA の選択結果や chunk 計算そのものをこの変数が変更するコードはない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:629-685,1203-1227`）。

この実装は `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp` の `qsa_decode_attn_batch` にある。通常の CUDA/HIP 経路にはこの読み取りがなく、SYCL は `STRATA_ENABLE_SYCL` で選ぶ独立した実験的 backend である（`engine/CMakeLists.txt:23-33`; `engine/sycl/CMakeLists.txt:273-282`）。

## 値と判定

`merge_active_on` の関数内 `static` 初期化から `strata::bm_default_on` に渡し、helper は `std::getenv` の値が null でなく、かつ空文字列でないとき、先頭文字が `'0'` 以外なら ON とする。文字列全体の parse や大文字小文字・空白の正規化はない。未設定と空文字列はどちらも device の既定値へ進む（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:688-691`; `engine/sycl/include/strata/sycl_queue.hpp:193-200`）。

| 条件 | unset / 空文字 | ON になる例 | OFF になる例 |
|---|---|---|---|
| Battlemage device | ON | `1`, `true`, ` 1` | `0`, `0anything` |
| Battlemage 以外（Arc A-series を含む） | OFF | `1`, `true`, ` 1` | `0`, `0anything` |

空白で始まる非空値は先頭文字が `'0'` ではないため ON。`false`、`00`、`0anything` は先頭文字規則によりそれぞれ ON、OFF、OFF となる。空文字列は「明示 OFF」ではなく未設定と同じ device 既定値である。非空値なら device にかかわらず先頭文字で上書きする（`engine/sycl/include/strata/sycl_queue.hpp:196-200`）。

## 有効になる条件

- `STRATA_ENABLE_SYCL` による SYCL engine build を使い、`qsa_decode_attn_batch` の一般 chunk-plus-merge 経路に入ること。`qsa_chunk_down_supported(...) && kv_mode == 1 && pools.v_q` が成立すると別 kernel を起動して return し、この変数による merge 分岐を通らない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1015`）。
- `n_q` が 1〜8 であること。`n_q <= 0` は関数冒頭で return し、9 以上では設定が ON でも通常の `attn_merge_kernel` を使う（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1007,1207-1226`）。
- 対象 device が Battlemage でなければ、unset/空文字では OFF。値を `1` などにすれば device 既定に関係なく ON にできる（`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。
- `qsa_decode_attn_batch_rows` が直接まとめて処理する経路では、この変数を参照せず通常 merge を使う。row 関数が別設定により各 row を `qsa_decode_attn_batch(..., n_q=1, ...)` に委譲した場合は、その委譲先でこの判定が適用される（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1256-1299`）。`qsa_decode_attn_step` にもこの変数の読み取りはない。

## 実行時の詳細

`qsa_decode_attn_batch` はまず入力・geometry を検査し、続いて chunk-down 経路を判定する。一般経路では 64 cell 単位で chunk 数 `n_chunks = ceil(cap / 64)` を作り、chunk kernel が部分結果を計算する。その後 `merge_active_on(device) && n_q <= 8` なら active merge kernel、そうでなければ全 `n_chunks` を走査する通常 merge kernel を queue に投入する（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:31,1001-1026,1203-1227`）。

active merge は query ごとに `steps[z * kStepCount + kStepWidth]` を幅として読み、幅が 0 以下なら `reach=0`、正なら `ceil(width / 64)` を計算して `n_chunks` で上限を設ける。各 head の chunk 部分値をこの範囲だけ合成し、重み合計 `L` が正なら `acc / L`、そうでなければ出力を 0 にする。したがって、`width` が `cap` 相当以上なら全 chunk が対象となり、0 以下なら active merge の出力は 0 になる（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:631-685`）。

設定値は `merge_active_on` の関数内 `static const bool` に保存され、最初にこの関数が評価された時点の環境値と device 既定判定が以後の呼び出しに使われる。実行中に環境を変更しても再評価されない。初回呼び出しより前に設定する必要がある（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:688-691`）。

## ログと測定値

この変数の読み取りや ON/OFF 分岐自体にログはない。バッチ関数の不正 geometry または必須 buffer 欠落は `qsa_decode_attn_batch: unsupported geometry or missing buffers` を stderr に出して `exit(1)` するが、これは環境変数固有の失敗ではない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1007`）。参照した `docs/INTEL.md` の表は Battlemage で既定 ON、対象を「bounded batched QSA decode で active chunks のみ merge」と記すが、この変数単独の測定条件・数値は記載していない（`docs/INTEL.md:584-602`）。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:193-200` — helper の unset/empty/device default および非空値の先頭文字判定。
- `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:31,629-691,1001-1026,1203-1227` — chunk 単位、active merge の計算、読み取り cache、呼び出し条件と fallback。
- `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1256-1299` — row-batch 経路と per-row 委譲条件。
- `engine/CMakeLists.txt:23-33`; `engine/sycl/CMakeLists.txt:273-282` — SYCL が独立 backend であることと kernel source の build 登録。
- `docs/INTEL.md:584-602` — SYCL runtime controls の説明と対象変数の一覧。
