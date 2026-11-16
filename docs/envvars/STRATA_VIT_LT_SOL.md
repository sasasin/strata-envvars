# `STRATA_VIT_LT_SOL`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP 版の Strata own vision GPU reader が hipBLASLt を使うとき、weight 行列積で shape ごとに選ぶアルゴリズム solution ID を指定する。通常は hipBLASLt の heuristic が workspace に収まる候補を選ぶが、この変数を非負の整数に変換できる値にすると、その ID を各 weight product の候補として渡す。solution が shape で使えない場合は hipBLAS の行列積へ戻る。これは vision encoder の GPU 行列積の選択だけを変え、CPU reader や engine 本体の行列積を制御しない（`tools/vision/own/vit_gpu.cu:483-487, 543-575, 748-770`）。

## 値と判定

`VitGpu::load` から呼ばれる `lt_setup` が `std::getenv` で読み、値が設定されていれば `std::atoi` の結果を `lt_sol` に保存する。文字列全体の検証はなく、空文字・数字で始まらない文字列は `atoi` により 0、先頭の空白と符号は整数変換規則に従い、数値の後ろの文字は無視される。大文字小文字の区別は該当しない。変換値が負なら指定 ID としては扱わず heuristic に切り替わる。整数の有効範囲をコードは検査しない（`tools/vision/own/vit_gpu.cu:499-500, 594-600`）。

| 条件 | unset | 有効になる値（例） | 無効・heuristic になる値（例） |
|---|---|---|---|
| HIP + `STRATA_VIT_HIPBLASLT` ビルドで own GPU reader をロード | `lt_sol=-1`。weight products は heuristic 候補を使用 | `0`, `1`, `12` はそれぞれ ID 0, 1, 12 を要求。`12tail` も `atoi` の結果 12 | `-1`, `-12` は負値なので heuristic。空文字、`abc` は 0 となり ID 0 を要求。`  7x` は 7 を要求 |
| CUDA、CPU、SYCL、Metal、または hipBLASLt なしの HIP build | この名前の読み取り箇所がなく、効果なし | 該当なし | 該当なし |

非負 ID が設定されても、それだけで hipBLASLt を有効にはしない。weight products を hipBLASLt に送る別変数 `STRATA_VIT_LT` が `atoi` で非ゼロとなる必要がある。ID 自体の lookup や shape ごとの対応可能性は利用時に検査される（`tools/vision/own/vit_gpu.cu:543-575, 594-600, 752-755`）。

## 有効になる条件

- own tower の GPU reader が選択され、`VitGpu::load` に到達すること。own reader の GPU 経路でのみ GPU encoder が生成・使用される（`tools/vision/own/own_reader.cpp:114-125, 141-149`）。
- HIP backend であり、ビルド時に hipBLASLt が見つかって `STRATA_VIT_HIPBLASLT` が定義されていること。CMake は HIP の own GPU source を追加し、`roc::hipblaslt` target がある場合だけこの macro と link を加える（`tools/vision/own/CMakeLists.txt:127-137`）。
- `STRATA_VIT_LT` が非ゼロで weight products が有効になること。`STRATA_VIT_LT_SOL` は `STRATA_VIT_LT_ATT` が有効な attention products には適用されず、attention 側は `lt_mm(..., -1)` を渡して heuristic を使う（`tools/vision/own/vit_gpu.cu:594-600, 643-647, 752-755`）。
- hipBLASLt handle と 32 MiB workspace の初期化に成功すること。失敗時は両方の hipBLASLt 機能を無効にして hipBLAS に戻る（`tools/vision/own/vit_gpu.cu:498, 600-607`）。
- 指定 ID が hipBLASLt の index lookup に成功し、対象 shape でサポートされ、必要 workspace が 32 MiB 以下であること。いずれかを満たさない shape は hipBLAS 経路を使う（`tools/vision/own/vit_gpu.cu:543-553, 575-582, 766-770`）。

## 実行時の詳細

値は画像 reader のプロセスで `VitGpu::load` 中に `lt_setup` が一度読み取る。own reader は GPU encoder を load 時に作り、その後の warm-up と画像 encode で同じ `VitGpu` を使う。環境値の再読込はなく、同一プロセス実行中の変更は反映されない（`tools/vision/own/vit_gpu.cu:594-600, 895-938`; `tools/vision/own/own_reader.cpp:114-125, 151-165, 190-194`）。

solution ID は各 weight GEMM の shape を初めて処理するときに lookup / support / workspace 判定される。結果の `LtPlan` は shape key ごとに `lt_plans` に保存され、以後の同形積は同じ plan を使う。指定 algorithm の判定に失敗するか、hipBLASLt 実行が失敗すると、その積または当該 shape は hipBLAS に fallback する。実行失敗時にはその shape の plan を破棄する（`tools/vision/own/vit_gpu.cu:495-502, 525-576, 578-592`）。

## ログと測定値

hipBLASLt の初期化に成功すると stderr に `vit-lt: hipBLASLt for %s%s%s (solution %s)\n` の形式で出す。これは設定された値の表示であり、各 shape で指定 ID が採用されたことまでは示さない（`tools/vision/own/vit_gpu.cu:609-610`）。

`STRATA_VIT_LT_VERBOSE` が非ゼロなら、新しい shape ごとに `vit-lt: %s%s m=%d n=%d k=%d types=%d/%d/%d batch=%d -> %s %d (workspace %zu)\n` を出す。`%s` の結果部分は成功時 `solution`、失敗時 `hipBLAS, no solution`。reader 終了時にも `vit-lt: %llu hipBLASLt products, %llu by hipBLAS\n` を出す（`tools/vision/own/vit_gpu.cu:572-575, 617-618`）。hipBLASLt の積そのものが失敗したときは `vit-lt: the hipBLASLt product failed (m=%d n=%d k=%d batch=%d); hipBLAS from now on for this shape\n` を stderr に出す。hipBLASLt handle / workspace の初期化失敗では `vit-lt: hipBLASLt is not usable here; hipBLAS for every product\n` を出す（`tools/vision/own/vit_gpu.cu:584-589, 601-610`）。

この設定の solution ID ごとの性能測定値は、`docs/DETAILS.md` および該当ソース内で条件付きの形では確認できなかったため記載しない。

## 根拠

- 全参照と読み取り: `tools/vision/own/vit_gpu.cu:485-487, 594-600`。候補名の他の参照はコメントのみ。
- ビルド条件: `tools/vision/own/CMakeLists.txt:127-137`。
- solution の指定、shape ごとの判定と fallback: `tools/vision/own/vit_gpu.cu:525-576, 578-592, 748-770`。
- own GPU reader のロードと encode 経路: `tools/vision/own/own_reader.cpp:114-125, 141-165, 190-194`。
