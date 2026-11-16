# `STRATA_SYCL_GR_LO_ONCE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の fused hyper-connection read で、down projection の分割 reduce 中に low-rank SiLU 値を一度計算して出力先 `lo` に書き、後続 up projection がその値を再利用する経路を選びます。SYCL 実装の `fused_gr_read_multi` にだけこの環境変数の読み取りがあります。CUDA 側の `src/kernels/cuda/fused_gr.cu` には同名の読み取りがないため、CUDA 実装での効果は確認できません（SYCL 実装: `sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1153,3359-3360,3392-3395,3485-3486`）。

この設定で変わるのは low-rank 値を計算・再利用するカーネル経路です。コードから生成 token の同一性や速度差は確認していません。

## 値と判定

グローバル変数 `g_gr_lo_once` の初期化時に `std::getenv` で取得し、`std::atoi(value) != 0` で判定します。`atoi` の結果が 0 なら無効、0 以外なら有効です。文字列全体の数値検証はなく、`atoi` が数値として読める先頭部分で判定されます。空白、大文字小文字、`true`/`false` を別扱いする処理はありません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1152`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL fused GR | false | `1`, `2`, `-1`, `1junk` | 空文字, `0`, `0anything`, `true`, `junk` |

未設定は `getenv` が null となり false、空文字や数値に変換できない文字列は `atoi` が 0 を返して false です。負の非ゼロ値も有効です。数値の後ろは検査されないため、`1junk` は有効、`0anything` は無効です。値域の clamp や fallback はありません。`atoi` で `int` に表現できない値の扱いは Strata 側で規定していません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1152`）。

## 有効になる条件

- SYCL の fused GR 実装がビルドされ、`fused_gr_read_multi` が実行されること。この変数の読み取り箇所は `sycl/src/kernels/cuda/fused_gr.dp.cpp` にあります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1153,3139-3141`）。
- `STRATA_GR_DOWN_SLICED` が未設定、または `atoi` の結果が非ゼロであること。明示的に 0（例: `0`, `0junk`）なら `gr_down_sliced()` が false となり、この変数が作る `lo_once` も false です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:834-837,3359-3360`）。
- スライス経路であること。`lo_once` は sliced down のときだけ true になり、false の場合は直接 down、または tiled down の経路に進みます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3359-3360,3365,3411-3416`）。
- `STRATA_GR_MORE_GROUPS` が有効な場合、`lo_once` が false なら more-groups down/up 経路が選ばれますが、true ならその経路を避けて通常の sliced down/reduce と prepared-lo up に進みます。`STRATA_GR_MORE_GROUPS` の未設定時既定値は Intel Alchemist 世代で true、それ以外で false です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:820-832,3360-3365,3485-3492`）。
- `STRATA_PRIVATE_GR_F32_REG` などで有効になる GF 経路が down/up を担当する場合、GF の phase 条件によって通常の reduce または up 分岐が置き換わり、この変数の経路が実行されないことがあります。GF 経路の有効条件は 1〜4 token、sliced down、`!gr_more_groups`、`!gr_large_grf`、`gr_norm_split()`、`gr_up_cols()==16`、ILP 無効、Battlemage です。phase は `STRATA_PRIVATE_GR_F32_PHASE` の未設定または `both`、`down`、`up` で選びます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2692,3368-3394,3467-3486`）。
- 別経路として、`STRATA_SYCL_GR_CACHED_NORM=3` で `cached_norm` 条件も満たす場合、`cached_norm` と mode 3 によって `lo_once` が成立し得ます。この場合も sliced down が必要です。`cached_norm` は GF が無効、norm direct bounds と norm split が有効、さらに `gr_cached_norm_safe(...)` が true の場合に限られます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79,85-99,3298-3300,3359,3471-3484`）。

## 実行時の詳細

`g_gr_lo_once` は関数内 static ではなく、翻訳単位のグローバル変数として初期化されます。環境変数はプロセス起動時のグローバル初期化で一度読み取られ、その後プロセス内で環境を変更してもこの値には反映されません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1152`）。

`fused_gr_read_multi` は入力を検証し、norm の後に sliced down を選ぶと、`lo_once` の値に従って more-groups を回避します。標準の sliced down kernel が partials を作り、reduce kernel は各 low-rank 行について部分和を `m.part` に保存するとともに `v = x / HC` と `v / (1 + exp(-v))` を `lo` に書きます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:739-771,775-806,3359-3365,3370-3395`）。

その後 `launch_gr_up_prepared_lo` が `m.cached_lo = true` として up kernel を起動し、reduce が用意した `lo` を読む経路にします。したがって、再利用が適用されるのは fused GR の down/reduce と up の間です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1153-1165,3485-3486`）。

## ログと測定値

この変数の値を示すログや、値を拒否するエラーはありません。切り替えだけで stderr/stdout に出力する処理もありません。fused GR read の一般的な入力検証失敗では `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を stderr に出して `exit(1)` しますが、これは本変数の値に対する失敗ではありません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3142-3155`）。この変数について条件付きの測定値は確認できません。

## 根拠

- 読み取り・変換・初期化時期: `sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1152`
- down reduce による low-rank 値の生成: `sycl/src/kernels/cuda/fused_gr.dp.cpp:775-806,3392-3410`
- sliced / more-groups の条件と up 分岐: `sycl/src/kernels/cuda/fused_gr.dp.cpp:820-837,3359-3365,3465-3492`
- prepared-lo up kernel: `sycl/src/kernels/cuda/fused_gr.dp.cpp:1153-1165`
- 読み取り関数と入力エラー経路: `sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3155`
