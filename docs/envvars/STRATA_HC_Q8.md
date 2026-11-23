# `STRATA_HC_Q8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

hyper-connection のダウン / アップ射影（`blk.*.hc_{attn,ffn}_{down,up}.weight` と最終ミキサの `output_hc_{down,up}.weight`）を Q8_0 で読むか、パックの BF16 で読むかを選ぶ（`engine/src/core/native_dense.cpp:47-118`）。ON のとき NativeDense はロード時に Q8_0 のコピーを確保し、verify ウィンドウの読み（`fused_gr_read_multi`）と最終ミキサだけがそれを読む（`engine/include/strata/kernels/fused_gr.hpp:41-52`）。プロンプト経路の GEMM と `fused_gr_read` は BF16 を読むため、bf16 コピーをロードしなかった行は `hc_bf16_view` が Q8_0 から都度 bf16 へ戻す（`engine/include/strata/core/native_dense.hpp:58-60`、`engine/src/prefill/prefill.cpp:5091-5100`）。

トークナイザ、KV、ルーティング、層の配置は変わらない。重みの丸めと和の順序が変わるため生成結果は一致しないことがある（`engine/src/kernels/cuda/fused_gr.cu:2174-2179`）。

## 値と判定

CUDA/HIP は先頭 1 文字だけを見る。`v[0]=='1'` なら ON で、`1`・`10`・`1x` はすべて ON。空でなく `"auto"` でない値は明示的な OFF で、`0`・`true`・`2`・`AUTO` がこれに当たる。空文字と `"auto"` だけがアーキテクチャ既定へ落ちる（`engine/src/core/native_dense.cpp:53-56`）。数値としての妥当性検査、大文字小文字の正規化、後続文字の検査はない。

| build / backend | unset・空文字・`auto` | ON になる値 | OFF になる値 |
|---|---|---|---|
| CUDA（非 HIP） | OFF（`#else return false`） | `1` で始まる値 | `0`・`true`・`2`・`AUTO` |
| HIP gfx1151 | ON | 同上 | 同上 |
| HIP gfx1100/1101/1102（dGPU、`STRATA_GFX11_DEFAULTS=0` と `STRATA_GFX11_WMMA_DEFAULTS=0` が無く `STRATA_DEFAULTS=026` でもない） | ON | 同上 | 同上 |
| HIP gfx1200/1201 | ON（`STRATA_GFX12_DEFAULTS=0` のときだけ OFF） | 同上 | 同上 |
| HIP その他の arch | OFF | 同上 | 同上 |
| SYCL | OFF（`auto` も含む） | `1` で始まる値 | それ以外すべて |
| Metal | ON | `"0"` 以外すべて（空文字・`false`・`off` も ON） | 文字列が完全に `"0"` のときだけ（`engine/metal/src/engine/window.cpp:926-928`） |

CUDA の既定 ON は別経路で入る。`generate.cpp` が `apply_hc_q8_default` を呼び、未設定で GGUF が down/up を Q8_0 で持つときだけ `"1"` を setenv する。設定済みの `0` も空文字も上書きしない（`engine/src/core/native_dense.cpp:683-691`、`engine/src/program/generate.cpp:5164-5169`）。よって CUDA で空文字を明示すると既定 ON は抑止され OFF になる。

## 有効になる条件

- CUDA/HIP: native dense の GGUF が渡されていること。Q8_0 コピーは `NativeDense::load` の中でしか作られない（`engine/src/program/generate.cpp:6032-6037`）。
- CUDA: 既定 ON は `STRATA_USE_HIP`・`STRATA_HIP_GFX906`・`STRATA_GPU_METAL` のいずれも定義されない build だけ（`:5165`）。
- HIP の arch 判定は latch 時点の `cudaGetDevice` が返す現在デバイスで行う（`engine/src/core/native_dense.cpp:58-95`）。
- bf16 コピーをロードしない節約は単一 GPU かつ native pack の `index.txt` が読めるときだけ（`engine/src/program/generate.cpp:5794-5797`）。

値が ON でも条件を満たさない場合は無視され、理由ログは出ない。Metal は decode ウィンドウだけで効く（`engine/metal/src/engine/window.cpp:937-949`）。

## 実行時の詳細

読み取り時期: CUDA/HIP と SYCL は関数内 `static` に latch するので、最初の `load` 以降の変更は反映されない（`engine/src/core/native_dense.cpp:48-99`、`engine/sycl/src/core/native_dense.cpp:34-37`）。CUDA の既定 ON はこの読みより前に走る必要がある（`engine/include/strata/core/native_dense.hpp:55-56`）。Metal は `Window::init` で 1 回読んで `hc_q8_` に保存する（`engine/metal/src/engine/window.cpp:592,926-928`）。

ロード時: GGUF が Q8_0 で持つ down/up と最終ミキサは 1 本ずつ `cudaMalloc` してコピーし、F32 の inject 行は `STRATA_HC_Q8_INJECT=1` のときだけ Q8_0 化する（`engine/src/core/native_dense.cpp:530-565`）。bf16 パックでは down/up を Q8_0 へ量子化し、arena に残った行は GPU で、skip した行はホストでパックから読む（`:566-602`）。bf16 コピーを持たない行用の bf16 スクラッチもデバイスごとに 2 枚確保し（`:603-625`）、VRAM 計画 `weight_bytes_for` は Q8_0 コピー分を 2 MiB granule で上乗せする（`:250-262`）。

使われ方: verify ウィンドウでは `hc_q8` が非 null なら `q8_down`/`q8_up`/`q8_inject` を `fused_gr_read_multi` に渡し、最終ミキサも両方が Q8_0 なら Q8 読みになる（`engine/src/core/verify.cpp:1805-1806,3032-3044`）。プロンプト経路は bf16 コピーがない場合だけ dequant してから GEMM する（`engine/src/prefill/prefill.cpp:5091-5100,9290-9300`）。`STRATA_HC_PERSIST=1` の読みは Q8 読みでは走らない（`engine/include/strata/kernels/fused_gr.hpp:100-103`）。

注意: `WeightTable::load_hc_q8` は `STRATA_HC_REQ8` の別経路（`engine/src/program/generate.cpp:5958`）。

## ログと測定値

stderr（arch ログは既定で ON になったときだけ）:

- gfx1151: `strata: Strix Halo (gfx1151): 8-bit hyper-connection weights are on (decode about 9% faster, answers can differ in near-tie tokens); STRATA_HC_Q8=0 keeps the bf16 read`
- gfx11: `strata: gfx11 (RDNA3): 8-bit hyper-connection weights are on (quantized at load, decode faster, answers can differ slightly); STRATA_HC_Q8=0 or STRATA_GFX11_DEFAULTS=0 keeps the bf16 read`
- gfx12: `strata: gfx12 (RDNA4): the hyper-connection projections are read as Q8_0 (quantized at load, decode faster, answers differ slightly); STRATA_HC_Q8=0 keeps the bf16 read`
- ロード後: `strata: STRATA_HC_Q8=1: %.2f GiB of Q8_0 hyper-connection projections for the verify read`
- Metal: `strata metal: HC read in Q8_0 (STRATA_HC_Q8=0: BF16): %zu matrices, %.0f MB, made in %.0f ms`

明示 ON の CUDA では arch ログは出ず、ロード後の 1 行だけになる（`engine/src/core/native_dense.cpp:58-95,663-665`）。
失敗経路: 行の形が合わない、アップロードや量子化に失敗した場合は err に `native dense (STRATA_HC_Q8): ...` を入れて load が false になり、`strata generate: native dense projections: ...` を出して終了コード 1（`engine/src/core/native_dense.cpp:548-600`、`engine/src/program/generate.cpp:6032-6037`）。

資料の測定値（条件付き）: `docs/STRIX_HALO.md:238` は gfx1151・IQ3_S・MTP 4 drafts・min-p 0.5 で `json_extract` 53.55 → 58.03 tok/s、250 トークン中 94 個が BF16 読みと異なるとする。`docs/AMD_HIP.md:307` は既定を gfx12 と gfx1151 のみと書くが、コードは gfx1100/1101/1102 も既定 ON にする（`engine/src/core/native_dense.cpp:70-85`）。

## 根拠

- `engine/src/core/native_dense.cpp:47-118,683-704`: `hc_q8_env()` の判定と arch 既定、`apply_hc_q8_default`、`add_hc_skip`。
- `engine/src/program/generate.cpp:5164-5169,5794-5797,6032-6037`: 既定 ON、bf16 skip、load 失敗。
- `engine/src/core/native_dense.cpp:250-262,530-625,663-665`: Q8_0 確保、VRAM 見積り、スクラッチ、ログ。
- `engine/src/core/verify.cpp:1805-1806,3032-3044`、`engine/src/prefill/prefill.cpp:5091-5100,9290-9300`: Q8 読みと dequant。
- `engine/metal/src/engine/window.cpp:592,926-949,972-973,3198-3199`、`engine/sycl/src/core/native_dense.cpp:34-37,393,480-482`、`engine/include/strata/kernels/fused_gr.hpp:41-52,100-103`。
