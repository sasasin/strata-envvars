# `STRATA_VIT_LT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 版 own vision tower で、16-bit 入力の重み行列積を hipBLASLt に切り替える診断用スイッチ。対象は ViT の重み行列積で、float32 入力の patch embedding は対象外。attention の batched products は別の `STRATA_VIT_LT_ATT` が制御する。変数を有効にしても、hipBLASLt がその shape の実行可能な解を返さない場合や実行に失敗した場合は hipBLAS を使う。CUDA、SYCL、CPU の積算経路を切り替える変数ではない（`terminal/tools/vision/own/vit_gpu.cu:500-504, 788-812`）。

この設定の読取箇所は `VitGpuImpl::lt_setup` の一箇所。CMake は HIP ビルド時に hipBLASLt を任意検出し、`roc::hipblaslt` target が存在するときだけ `STRATA_VIT_HIPBLASLT` を定義して同実装を含める（`terminal/tools/vision/own/vit_gpu.cu:611-628`, `terminal/tools/vision/own/CMakeLists.txt:127-137`）。

## 値と判定

`lt_setup` 内の共通 lambda が `std::getenv(name)` で取得し、`e && std::atoi(e) != 0` で判定する。未設定と空文字は false。整数全体の妥当性や末尾文字は検証せず、`atoi` が先頭から変換した値が 0 かどうかだけを見る。従って `1`, `-1`, `1tail` は true、`0`, `0tail`, `true`, `false`, 空白だけの文字列は false。先頭空白の後に非ゼロ整数があれば true。これは既定で無効である（`terminal/tools/vision/own/vit_gpu.cu:611-617`）。

| 条件（build / 実行経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP build かつ `STRATA_VIT_HIPBLASLT` 定義あり、own tower を GPU 実行 | `lt_weights=false`。重み積は hipBLAS | `1`, `-1`, `1tail` | 空文字, `0`, `0tail`, `true`, `false`, `abc` |
| CUDA / SYCL / CPU、または hipBLASLt 非検出 build | この名前の読取コード自体がないため効果なし | 該当なし | 該当なし |

## 有効になる条件

- プロセスが HIP 版 own vision tower を使い、ビルド時に `STRATA_VIT_HIPBLASLT` が定義されていること。CMake では HIP backend と `roc::hipblaslt` target の両方が必要（`terminal/tools/vision/own/CMakeLists.txt:127-137`）。
- `strata-vision` の own tower を GPU で起動すること（通常の reader は `--gpu` 相当のオプションで `VitGpu::load` を通る）。CPU path では `VitGpu` を作らず、CUDA/SYCL path にはこの hipBLASLt 設定部がない（`terminal/tools/vision/own/own_reader.cpp:60-88, 95-101`; `terminal/tools/vision/own/own_main.cpp:13-41`）。
- `atoi` 判定が非ゼロであること。`0` の場合は `STRATA_VIT_LT_ATT` も無効なら hipBLASLt handle と workspace を作らず、通常の hipBLAS 経路のまま（`terminal/tools/vision/own/vit_gpu.cu:617-625`）。
- 重み積の入力型が float32 でないこと。`gemm` は `lt_weights` が true でも `kind_a == CUDA_R_32F` なら hipBLASLt を呼ばない。patch embedding の float32 積はこのため対象外（`terminal/tools/vision/own/vit_gpu.cu:788-812`, 呼出し例 `1091-1096, 1144-1157, 1163-1170`）。
- shape ごとに hipBLASLt の plan が有効で、matmul が成功すること。利用可能な plan が作れない場合または matmul が失敗した場合は hipBLAS へ fallback する（`terminal/tools/vision/own/vit_gpu.cu:543-593, 595-609, 803-806`）。

## 実行時の詳細

own reader が GPU tower をロードすると `VitGpu::load` は BLAS handle を作った後、一度 `lt_setup` を呼ぶ。ここで `STRATA_VIT_LT` を読み、`lt_weights` に保存するため、load 後の環境変更はその reader instance には反映されない。reader は READY 前に GPU load と warm-up を行い、その後の画像 encode は同じ `VitGpu` instance を使う（`terminal/tools/vision/own/vit_gpu.cu:917-962`; `terminal/tools/vision/own/own_reader.cpp:63-78, 102-120`）。

重み行列積で有効なら hipBLASLt を試し、失敗時に既存の hipBLAS GEMM を呼ぶ。solution は shape ごとに `lt_plans` map に保存され reader lifetime 中再利用される。`STRATA_VIT_LT_SOL` が設定され、`atoi` の結果が 0 以上なら指定 ID を試し、それ以外は workspace 上限 32 MiB に収まる最初の heuristic 解を使う。これは関連設定の影響であり、本変数自体は解 ID を指定しない（`terminal/tools/vision/own/vit_gpu.cu:512-519, 543-588, 611-616`）。

handle の作成または 32 MiB workspace の確保に失敗すると、両方の Lt switch を false にして以降の全積を hipBLAS にする。shape に解がなければその積のみ hipBLAS に回る。Lt matmul 自体が失敗した場合はその shape の plan を破棄し、以降同 shape は hipBLAS に回る。通常の hipBLAS GEMM が失敗した場合は `the BLAS matrix product failed (status N)` をエラーとして返す（`terminal/tools/vision/own/vit_gpu.cu:595-625, 788-806`）。

## ログと測定値

- 設定された重み積か attention 積の少なくとも一方が有効で、Lt handle と workspace の作成に成功すると stderr に `vit-lt: hipBLASLt for the weight products (solution heuristic)`（solution ID が 0 以上なら `solution <ID>`）等を出す。`STRATA_VIT_LT` のみ有効なら表示対象は `the weight products`（`terminal/tools/vision/own/vit_gpu.cu:626-627`）。
- handle または workspace の初期化失敗時は stderr に `vit-lt: hipBLASLt is not usable here; hipBLAS for every product` と出す（同 `:618-624`）。
- 実行可能な解がない shape は `STRATA_VIT_LT_VERBOSE` が有効なら shape ごとに `vit-lt: ... -> hipBLAS, no solution ...` を出す。matmul が失敗すると stderr に `vit-lt: the hipBLASLt product failed (m=... n=... k=... batch=...); hipBLAS from now on for this shape` を出す（同 `:589-592, 601-606`）。
- `STRATA_VIT_LT_VERBOSE` が有効で Lt launch または fallback があった場合、reader 破棄時に `vit-lt: <N> hipBLASLt products, <N> by hipBLAS` を出す（同 `:629-635, 685-692`）。対象 commit の `docs/DETAILS.md` にこの変数名の記載は見つからなかった。ソースコメントに別環境・条件の計測に関する記載はあるが、本調査では本変数の一般的な性能値として採用しない。

## 根拠

- 値の判定・関連 Lt 設定・初期化ログ: `terminal/tools/vision/own/vit_gpu.cu:611-628`
- shape ごとの plan と cache、fallback、verbose logs: `terminal/tools/vision/own/vit_gpu.cu:512-519, 543-609, 629-638`
- 重み積が対象になる条件と通常 GEMM fallback: `terminal/tools/vision/own/vit_gpu.cu:788-812`
- load 時期・backend 条件: `terminal/tools/vision/own/vit_gpu.cu:917-962`; `terminal/tools/vision/own/CMakeLists.txt:120-137`
- own reader の GPU load / warm-up / encode: `terminal/tools/vision/own/own_reader.cpp:63-78, 95-120`
