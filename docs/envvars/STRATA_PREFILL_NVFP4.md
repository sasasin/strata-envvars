# `STRATA_PREFILL_NVFP4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

NVFP4 の MoE expert を含む prompt prefill で、Strata の fused expert 経路が使う活性値の精度・計算経路を選ぶ。現在のソースでは `w4a4` は Blackwell の Strata 所有 mxf4nvf4 kernel、未設定・空・`w4a8` は fused W4A8（int8 tensor core、Q8_1 活性値）、その他の明示値は legacy MMQ または FP16 経路に振り分ける（`engine/include/strata/prefill/nvfp4_prefill_mode.hpp:27-53`）。実際に prompt の NVFP4/NVFP4 expert pair を fused 経路へ載せるには `STRATA_PF_FUSED` の判定と、device・layer 条件も満たす必要がある（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3465-3489`）。decode の計算方法はこの分岐の対象ではない。

`docs/NVFP4.md` の MMQ 用 `w4a4` / `w4a4x2` 表は、この checkout の Strata 所有実装の説明とは一致しない。同ファイルは MMQ kernel を前提に記述している一方、現行 CUDA/HIP の own-kernel target は `mmq_absent.cpp` をリンクし、W4A4 は `moe_fp4_tc.cu` の Strata kernel として実装されている（`engine/cmake/backends/cuda.cmake:94-136`、`engine/cmake/backends/hip.cmake:30-46`）。ここでは現行コードの分岐だけを記す。

## 値と判定

CUDA の共通 resolver は文字列全体を大文字小文字を区別して比較する。数値変換、trim、prefix 判定はしない。未設定・空文字・完全一致の `w4a8` は W4A8、完全一致の `w4a4` は条件付き W4A4、それ以外の明示値は `LegacyMmqOrF16` を選ぶ（`engine/include/strata/prefill/nvfp4_prefill_mode.hpp:27-46`）。現在の own-kernel build は MMQ を含まないため、legacy 側は prompt planner の FP16 path となる（`engine/src/prefill/mmq_absent.cpp:1-23`、`engine/src/prefill/prefill.cpp:399-404`）。

| 条件 | unset / 空文字 | 有効値 | 無効値・結果 |
| --- | --- | --- | --- |
| CUDA resolver。モデルに `<stem>.input_scale` があり、native FP4 kernel が利用可能 | W4A8 | `w4a4` → W4A4、`w4a8` → W4A8 | `fp16`、`w4a4x2`、`W4A4`、空白付きなど → legacy MMQ/FP16 |
| CUDA resolver。`w4a4` だがモデル scale がない | W4A8 | `w4a4` → lossless W4A8 へ degrade | 上と同じ。scale 不足は W4A8 へ degrade しない別条件 |
| CUDA resolver。`w4a4` だが native FP4 kernel が利用不能 | W4A8 | `w4a4` → MMQ が build にあれば legacy MMQ/FP16、なければ W4A8 へ degrade | その他の明示値 → legacy MMQ/FP16 |
| HIP の fused NVFP4 pair | unset・空・`w4a8` のみ fused W4A8 判定を通る | 完全一致 `w4a8` | `w4a4` を含む他の明示値は fused NVFP4 pair の条件を満たさない（`engine/src/prefill/moe_fused_iq.cu:3555-3559`） |

`getenv(...) != nullptr` は空文字も「設定済み」として扱うため、起動時の GPU 既定値適用では空文字を含む利用者の値を上書きしない（`engine/src/core/nv_defaults.cpp:222-234`）。resolver 自体では空文字は未設定と同じ W4A8 である。

## 有効になる条件

- CUDA の `w4a4` native kernel は CUDA compiler 13.0 以上で、build の CUDA architecture list に 120 または 121 が含まれる場合にだけ target に組み込まれる。実行時にも現在の device が compute capability 12.0/12.1 で、shape と kernel occupancy の検査を通る必要がある（`engine/cmake/backends/cuda.cmake:97-130`、`engine/src/prefill/moe_fp4_tc.cu:497-537`）。
- 対象 expert pair は gate/up と down の両方が NVFP4 で、native pack の fused prompt 経路が選ばれる場合。mixed pair は対象外。CUDA の NVFP4 pair 判定は `STRATA_PF_FUSED` の effective 値が `1` の場合だけ通る。未設定でも MMQ なし build は pre-main 初期化で `1` を入れるが、既に設定済みの値は保持する。さらに native kernel の device/layer 条件、非 warp-specialized 等の制約がある（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3465-3489`、`engine/src/prefill/prefill.cpp:223-255`）。
- `w4a4` ではロード済みモデルの対象 NVFP4 expert に `<stem>.input_scale` が必要。`--native` のモデル走査で対象 tensor の scale 欠落が一つでも見つかると、モデル全体の `fp4_tc::wanted()` は W4A4 を選ばず W4A8 に degrade する（`engine/src/program/generate.cpp:5135-5149`、`engine/src/prefill/moe_fp4_tc.cu:543-568`）。
- CUDA 起動時の自動既定値は、可視 device がすべて同じ compute capability の場合に適用される。compute capability 12.0 / 12.1 の既定表はそれぞれ `STRATA_SM120_PERF=0` / `STRATA_SM121_PERF=0`、または `STRATA_DEFAULTS=026` で外れる。利用者が `STRATA_PREFILL_NVFP4` を何らかの値で設定していれば既定値 `w4a4` は追加されない（`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:104-129,176-214,222-234`）。
- 同一 compute capability でない複数 CUDA device では上記の GPU 既定表は適用されない。明示値は残るが、native kernel の可用性は呼出し中の device ごとに判定される（`engine/src/program/generate.cpp:4428-4469`、`engine/src/prefill/moe_fp4_tc.cu:497-537`）。
- HIP には FP4 tensor-core target の absent stub が入り、`fp4_tc::available()` / `wanted()` は false。HIP の NVFP4 fused pair 判定は unset・空・`w4a8` のみを受け付ける（`engine/cmake/backends/hip.cmake:32-46`、`engine/src/prefill/moe_fp4_tc_absent.cpp:10-16`、`engine/src/prefill/moe_fused_iq.cu:3555-3559`）。

## 実行時の詳細

CUDA の NVFP4 W4A4 kernel が組み込まれている場合、`fp4_tc::wanted()` は利用可能 device を確認してから `std::getenv("STRATA_PREFILL_NVFP4")` を resolver に渡す。環境値自体はこの関数呼び出しごとに読み直され、関数内に値の static cache はない。一方、device 可用性は device ごとの `DevState` に cache される（`engine/src/prefill/moe_fp4_tc.cu:497-558`）。model の scale 有無は `--native` ロード時に設定される（`engine/src/program/generate.cpp:5135-5149`）。

W4A4 が選ばれると、prompt prefill は活性値を NVFP4 に量子化し、Blackwell mxf4nvf4 tensor-core kernel を用いる。prefill の fused layer walk は gate/up と down の NVFP4 pair かつ `fp4_tc::wanted()` のときだけ `fp4_nat` として扱い、該当 kernel の利用ログを一度出す（`engine/src/prefill/prefill.cpp:5740-5766`）。同じ `wanted()` 判定は staged group と layer-major の prompt 経路にも使われる（`engine/src/prefill/prefill.cpp:6423-6441,8843-8850`）。

W4A8 / W4A4 以外の値では fused NVFP4 pair を選ばず、現行 own-kernel build では MMQ がないため planner が FP16 経路を選ぶ。HIP の `mode_ok` は関数内 `static` で初回判定を cache する。CUDA の `native_supported()` も `STRATA_PF_FUSED` を static に読み取るが、対象の `STRATA_PREFILL_NVFP4` はその関数内では毎回 resolver に渡される（`engine/src/prefill/moe_fused_iq.cu:3425-3428,3475-3489,3555-3559`）。

## ログと測定値

- `w4a4` が要求されたが native Blackwell FP4 kernel を build/device で使えず、W4A8 に degrade する場合、stderr に `strata: STRATA_PREFILL_NVFP4=w4a4 requested, but native Blackwell FP4 tensor-core prompt kernels are not active on this device/build; staying on fused W4A8 tensor cores instead of falling back to FP16 cuBLAS` を一度出す（`engine/src/prefill/moe_fused_iq.cu:3478-3485`）。
- 対象 model に `<stem>.input_scale` がない場合、stderr に `strata: STRATA_PREFILL_NVFP4=w4a4 requested, but model lacks <stem>.input_scale; degrading to lossless W4A8 prefill.` を一度出す（`engine/src/prefill/moe_fp4_tc.cu:559-567`）。
- W4A4 の kernel が実際に prompt layer で使われると、stderr に `strata: prompt NVFP4 experts on the Blackwell mxf4nvf4 tensor-core kernels (STRATA_PREFILL_NVFP4=w4a4)` を一度出す（`engine/src/prefill/prefill.cpp:5740-5751`）。
- 12.0/12.1 の自動既定値が追加された場合、`apply_nv_defaults()` は stderr にカード別の「speed switches on by default」行を出し、その switch 名一覧に `PREFILL_NVFP4` を含める（`engine/src/core/nv_defaults.cpp:240-255`）。

## 根拠

- 値解決: `engine/include/strata/prefill/nvfp4_prefill_mode.hpp:27-53`
- native kernel build / device 条件: `engine/cmake/backends/cuda.cmake:97-130`、`engine/src/prefill/moe_fp4_tc.cu:497-568`
- 自動既定値と利用者設定の優先: `engine/src/core/nv_defaults.cpp:104-129,176-234`、`engine/src/program/generate.cpp:4421-4449`
- model scale の検査: `engine/src/program/generate.cpp:5135-5149`
- fused NVFP4 条件と HIP 判定: `engine/src/prefill/moe_fused_iq.cu:3415-3432,3465-3489,3555-3559`
- prompt dispatch と観測ログ: `engine/src/prefill/prefill.cpp:5740-5766,6423-6441,8843-8850`
- legacy/FP16 path: `engine/cmake/backends/cuda.cmake:135-136`、`engine/src/prefill/mmq_absent.cpp:1-23`、`engine/src/prefill/prefill.cpp:399-404`
