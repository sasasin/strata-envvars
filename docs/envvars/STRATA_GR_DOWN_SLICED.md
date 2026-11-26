# `STRATA_GR_DOWN_SLICED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 fused GR の multi-token read における down projection の方式を選ぶ。未設定時は sliced down kernel と reduction kernel を使う。0 と判定される値では `STRATA_GR_DOWN_DIRECT` を続けて判定し、既定では direct kernel、そちらも無効なら local-memory 容量に応じて token を分割する tiled kernel を使う。値を読む実装は `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` の `gr_down_sliced()` である（同 834-850、3343-3347、3360-3415 行）。

## 値と判定

関数内 `static const bool` の初期化で `std::getenv` を調べ、設定されていれば `std::atoi(...) != 0` を使う。未設定だけが sliced を既定で有効にする。空文字は `atoi` が 0 を返すため無効。数値文字列全体の検証はなく、`atoi` が先頭から変換できる整数部分で判定する（例: `0anything` は無効、`1anything` と `-1` は有効、`true` は無効）。先頭の空白の後の数字も変換される。範囲チェックや clamp はない。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-836`。

| 条件 | unset | 設定時に sliced が有効 | 設定時に sliced が無効 |
|---|---|---|---|
| SYCL fused GR の down 分岐 | 有効 | `atoi` の結果が 0 以外（例: `1`, `-1`, `1tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0tail`, `true`） |

## 有効になる条件

- Strata の SYCL engine を使うこと。SYCL build は `fused_gr.cu` に対する migrated copy として `fused_gr.dp.cpp` を source resolution して `strata_kernels` に含める（`engine/sycl/CMakeLists.txt:273-286`、140-159）。この環境変数を読む同等の CUDA/HIP 実装は確認できない。
- fused GR が選ばれること。起動時の設定では `o.gr_native_mmvf` が真で、`--no-fused-gr`、GPU stage、layer/half dump、stage timing の各条件に該当しない場合に fused GR を有効にする（`engine/sycl/src/program/generate.cpp:3221-3228`）。対象 geometry も `fused_gr_supported()` の条件を満たす必要がある（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`、呼び出し側 `engine/sycl/src/core/layer.cpp:1558-1559`）。
- `STRATA_GR_V3` が有効で、その device の local-memory 判定で split 1 が選ばれると、`fused_gr_read_multi()` はこの変数の down 分岐に到達する前に V3 kernel を実行して戻る。V3 は未設定または `atoi` が 0 なら無効。V3 の split が選べない場合は通常の down 分岐に進む（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202`、3294-3297）。
- 値が 0 の場合は `STRATA_GR_DOWN_DIRECT` が次の選択条件になる。同変数は未設定時または `atoi` が非 0 のとき direct kernel を選び、0 のとき tiled kernel を使う（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:848-850`、3411-3463）。このため sliced を無効にしただけでは tiled kernel にはならない。

## 実行時の詳細

`gr_down_sliced()` は関数内 static に判定結果を保持するため、プロセスで最初に呼び出された時の環境を使い、その後の環境変更は反映されない。device ごとの値ではない。fused GR の単一 read は、hidden 幅が single-token down kernel の local-memory 条件を超える場合、または `gr_down_sliced()`、norm split、down direct のいずれかが有効な場合に scratch を用意して `fused_gr_read_multi(..., 1, ...)` に委譲する。したがって sliced の既定有効時は単一 token も multi-token 実装を通る（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3510-3533`）。

multi-token 実装では sliced が有効なら、sliced down kernel と partial sum の reduction を起動する。`gr_more_groups()` が有効で low-rank 値の一括処理条件を満たす場合は、そのための sliced kernel variant を使う。sliced が無効なら direct kernel、または device local-memory から求めた `chunk_tok` に応じた tiled kernel を起動する（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3343-3358`、3360-3415、3416-3463）。

この変数専用のログや警告はない。multi read の引数が不正な場合は stderr に `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を出して `exit(1)` するが、これは環境変数の値を理由とするエラーではない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3155`）。

## 根拠

- 読み取り、既定値、static cache: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-836`
- sliced kernel と fallback の選択: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3343-3358`、`3360-3415`
- tiled kernel の chunking: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3416-3463`
- V3 の早期経路: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202`、`3294-3297`
- single-token read の委譲: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3510-3533`
- fused GR の起動条件: `engine/sycl/src/program/generate.cpp:3221-3228`、`engine/sycl/src/core/layer.cpp:1558-1559`
