# `FNX_PF_F16ACC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

sFNX の prompt prefill 経路で行う一部の FP16 行列積を、FP32 累積・FP32 出力から FP16 累積・FP16 出力へ切り替える。FP16 出力は直後に Strata の kernel で FP32 に変換して後続計算へ渡す。対象は `pf_gemm()` を使う dense GEMM、hyper-connection の down/up GEMM などで、decode 経路全般を切り替える設定ではない。変数は `Engine::prefill_alloc()` が各カード用の状態 `Pf::f16acc` に保存し、`pf_gemm()` と `pf_hc_read()` が分岐に使う（`engine/src/split/src/prefill.cu:391-392,463-479,629-645,854-875`）。

このコードは任意ビルドの `strata-split-N` に属する。通常の Strata 実行ファイル全般に適用される設定ではない（`engine/src/split/CMakeLists.txt:1-7,76-92,116-129`）。コメントは V100 と llama.cpp `COMPUTE_16F` を例に挙げるが、現行コードは split の CUDA/HIP BLAS 呼び出しを通じて設定される。コメントだけから性能、精度、出力 token の同一性は断定できない。 `docs/DETAILS.md` と `docs/SPLIT_ENGINE.md` にこの変数固有の記述や測定値は見つからないため、速度・精度の測定値は記載しない。

## 値と判定

`env_flag(name)` は `env_int(name, 0) != 0`。未設定なら `0`、設定時は符号付き base-10 整数全体を `strtoll` で読み、末尾まで数字（先頭の `+` / `-` は可）で、`long long` 範囲内である必要がある。したがって空文字、空白、数字以外の接尾辞、範囲外は無効値として例外になる。整数として有効な値は `0` だけが OFF、その他は正負を問わず ON。真偽文字列としての解釈や値の clamp はない（`engine/src/split/src/env.hpp:15-21,33-40,51-52`）。

| 条件 | unset | 有効になる値（例） | 無効値・OFF の例 |
|---|---|---|---|
| `strata-split-N` の CUDA または HIP 実行時 | `env_int` の既定値 `0` により OFF | `1`, `-1`, `+2`（整数全体が 0 以外） | `0`, `00` は OFF。空文字、`true`, `1x`, 前後の空白付き値、`long long` 範囲外は parse error |

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` でビルドされ、実行しているのが `strata-split-N` であること。CMake は split を opt-in とし、CUDA/HIP 用に同じ `prefill.cu` をビルドする（`engine/src/split/CMakeLists.txt:1-7,20-27,76-92,116-129`）。
- split engine の `Engine` が構築され `prefill_alloc()` まで到達すること。値は prompt が実際に読まれる時ではなく、engine 構築中に各カードの `Pf` を作る際に読み込まれる（`engine/src/split/src/engine.cu:317-319`; `engine/src/split/src/prefill.cu:854-875`）。
- その後 `pf_gemm()` または `pf_hc_read()` の該当 GEMM 分岐が実行されること。対象の処理を通らない実行では計算への影響はない（`engine/src/split/src/prefill.cu:463-479,623-645,1756-1759`）。
- CLI 引数や別の環境変数でこの値を上書きする処理は確認できない。候補名の全参照は、`prefill.cu` の説明コメントと `env_flag("FNX_PF_F16ACC")` の読み取り箇所のみ。

## 実行時の詳細

`Engine` の構築から `prefill_alloc()` に進み、カードごとに `p->f16acc = env_flag("FNX_PF_F16ACC")` として値を保持する。関数内 static cache ではなく、各カードの `Pf` に構築時の値を保存し、その後の GEMM がその bool を参照する。実行中にプロセス環境を書き換えても、既に作られた `Pf` の値は更新されない（`engine/src/split/src/engine.cu:317-319`; `engine/src/split/src/prefill.cu:391-392,463-479,629-645,854-875`）。

OFF の `pf_gemm()` は入力・重みを FP16 として渡し、FP32 出力バッファと `CUBLAS_COMPUTE_32F` を指定する。ON では同じ FP16 入力に対し、作業領域へ FP16 出力、`CUBLAS_COMPUTE_16F` を指定し、`k_f16_f32` で結果を FP32 に変換する。共有 expert の dense GEMMも `pf_gemm()` を通る。hyper-connection の down/up GEMM も ON 時に FP16 累積・出力へ分岐する。CUDA の down GEMM で cublasLt 経路が利用可能でも、`p.f16acc` が真ならそれを避けて `pf_gemm()` に進む。HIP では該当 cublasLt 分岐自体がコンパイル対象外（`engine/src/split/src/prefill.cu:463-479,481-490,623-645,1756-1759`）。

不正値は helper が `FNX_PF_F16ACC: '<値>' is not a whole number` の `std::runtime_error` を投げる。sfnx の engine 構築失敗処理は stdout に `ERR ...`、stderr に `sfnx: failed: ...` を出し、終了コード 1 で終了する。値を有効化したことを示す専用ログは見当たらない（`engine/src/split/src/env.hpp:33-39`; `engine/src/split/tools/sfnx.cpp:1094-1103,1123-1135`）。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40,51-52` — 整数全体の parse、未設定既定値、flag 判定。
- `engine/src/split/src/prefill.cu:391-392,463-490,623-645,854-875,1756-1759` — 状態保持、各 GEMM 分岐、構築時読み取りと呼び出し。
- `engine/src/split/src/engine.cu:317-319` — engine 構築から prompt buffer 初期化への呼び出し。
- `engine/src/split/tools/sfnx.cpp:1094-1103,1123-1135` — 起動失敗時の標準出力・標準エラーと終了。
- `engine/src/split/CMakeLists.txt:1-7,20-27,76-92,116-129` — split の対象 build と executable。
