# `STRATA_GR_Q8_UP_MODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。調査開始時の作業ツリーに未コミット変更はない。

## 役割

ハイパーコネクション（HC）の Q8_0 up projection で、列を 16 分割する経路を選んだときの kernel を切り替える。内部値が `2` のときだけ `gr_up_q8_split_v2_kernel<T, 16>` を使い、それ以外は `gr_up_q8_split_kernel<T, 16>` を使う（`engine/src/kernels/cuda/fused_gr.cu:4003-4006`、同 `:4033-4042`）。どちらも up projection の式（`rs`・`w_norm` の適用、SiLU、HC 平均）は同じで、正規化と混合の実行位置、および丸めの指定が異なる。down projection、attention、モデル選択には関与しない。`docs/NVIDIA_V100.md:51` は `2` を "pre-normalized up projection" と呼び、unfused Q8_0 HC kernel と bit-exact としている。

## 値と判定

`std::getenv("STRATA_GR_Q8_UP_MODE")` の戻り値に `std::atoi` をかけ、結果が `2` と等しいかだけを見る（`engine/src/kernels/cuda/fused_gr.cu:4003-4006`）。文字列全体の比較ではなく、先頭の整数を読む。`2` の後ろに文字が続いても無視し、大文字小文字・空白・数値としての妥当性の検査はない。`atoi` は先頭の空白を読み飛ばす。`2` 以外はすべて内部値 `1` になる。無効値を警告するコードはない。

| build / 条件 | 未設定時 | 内部値が 2 になる入力 | 内部値が 1 になる入力 |
|---|---|---|---|
| CUDA・全可視 GPU が sm_70・既定表 ON | `nv_defaults` が `2` を設定（`engine/src/core/nv_defaults.cpp:158`） | `2`, `02`, ` 2`, `+2`, `2x`, `2.9` | 空文字, `0`, `1`, `3`, `true`, `-2` |
| 上記以外の CUDA | `1` | 同上 | 同上 |
| HIP / Metal | `1`（既定表は適用されない） | なし（`2` を選ぶ分岐が無い） | すべて `1` と同じ |

空文字は「未設定」ではなく「設定あり」として扱われ、sm_70 の既定表も上書きする（`engine/src/core/nv_defaults.cpp:228`）。その場合の内部値は `1`。同名の CLI 引数はなく、値は環境変数と sm_70 既定表だけで決まる。

## 有効になる条件

- CUDA build で `__HIPCC__` が定義されていないこと。v2 kernel は `#if !defined(__HIPCC__)` の内側にあり（`engine/src/kernels/cuda/fused_gr.cu:3019-3251`）、16 列分割の呼び分けも non-HIP 側にだけある（同 `:4037-4042`）。
- HC の Q8_0 read が選ばれ、`q8_down` と `q8_up` が非 null であること（`engine/src/kernels/cuda/fused_gr.cu:4284`）。`STRATA_HC_Q8` が有効で、GGUF が HC projection を Q8_0 で持つか loader が量子化した場合に成立する（`engine/src/core/native_dense.cpp:48-99`）。
- 手前の Tensor Core 経路が無効なこと。`hc_q8_tc_mode()` は `STRATA_HC_Q8_TC=0` か sm_80 未満で 0、`hc_q8_bf16tc_mode()` も `STRATA_HC_Q8_BF16TC=0` か sm_80 未満で 0 を返す（`engine/src/kernels/cuda/fused_gr.cu:3902-3923`、同 `:3943-3955`）。両方が 0 なら `up_mode` の読み取りまで到達する（同 `:3962-3988`）。sm_70 では両方とも 0 になる。
- `STRATA_TSUM` が 0 以外の非負値であること。未設定・負値では既定に戻り、sm_80 以上では ON、sm_70 では既定表の `STRATA_TSUM=1` が効く（`engine/src/kernels/cuda/fused_gr.cu:3926-3940`、同 `:4007`、`engine/src/core/nv_defaults.cpp:145`）。`ts` が偽なら `gr_up_q8_kernel` が走り、この変数の分岐は使われない（同 `:4052`）。
- `STRATA_GR_Q8_UP_COLS` が `16` であること。許容値は `16/8/4/2` だけで、それ以外と未設定は `0` になる（`engine/src/kernels/cuda/fused_gr.cu:3998-4002`）。sm_70 の既定表は `16` を設定する（`engine/src/core/nv_defaults.cpp:157`）。`0` や `8/4/2` では mode 2 の分岐に入らない（同 `:4033-4046`）。
- トークン数 1〜8 のすべてで同じ選択になる（`launch_q8_t<1>`〜`<8>`、`engine/src/kernels/cuda/fused_gr.cu:4054-4066`）。
- `docs/SETTINGS.md:94` は対象を "NVIDIA and AMD" とするが、`2` を選ぶ分岐は HIP 側に存在しない。HIP では値を読んでも効果がない。

## 実行時の詳細

既定表は起動時に一度だけ適用される。`generate.cpp` は全可視 CUDA デバイスの compute capability が一致したときだけ `apply_nv_defaults` を呼び、その中で sm_70 なら `STRATA_GR_Q8_UP_MODE=2` を設定する（`engine/src/program/generate.cpp:4416-4443`、`engine/src/core/nv_defaults.cpp:136-163`）。`apply_nv_defaults` は既に `getenv` が非 null の変数を飛ばし（`:228`）、`setenv(..., 0)` で設定する（`:232`）ので、利用者が設定した値（空文字を含む）が常に優先する。`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` のときは sm_70 の表全体が適用されない（`:140`）。

読み取りは `launch_q8_t<T>` の関数ローカル `static` で、その `T` の初回呼び出し時に一度だけ行われる（`engine/src/kernels/cuda/fused_gr.cu:4003`）。同じ `T` では実行中の環境変更が反映されない。まだ呼ばれていない `T` は変更後の値を読む。リクエストごとの再読み取りはない。Tensor Core 経路が先に `return` する間は、この `getenv` 自体が実行されない（`:3962-3988`）。

`launch_q8` はトークン数に応じて `launch_q8_t<1>`〜`<8>` を選ぶ（`:4054-4066`）。down projection の後、`ts` が真で `up_cols==16` なら `gr_mid_q8_kernel` を実行し、`up_mode==2` なら v2、そうでなければ v1 を `N/16` ブロック・256 スレッドで起動する（`:4032-4042`）。v2 は dot の結果 `sigmoid(mine)` だけを共有メモリ `g` に保存し（`:3203-3205`）、`rv*w_norm*rsS` の適用と HC 平均を dot ループの外へ移して `__fmul_rn`/`__fadd_rn` で計算する（`:3207-3225`）。v1 は owner lane が正規化を済ませた値を `g` に保存する（`:2997-3013`）。v2 は `lo` を float4 で読み込む（`:3155-3160`）。この名前を読む箇所は Strata 内でこの 1 か所だけである。

## ログと測定値

変数の値自体を表示するログ・警告はない。無効値も無言で `1` になる。sm_70 の既定表が適用されたときだけ、起動時に stderr へ switch 名を並べた行が出る。書式は `strata: sm_70 (Volta): <N> exact speed switches on by default (STRATA_SM70_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ... GR_Q8_UP_MODE ...` で、名前は `STRATA_` を除いた形で表示される（`engine/src/core/nv_defaults.cpp:247-253`）。利用者がこの変数を設定した場合は一覧に含まれない（`:228`）。

`docs/NVIDIA_V100.md:51` は `STRATA_GR_Q8_UP_MODE=2` が unfused Q8_0 HC kernel と bit-exact であると記載する。本調査では build・GPU 実行・テストを行っていないため、この主張を独自には確認していない。本変数固有の速度値は参照した資料に記載がない。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:4003-4006` — `getenv` と `atoi(v)==2` による値の決定。
- `engine/src/kernels/cuda/fused_gr.cu:4033-4046` — `up_cols==16` と `up_mode==2` による v2 / v1 の呼び分け。
- `engine/src/kernels/cuda/fused_gr.cu:3138-3229` — v2 kernel の保存・正規化・混合。
- `engine/src/core/nv_defaults.cpp:136-163` — sm_70 の既定表と `STRATA_GR_Q8_UP_MODE=2`。
- `engine/src/core/nv_defaults.cpp:227-253` — 利用者設定の優先、sm_70 の起動ログ。
- `engine/src/program/generate.cpp:4416-4443` — 既定表の適用条件と時期。
- `docs/NVIDIA_V100.md:51`、`docs/SETTINGS.md:94` — 資料側の記述と対象 backend の差。
