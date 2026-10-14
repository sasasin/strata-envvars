# `STRATA_WMMA_BF16`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

HIP の prompt 用 BF16 dense GEMM で、RDNA3 / RDNA3.5 向け WMMA kernel を使うかどうかを制御します。この変数は WMMA GEMM 全体を有効にするスイッチではありません。別変数 `STRATA_WMMA_GEMM` が有効なときに、BF16 GEMM も WMMA の候補に含める既定動作を切り替えます。`STRATA_WMMA_GEMM` が無効なら、この変数だけを設定しても BF16 WMMA は呼ばれません。根拠: `src/prefill/gemm.cu:629-636`。

## 値と判定

値全体や数値としての妥当性は parse せず、最初の1文字で判定します。

| `STRATA_WMMA_BF16` | BF16 WMMA の追加ゲート |
|---|---|
| 未設定 | 有効 |
| 空文字 | 無効 |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外（例: `1`, `true`, `false`, `2`） | 有効 |

したがって、この変数の既定は「BF16 WMMA を許可」ですが、全体の WMMA は `STRATA_WMMA_GEMM` が別途有効な場合に限り候補になります。両方の判定は `static const bool` に保存されるため、各判定箇所で初回評価された後にプロセス環境を書き換えても反映されません。根拠: `src/prefill/gemm.cu:632-635`、同じ HIP 条件分岐を持つ `sycl/src/prefill/gemm.dp.cpp:751-758`。

## 有効になる条件

`STRATA_WMMA_BF16` が有効で、さらに `STRATA_WMMA_GEMM` も有効なとき、`Gemm::bf16()` は次の条件を満たせば WMMA dispatch を試します。

- `ldx <= K`（この場合 `Gemm::bf16()` が `ldx` を 0 に正規化する）。`ldx > K` の padded 入力では WMMA dispatch を試しません。
- `T >= 16`。
- `beta` が `0.0f` または `1.0f`。
- WMMA 実装が現在の device を対応 gfx11 と判定し、`K` が 16 の倍数、`ldy >= N` など内部条件も満たす。

内部 dispatch は `gfx1100`, `gfx1101`, `gfx1102`, `gfx1103`, `gfx1150`, `gfx1151` のみを対応対象とします。条件を満たさない場合は `false` を返して通常の GEMM 経路へ進みます。`STRATA_WMMA_GFX11` がビルド時に定義されなければ、実装ファイルの fallback stub も常に `false` を返します。根拠: `src/prefill/gemm.cu:624-638`、`src/prefill/wmma_gemm.cu:31-56,264-289,732-735`、`include/strata/kernels/gfx_arch.hpp:22-25`。

## 実行時の詳細

この環境変数を読む箇所は `Gemm::bf16()` 内の HIP 条件分岐です。`Gemm::bf16()` は通常の BF16 prompt projection などから呼ばれます（例: `src/prefill/prefill.cpp:1989-1994,2567-2577`）。対応条件を通ると BF16 入力を WMMA intrinsic で積和し、FP32 出力 `Y` を計算して通常経路へ戻ります。`T` と `N` がともに32以上なら 64×64 tile の kernel、それ以外は 16×16 tile の kernel を選びます。`K` の端数は内部 dispatch 条件で拒否されます。根拠: `src/prefill/wmma_gemm.cu:75-85,88-148,150-262,264-301`。

WMMA 呼び出しが成功した場合はその場で return します。対応外の device / shape / parameter では後続経路へ進みます。HIP の `f16_io_` が有効なら、まず BF16 weight を FP16 scratch へ変換する経路を通ります。そうでなければ、HIPBLASLt が利用可能で dispatch が受理すると hipBLASLt、それ以外は通常の BF16 GEMM fallback になります。`f16_io_` 用経路も WMMA 判定より後にあるため、WMMA 判定が成功する条件では先に return します。根拠: `src/prefill/gemm.cu:634-660,720-725`。

CUDA ビルドではこの環境変数を読むコードは実行されません。WMMA ソースは CMake 上 HIP build の場合だけ `strata_prefill` に追加され、gfx11 用のビルドでは `STRATA_WMMA_GFX11` が設定されます。根拠: `CMakeLists.txt:607-611`、`cmake/hip_backend.cmake:85-98`。SYCL 側にも同じ判定があり、`sycl/src/prefill/gemm.dp.cpp:751-760` の `STRATA_USE_HIP` 分岐内で使われます。

この変数について、`docs/DETAILS.md` や `docs/AMD_HIP.md` に個別の速度測定値や品質測定値は見当たりません。ここでは性能・出力の同一性を主張しません。

## 根拠

- 読み取り、既定値、併用ゲート、入力 stride と `T` / `beta` 条件: `src/prefill/gemm.cu:624-638`
- HIP/SYCL 系の同等分岐: `sycl/src/prefill/gemm.dp.cpp:746-760`
- gfx11 WMMA の build/runtime gate、shape 条件、tile 選択、BF16 intrinsic: `src/prefill/wmma_gemm.cu:31-56,75-85,264-301`
- 対応 gfx arch: `include/strata/kernels/gfx_arch.hpp:22-25`
- HIP build への WMMA ソース追加と gfx11 compile macro: `CMakeLists.txt:607-611`、`cmake/hip_backend.cmake:85-98`
- BF16 projection 呼び出し例: `src/prefill/prefill.cpp:1989-1994,2567-2577`
