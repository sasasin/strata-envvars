# `STRATA_VIT_CPU_TAIL1`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

独自 Vision CPU tower の AVX 系積カーネルで、最後に残る列がベクトル幅以下のとき、専用の 1 ベクトル積カーネルを使うか選ぶ診断用スイッチである。既定は有効。無効にすると、同じ列を従来の 2 ベクトル積カーネルと全幅の一時バッファで処理する。分岐は `cpu_kernels_impl.h` の `gemm` にあり、環境変数の読み取りはベースライン CPU 向けにコンパイルされた `cpu_ops.cpp` にある（`tools/vision/own/cpu_ops.cpp:20-23`, `tools/vision/own/cpu_kernels_impl.h:109-142`）。

専用カーネルのコメントは各列の積和の順序が同じで結果は bit-identical と説明している。これはコード上の実装説明であり、この調査では性能や出力を実測していない（`tools/vision/own/cpu_kernels_impl.h:81-106`）。

## 値と判定

`std::getenv` の結果に `std::atoi` を適用し、その結果が 0 のときだけ無効にする。それ以外は有効で、文字列全体の検証・エラー処理・clamp はない（`tools/vision/own/cpu_ops.cpp:20-22`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| すべての build（下記の適用条件を満たす経路） | 有効 | `1`, `-1`, `1abc`, ` 1`（`atoi` の結果が非 0） | 空文字, `0`, `00`, `0anything`, `true`, `abc`（`atoi` の結果が 0） |

したがって真偽値文字列 `true` は有効化せず、数値の後ろに文字があっても数値部分で判定する。`atoi` が 0 を返す入力は無効、それ以外は有効であり、無効値専用の警告や fallback はない（`tools/vision/own/cpu_ops.cpp:21`）。

## 有効になる条件

- `strata-vision` が独自 tower の CPU 経路を実行し、`STRATA_VIT_CPU=ref` による `VitRef` 選択がされていないこと。独自 CPU 経路では `VitCpu` をロードして実行する（`tools/vision/own/own_reader.cpp:128-149`）。
- `VitCpu` が選ぶ ISA tier が AVX、AVX2、AVX-512 のいずれかであること。これらの tier は `STRATA_KN_RAW` を定義し、末尾用の分岐を含む。SSE4.1、NEON、scalar はこの分岐を持たない（`tools/vision/own/cpu_kernels_avx.cpp:21-23,166-168`, `tools/vision/own/cpu_kernels_avx2.cpp:21-25,130-137`, `tools/vision/own/cpu_kernels_avx512.cpp:22-25,116-123`, `tools/vision/own/cpu_kernels_sse41.cpp:158-162`, `tools/vision/own/cpu_kernels_neon.cpp:133-140`, `tools/vision/own/cpu_kernels_impl.h:115-129`）。
- その tier の `gemm` に渡る列数 `N` の最終タイルが 2 ベクトル幅 `NR` に満たず、残り列数 `nc` が 1 ベクトル幅 `W` 以下であること。`nc == NR` の通常タイルや、`W < nc < NR` の末尾タイルではこの値を参照しない（`tools/vision/own/cpu_kernels_impl.h:109-116`）。
- ISA は CPU 機能に基づいて選ばれる。x86 では `STRATA_FORCE_ISA` が tier を上限指定できるため、`scalar` / `sse41` に制限した場合はこの分岐に到達しない（`tools/vision/own/cpu_caps.h:88-106`, `tools/vision/own/vit_cpu.cpp:142-148`）。
- `--gpu` で GPU reader を実行する場合、この CPU tower の経路を通らない（`tools/vision/own/own_reader.cpp:114-128,143-149`）。上位の Vision reader 選択では `--vision cpu` / `--vision gpu` が reader を選ぶ（`docs/DETAILS.md:996-1000`）。

## 実行時の詳細

`cpu_tier_one_vector_tail()` の関数内 `static const bool` 初期化子が、関数の最初の呼び出し時に値を読み、以後はプロセス内でキャッシュする。プロセス起動後に環境を書き換えても、このキャッシュ済み値は変わらない。なお、この関数は AVX 系 `gemm` で `nc <= W` の分岐候補になったときだけ呼ばれるため、それ以前や該当する末尾タイルがない実行では値を読まない（`tools/vision/own/cpu_ops.cpp:20-23`, `tools/vision/own/cpu_kernels_impl.h:109-116`）。

有効なら `float bb[W]` / `cb[MRF][W]` の一ベクトル用バッファで `tile_rows1` を呼び、結果の有効列だけを出力へ戻す。無効なら `else` 側へ進み、`float bb[NR]` / `cb[MRF][NR]` の全幅バッファを介して通常の `tile_rows` を呼ぶ。どちらも積結果を `C` に書き戻す経路であり、この変数による CLI 優先順位・他設定値との上書き規則はない（`tools/vision/own/cpu_kernels_impl.h:81-107,109-142`）。

CPU tower の選択自体にはモデル形状の対応条件があるが、本変数固有のモデル判定はない。対象の分岐に来るかは個々の積の列数で決まる（`tools/vision/own/vit_cpu.cpp:142-148,195-203`）。

## ログと測定値

この変数の値、有効・無効の選択、無効値について専用のログやエラー出力はない。独自 tower のロード時には `strata-vision: own tower (...) loaded ...` のログが出るが、これは本変数の判定結果を示さない（`tools/vision/own/own_reader.cpp:141-142`）。`docs/DETAILS.md` は Vision reader の一般的な選び方を記載しているが、この変数の性能値は記載していない（`docs/DETAILS.md:990-1016`）。

## 根拠

- `tools/vision/own/cpu_ops.cpp:20-23` — 読み取り、`atoi` 判定、関数内キャッシュ。
- `tools/vision/own/cpu_tier.h:56-61` — 呼び出し helper の宣言と診断用スイッチについての記述。
- `tools/vision/own/cpu_kernels_impl.h:81-107,109-142` — 1 ベクトル積と全幅バッファ経路、分岐条件。
- `tools/vision/own/cpu_kernels_avx.cpp:21-23,161-168`, `tools/vision/own/cpu_kernels_avx2.cpp:21-25,130-137`, `tools/vision/own/cpu_kernels_avx512.cpp:22-25,116-123` — raw-vector tier の定義。
- `tools/vision/own/own_reader.cpp:114-149`, `tools/vision/own/vit_cpu.cpp:142-148`, `tools/vision/own/cpu_caps.h:88-106` — reader と ISA tier の選択。
- `docs/DETAILS.md:990-1016` — Vision reader の一般的な選択肢と CPU/GPU 経路。
