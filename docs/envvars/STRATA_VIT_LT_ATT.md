# `STRATA_VIT_LT_ATT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 版の Strata own vision tower で、attention の2つの batched 行列積を hipBLASLt に通す要求フラグ。対象は `K Q^T` の score 計算と、softmax 後の `V P` による context 計算で、重み行列の積を選ぶ `STRATA_VIT_LT` とは別に制御される。CUDA/cuBLAS、SYCL/oneMKL、Metal、CPU の実装にはこの読み取りがなく、変数を設定してもそれらの経路は変わらない。`terminal/tools/vision/own/vit_gpu.cu:500-504,611-615,659-664,1130-1141`。

## 値と判定

`lt_setup()` 内の helper が `std::getenv(name)` の結果に `std::atoi(e) != 0` を適用する。未設定は false、空文字も `atoi("") == 0` となり false。整数全体の厳密な検証や文字列比較はなく、`atoi` が読む先頭の整数部分が 0 以外なら true になる（例: `1`, `-1`, `1tail` は true、`0`, `0tail`, `true`, `false`, 空文字、整数に変換できない文字列は false）。先頭の空白と符号は `atoi` の変換規則に従う。`terminal/tools/vision/own/vit_gpu.cu:611-615`。

| ビルド・実行経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP + `STRATA_VIT_HIPBLASLT` が定義され、own vision GPU reader がロードされる | false（hipBLASLt attention 積を要求しない） | `atoi` の結果が 0 以外。例: `1`, `-1`, `1tail` | `atoi` の結果が 0。例: `0`, `0tail`, `true`, 空文字 |
| CUDA、SYCL、Metal、CPU、または HIP build で hipBLASLt が見つからない | このコードで読まれない | 該当なし | 該当なし |

## 有効になる条件

- `strata-vision-hip` を使う HIP GPU vision reader の経路であること。reader は `--gpu` 指定時に GPU を生成してロードする。`terminal/tools/vision/own/own_reader.cpp:63-77,95-100`。
- HIP build に `roc::hipblaslt` target が見つかり、`STRATA_VIT_HIPBLASLT` が定義されること。CMake は hipBLASLt を任意依存として探索する。見つからなければ、この変数を読むコードもコンパイルされない。`terminal/tools/vision/own/CMakeLists.txt:127-137`。
- `lt_setup()` の hipBLASLt 初期化と 32 MiB workspace 確保が成功すること。失敗すると両方の LT 要求フラグを false にし、全積を hipBLAS に戻す。`terminal/tools/vision/own/vit_gpu.cu:515-516,611-624`。
- encode が通常の chunked attention 経路を通ること。HIP の fused attention (`m.fa`) が有効な場合は fused kernel が実行され、以下の batched GEMM (`bgemm`) に進まない。このため `STRATA_VIT_LT_ATT=1` だけでは fused attention を hipBLASLt に切り替えない。fused attention の要求・カード条件は別の `STRATA_VIT_FA`、HIP device の条件、または gfx1151 の既定条件に依存する。`terminal/tools/vision/own/vit_gpu.cu:923-924,942-978,1105-1129`。
- このフラグは `STRATA_VIT_LT` や CLI による重み積の選択を変更しない。`lt_weights` と `lt_att` は別々に読み、積の経路も別に分岐する。`terminal/tools/vision/own/vit_gpu.cu:611-617,659-664,788-792`。

## 実行時の詳細

値は `VitGpu::load()` の中で GPU/BLAS handle を用意した後、`lt_setup()` が呼ばれる時点で読み取られる。プロセス起動時の一括 cache ではなく、`VitGpu` インスタンスのロード時に一度 `lt_att` に保存され、その reader の encode 中はこの値を使う。ロード済みインスタンスに対するプロセス環境の後変更は反映されない。別インスタンスを後からロードすれば、そのロード時の環境を読む。`terminal/tools/vision/own/vit_gpu.cu:611-617,917-918,956-962`。

要求が有効で setup に成功すると、通常の attention loop で `bgemm()` がまず `lt_mm()` を試し、成功時は hipBLASLt の batched product を実行する。対象は `K Q^T` と `V P` の二箇所。shape ごとの plan は `lt_plans` に保存され、2回目以降は再利用される。`lt_mm()` が plan を作れない場合は false を返し、呼び出し元が通常の `cublasGemmStridedBatchedEx`（HIP build では hipBLAS 名に対応）へ進む。実行時に hipBLASLt product が失敗した場合も、その shape の plan を無効化し、以後その shape は hipBLAS に戻す。`terminal/tools/vision/own/vit_gpu.cu:543-593,596-609,659-682,1130-1141`。

## ログと測定値

- LT setup と workspace 確保が失敗した場合、stderr に `vit-lt: hipBLASLt is not usable here; hipBLAS for every product` を出し、LT を無効にする。成功時は `vit-lt: hipBLASLt for ... (solution ...)` を出す（attention のみなら `the attention products`）。`terminal/tools/vision/own/vit_gpu.cu:618-627`。
- 個別 shape の hipBLASLt product が失敗すると stderr に `vit-lt: the hipBLASLt product failed (m=%d n=%d k=%d batch=%d); hipBLAS from now on for this shape` を出して fallback する。`terminal/tools/vision/own/vit_gpu.cu:601-606`。
- `STRATA_VIT_LT_VERBOSE` が有効なら plan の選択・非対応状況を shape ごとに stderr に出し、reader 破棄時に `vit-lt: %llu hipBLASLt products, %llu by hipBLAS` の集計を出す。Verbose の判定も同じ `atoi != 0` helper を使う。`terminal/tools/vision/own/vit_gpu.cu:589-593,611-615,629-635`。
- `docs/DETAILS.md` の Vision settings（`docs/DETAILS.md:1133-1144`）にこの変数の記述はない。調査対象 commit のソースから、この変数による測定値は確認できないため記載しない。

## 根拠

- 読み取りと既定値、LT setup、初期化ログ: `terminal/tools/vision/own/vit_gpu.cu:611-627,917-918,956-962`。
- 任意の HIP hipBLASLt build 条件: `terminal/tools/vision/own/CMakeLists.txt:127-137`。
- attention の2積、通常の hipBLAS fallback、shape ごとの失敗処理: `terminal/tools/vision/own/vit_gpu.cu:596-609,659-682,1130-1141`。
- fused attention の条件と分岐: `terminal/tools/vision/own/vit_gpu.cu:923-924,942-978,1105-1129`。
- GPU reader の選択・ロード・encode: `terminal/tools/vision/own/own_reader.cpp:63-77,95-100`。
