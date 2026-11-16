# `STRATA_SYCL_GR_CACHED_NORM`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 版 fused hyper-connection (GR) の複数 token 読み取りで、正規化済み activation を `xn_scratch` に書き、後段の up kernel で再利用する実験経路を選ぶ。通常の down/reduce/up 分割に比べ、up 側で同じ正規化 activation を再計算する代わりに保存値を使う。値が `3` でも単独で有効にはならず、後述の bounds/split/down 設定と scratch・出力ポインタの安全条件がすべて必要である。実装は `sycl/src/kernels/cuda/fused_gr.dp.cpp` のファイルスコープ初期化と `fused_gr_read_multi` にある（76-79, 3298-3323, 3471-3484）。

この名前を読むのは SYCL 側の移植カーネルだけで、通常の CUDA/HIP 実装 `src/kernels/cuda/fused_gr.cu` には参照がない。SYCL build は `fused_gr.cu` の移植先 `sycl/src/kernels/cuda/fused_gr.dp.cpp` を `strata_kernels` に解決して組み込む（`sycl/CMakeLists.txt:240-255`）。

## 値と判定

ファイルスコープの初期化時に `std::getenv` で値を読み、`std::atoi(e) == 3` のときだけモードを `3`、それ以外は `0` にする。初期化は一度だけで、後からプロセス環境を変更しても再評価されない（`sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL カーネルが組み込まれたプロセス | モード `0` | `3`, `03`, `+3`, ` 3`, `3suffix`, `3.0`（`atoi` が先頭の整数部分を `3` と読む文字列） | 空文字、`0`, `1`, `2`, `-3`, `4`, `true`, `  x` |

全体一致ではなく `atoi` なので、前後の空白や符号、整数の後ろの文字列を検査しない。空文字・非数値文字列は `atoi` の結果が `0` になり、無効である。大小文字による判定はない（数値変換のみ）。この実装では `1` や `2` を段階的な有効値として扱わず、`3` 以外はすべて同じ無効モード `0` になる（同ファイル `76-79`, `3298-3299`）。

## 有効になる条件

値が `3` で、以下をすべて満たす場合に限り `cached_norm` 経路を選ぶ（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3299`）。

- SYCL build の fused GR `fused_gr_read_multi` が呼ばれること。通常の生成経路では `--gr-native-mmvf` が有効で、`--no-fused-gr`、GPU stage、layer/half dump、stage timing が無効である必要がある（`sycl/src/program/generate.cpp:3141-3150`）。モデル/API・verify 経路から同関数が呼ばれる場合も対象だが、通常の fused GR 経路が選ばれなければこの変数は使われない。
- `STRATA_PRIVATE_GR_F32_REG` による `gf_enabled` 経路が有効でないこと。同経路が有効なら `cached_norm` は false になる（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689, 3298`）。
- `STRATA_SYCL_GR_NORM_BOUNDS` の先頭文字が `'1'` であること。`getenv` した値の `value[0]` だけを見るため、未設定・空文字・`true`・先頭が `1` でない値は無効、`1` や `1suffix` は有効（同ファイル `569-572, 3324-3327`）。
- `STRATA_GR_NORM_SPLIT` が未設定、または `atoi` の結果が非ゼロであること。未設定時は有効、空文字・`0`・`0suffix` は無効。先頭整数が非ゼロなら後続文字は検査しない（同ファイル `574-577`）。
- `STRATA_GR_DOWN_SLICED` が未設定、または `atoi` の結果が非ゼロであること。値の判定は上記 split と同じ（同ファイル `834-836`）。
- `gr_cached_norm_safe` が true であること。`apply` が true の token について、`R_out` が存在し16-byte境界に整列し、`xn_scratch`、入力 `R`、他 token の出力、および weights・各出力領域と重ならない必要がある。いずれかの検査に失敗するとこの経路を使わない（同ファイル `85-105`）。

上記の変数条件を満たさない場合、通常の bounds kernel または split/non-split の norm kernel を選ぶ（同ファイル `3320-3340`）。また、SYCL 専用コードではない通常の CUDA/HIP build にはこの読み取り自体がない。

## 実行時の詳細

`fused_gr_read_multi` は引数と token ごとの必要ポインタを先に検査し、無効なら `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を stderr に出して `exit(1)` する。その後、対象変数と他の条件から `cached_norm` を決め、norm 段で `gr_norm_cached_write` kernel を起動する（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159, 3298-3327`）。

down/reduce の結果を up 段で使う際、cached norm kernel は保存された正規化 activation を `m.xn` から読み、各出力を計算する（同ファイル `932-976, 994-1020`）。モード `3` は `lo_once` も有効にするため、down reduce が作った low-rank SiLU 値を一度保存し、`gr_up_compact_ready` kernel を選ぶ（同ファイル `3359, 3471-3484`）。これらは同じ `fused_gr_read_multi` 呼び出しのカーネル選択であり、変数値をリクエストごとに読み直す処理ではない。ファイルスコープのモード値はプロセス内で一度だけ読み取られる。

`STRATA_GR_CACHED_NORM` は別の Battlemage 向け reuse helper に渡される名前であり、この変数とは別物である。helper は明示値が空でなければ先頭文字が `'0'` 以外を on とし、unset/空なら Battlemage では既定 on だが、この再利用分岐は `cached_norm` が false のときだけ評価される（`sycl/include/strata/sycl_queue.hpp:159-166`, `sycl/src/kernels/cuda/fused_gr.dp.cpp:3301-3314`）。したがって対象変数の mode 3 が安全条件を満たす呼び出しでは、その Battlemage reuse 分岐を選ぶことはない。

## ログと測定値

対象変数の mode 3 による cached norm / compact up の選択を直接知らせるログはない（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3323, 3471-3484`）。隣接する Battlemage reuse 分岐の `strata: GR reuse enabled: normalized activation %d, low-rank SiLU %d` は `cached_norm` が false の場合に限って出るので、対象変数の cached norm 選択ログではない（同ファイル `3301-3314`）。

`docs/A770_SPEED_SPEC.md:661-664` には fused GR read 全般の測定があるが、この環境変数や cached norm 経路を条件にした測定ではないため、本変数の速度・正確性の測定値としては記載しない。

## 根拠

- 読み取り・値変換・一度だけの初期化: `sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79`
- 安全条件: `sycl/src/kernels/cuda/fused_gr.dp.cpp:85-105`
- 有効条件と norm kernel 選択: `sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3340`
- down/reduce と `lo_once` / up kernel 選択: `sycl/src/kernels/cuda/fused_gr.dp.cpp:3359-3410, 3465-3493`
- cached norm を up kernel で使う処理: `sycl/src/kernels/cuda/fused_gr.dp.cpp:932-976, 994-1020`
- 通常生成での fused GR 条件: `sycl/src/program/generate.cpp:3141-3150`
- SYCL kernel build 登録: `sycl/CMakeLists.txt:240-255`
