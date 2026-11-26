# `STRATA_GR_DOWN_DIRECT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 実装の fused hyper-connection（GR）複数 token 読み取りで、down 投影に direct kernel を使うかを選ぶ。値が有効なら `gr_down_multi_direct_kernel` を起動し、無効なら local memory の容量に応じて tiled kernel を一括または分割起動する。ただし `STRATA_GR_DOWN_SLICED` が有効な間は sliced kernel の分岐が先に選ばれるため、この変数は down kernel の選択を変えない。読み取り関数は `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` の `gr_down_direct()`（同ファイル:848-851）、選択箇所は同:3360-3435。

この参照は SYCL ソースにのみあり、CUDA/HIP/Metal 用実装の同名読み取りはない。通常の生成で fused GR を使うには、`--gr-native-mmvf` または `--native` 等によって `gr_native_mmvf` が有効で、`--no-fused-gr` がなく、GPU stages・layer dump・half dump・stage timing を使わないことが必要（`engine/sycl/src/program/generate.cpp:1952,2209,2593,3221-3228`）。さらに fused 対象 shape で、`stage_prefix == 0` かつ `half == 0` の呼び出しである必要がある（`engine/sycl/src/core/layer.cpp:1558-1559,1620-1629,1643-1652`）。

## 値と判定

`std::getenv` で存在を調べ、設定されていれば `std::atoi` の結果が 0 以外かを判定する。文字列全体の検証はなく、`atoi` が数値として読めない先頭は 0 になる。先頭の空白と符号付き整数の形式が読まれ、整数の後ろの文字列は判定に使われない。未設定だけは `true`。空文字は設定済みで `atoi("") == 0` となり `false`。（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:848-851`）

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `gr_down_sliced()` が false のとき | direct が有効 | `1`, `-1`, `2tail`, ` 1` | `0`, `-0`, `true`, `0anything`, 空文字 |
| `gr_down_sliced()` が true のとき | down kernel 選択への影響なし | 上と同じ判定結果だが sliced 分岐が先行 | 上と同じ判定結果だが sliced 分岐が先行 |

`atoi` の整数表現範囲を超える値について、C/C++ の変換結果はこのコードでは制限・検査されないため、文書上の有効値として定めない。別の CLI 引数による値の上書きはない。関連する独立スイッチ `STRATA_GR_DOWN_SLICED` は未設定または `atoi` が非 0 なら true であり、0 にするとこの変数による分岐に進む（同:834-836）。

## 有効になる条件

- SYCL backend の fused GR 実装がビルドに含まれ、実行経路で `fused_gr_read_multi()` が呼ばれること。この名前の読み取りは SYCL 実装内だけにある（`engine/sycl/CMakeLists.txt:46,276`）。
- fused GR が有効で、対象 shape（`n_embd == N`, `hc == HC`, `hc_lr == LR`）に合うこと。fused GR は `--gr-native-mmvf` が有効、`--no-fused-gr` なし、GPU stages・layer/half dump・stage timing なしのときに有効化される（`engine/sycl/src/program/generate.cpp:3221-3228`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`; `engine/sycl/src/core/layer.cpp:1558-1559`）。
- `STRATA_GR_DOWN_SLICED` が unset または `atoi` 非 0 の場合、この変数による direct/tiled の切替は使われない。`STRATA_GR_DOWN_SLICED=0` の場合、`STRATA_GR_DOWN_DIRECT` が unset または `atoi` 非 0 なら direct、0 なら tiled に進む（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-850,3360-3416`）。
- 単一 token の `fused_gr_read()` では、`kDownXnTooBig`、`gr_down_sliced()`、`gr_norm_split()`、`gr_down_direct()` のいずれかが true のときだけ multi read に委譲する。したがって sliced と direct の両方を 0 にしても、norm split と大きすぎる Xn の条件がなく、`gr_norm_split()` も false なら、この単一 token 経路ではこの変数による kernel 切替は実行されない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3522-3533`）。
- direct が無効で tiled に進んだ場合だけ、デバイスの local memory から計算した token chunk 数に応じて一括 kernel または chunk ごとの kernel が選ばれる（同:3348-3358,3416-3463）。

## 実行時の詳細

各判定関数内の `static const bool` が初回呼び出し時に一度評価され、そのプロセス内の後続呼び出しは値を cache する。したがって実行中に環境を変更しても再評価されない。起動引数・設定ファイルによる再設定経路は見つからなかった（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-851`）。

複数 token の GR 読み取りでは、まず sliced + more-groups、次に sliced kernel、次に direct kernel、最後に tiled kernel を判定する。direct kernel は `DOWN_BLOCKS * DOWN_SPLIT + 1` work-group 構成で `gr_down_multi_direct_kernel(m)` を起動する。tiled kernel は `chunk_tok >= n_tok` ならまとめて起動し、そうでなければ `chunk_tok` ごとに分割して起動する（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3343-3358,3360-3463`）。1 token の `fused_gr_read()` も、sliced/direct などの経路では scratch を用意して `fused_gr_read_multi(..., 1, ...)` に委譲する（同:3510-3533）。

down 投影の kernel 選択を変える環境変数である。ソースコメントは `STRATA_GR_DOWN_DIRECT=0` で tiled kernel を選ぶとし、`gr_bench` の 3–6 token で 13–19% 遅いと記すが、対象機器・実行条件・測定回数がこのコメントにないため、一般的な性能値としては扱えない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:848-850`）。

## ログと測定値

この変数の値や direct/tiled 選択を通知する専用ログ・警告は見つからなかった。`fused_gr_read_multi()` は不正な token 数や null scratch、各 token の不正・不整合な引数で stderr に `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を出して `std::exit(1)` するが、これは環境変数値に対する検証ではない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3155`）。SYCL 例外は layer 側の catch で例外文と位置を stderr に出して終了コード 1 となる（`engine/sycl/src/core/layer.cpp:1665-1669`）。

コードコメントにあるベンチマーク数値は、条件が不足しているため上記以外の性能・速度差を示す測定値としては記載しない。`docs/DETAILS.md` と `docs/A770_SPEED_SPEC.md` にこの変数固有の動作や条件を追加説明する記述は見つからなかった。

## 根拠

- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-851` — sliced/direct の値判定と cache。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3155` — fused multi read の引数検証と失敗時終了。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3343-3463` — local memory に基づく tiled chunk、優先順位、kernel 起動。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3533` — shape 判定と単一 token 読み取りからの委譲。
- `engine/sycl/src/program/generate.cpp:1952,2209,2593,3221-3228` — CLI と fused GR の有効化条件。
- `engine/sycl/src/core/layer.cpp:1558-1559,1620-1629,1643-1652,1665-1669` — layer からの呼び出しと SYCL 例外処理。
- `engine/sycl/CMakeLists.txt:46,276` — SYCL kernel ソースと fused_gr 機能の登録。
