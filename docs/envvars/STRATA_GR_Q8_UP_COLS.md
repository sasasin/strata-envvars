# `STRATA_GR_Q8_UP_COLS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

ハイパーコネクション（HC）読みの Q8_0 アップ射影で、1 ブロックが受け持つ出力列数 `d` を選ぶ。値は `launch_q8_t<T>` が読み（engine/src/kernels/cuda/fused_gr.cu:3998-4002）、アップ側のカーネルと起動グリッドだけを変える。

- `16`: `gr_mid_q8_kernel` で `rs` と `lo` をトークンごとに一度だけ計算し、`gr_up_q8_split_kernel<T,16>`（`N/16` = 160 ブロック）で `mixed` を書く。`STRATA_GR_Q8_UP_MODE=2` のときだけ `gr_up_q8_split_v2_kernel<T,16>`（正規化の積を列ごとに 1 回）に替わる（fused_gr.cu:4036-4042, 3138-3229）。
- `8` / `4` / `2`: `gr_mid_q8_kernel` + `gr_up_q8_split_kernel<T,UCOLS>`。グリッドは `N/8`=320、`N/4`=640、`N/2`=1280 ブロック（fused_gr.cu:4044-4046）。
- `0`（未設定・無効値）: 従来の `gr_up_q8_fast_kernel<T,false>`（`UPM_COLS=16` で 160 ブロック）のみ。mid カーネルは走らない（fused_gr.cu:4047, 4050, 404-405）。

ダウン射影の選択（`STRATA_GR_Q8_DOWN_MODE`）、重み、生成トークンは変えない。変わるのは `m.a[k].mixed` を書くカーネル、起動グリッド、`STRATA_QFUSE` の q8_1 tail を書く単位である。

## 値と判定

`std::getenv` の有無ではなく値を読み、`std::atoi` した整数が `16` / `8` / `4` / `2` のときだけ採用する。それ以外は 0（未設定と同じ扱い）に落ちる（fused_gr.cu:3998-4002）。

- 空文字と非数値（`on`、`true`）: `atoi` が 0 を返すので未設定と同じ。
- 数値の後ろは無視（`16abc` → 16、`16.9` → 16）。`atoi` なので先頭の空白と符号は解釈され（` 16`、`+16`）、`0x10` は 0、`016` は十進の 16。大文字小文字を見る判定は無い。
- `0`、`1`、`32`、`-16` は 0 に落ちる。clamp も代替値も無く、警告も出ない。結果は未設定と同じ `gr_up_q8_fast_kernel` になる。

| 条件 | 未設定・空文字・無効値 | 有効値（16 / 8 / 4 / 2） |
|---|---|---|
| CUDA sm_80 以上（`STRATA_HC_Q8_TC` / `STRATA_HC_Q8_BF16TC` 既定） | 値は読まれない（TC / BF16TC 経路が return） | 値は読まれない |
| CUDA で TC / BF16TC 経路が成立しない（sm_70 など、または両方 `=0`） | 0: `gr_up_q8_fast_kernel`（`ts` が真のとき） | 16 は mid + split、8/4/2 は mid + split（列数だけ違う） |
| HIP 非 gfx906 | `STRATA_TSUM` 未設定なら値は未使用 | `STRATA_TSUM` 非 0 のとき上と同じ |

## 有効になる条件

- **Q8_0 の HC 重みで読みが走ること。** `q8_down` と `q8_up` が非 null のときだけ `launch_q8` が呼ばれる（fused_gr.cu:4284-4285）。Q8_0 の HC 射影を積むのは `STRATA_HC_Q8=1`、または CUDA でファイルが Q8_0 の HC 射影を持つ場合の既定（native_dense.cpp:683-691、generate.cpp:5164-5168）。
- **`ts` が真であること。** `STRATA_TSUM` 未設定なら `hc_q8_sm80_fast()` の値で、compute capability 8 以上のみ真。sm_70 では `STRATA_TSUM=1` が要る。`STRATA_TSUM=0` は明示的に偽で、アップは `gr_up_q8_kernel` になり値は使われない（fused_gr.cu:4007, 4052）。
- **CUDA では上流の早期 return を抜けること。** `hc_q8_tc_mode` と `hc_q8_bf16tc_mode` は sm_80 以上で既定 1 を返し、ダウン + アップを別カーネルで済ませて return する（fused_gr.cu:3962-3988）。sm_80 以上でこの変数を効かせるには `STRATA_HC_Q8_TC=0` と `STRATA_HC_Q8_BF16TC=0` が要る。TC 経路はさらに `LR % 32 == 0` などを要求するが、コンパイル時定数 `LR=320`、`Q8_KC=640` で成立する。
- **HIP では q32 経路を外すこと。** 非 gfx906 の HIP ビルドは `q8_mixed` 非 null かつ `qfuse_hc_local()` が真（`STRATA_QFUSE_HC_LOCAL` 未設定で真）なら `gr_up_q8_q32_kernel` で return する（fused_gr.cu:4022-4031, 1553-1556）。
- **8 / 4 / 2 は q8_1 出力と併用できない。** 分岐条件は `up_cols != 0 && (up_cols == UPM_COLS || m.a[0].q8_mixed == nullptr)` で、`UPM_COLS` は 16（fused_gr.cu:4033, 404）。`STRATA_QFUSE` の q8_1 出力（`q8_mixed`）が非 null のとき効くのは 16 だけで、8/4/2 は `gr_up_q8_fast_kernel` に戻る。
- **16 でも `v2` は `STRATA_GR_Q8_UP_MODE=2` のときだけ。** 未設定・その他の値では `gr_up_q8_split_kernel<T,16>` を使う（fused_gr.cu:4003-4006, 4038-4039）。

## 実行時の詳細

- **読み取り時期と cache。** `launch_q8_t<T>` 内の `static const int` なので、TC / BF16TC の分岐を抜けてその行に初めて到達した時点で一度だけ読み、以後そのプロセスの値は変わらない（fused_gr.cu:3993-4006）。テンプレートなので `T=1..8` の実体ごとに別の static で、トークン数ごとに初回 1 回ずつ読む。プロセス起動後の変更は反映されない。
- **sm_80 以上の既定構成では一度も読まれない。** 早期 return が先に成立するため、この変数を設定しても値の読み取り自体が起こらない。
- **既定値の注入。** 起動時に `apply_nv_defaults` が sm_70 の表を環境へ書き込み、そこに `{"STRATA_GR_Q8_UP_COLS", "16"}` がある（engine/src/core/nv_defaults.cpp:136-163, 222-236、呼び出しは generate.cpp:4420-4443）。ユーザーが既に設定していれば触らない（`std::getenv(kv.first.c_str()) != nullptr` で skip、nv_defaults.cpp:228）。表ごと無効になるのは `STRATA_SM70_PERF=0`、または `STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` のとき（nv_defaults.cpp:139-140、engine/include/strata/core/defaults_026.hpp:22-30）。
- **順序。** 表の適用はモデル読み込み前かつ fused_gr の static 読み取り前なので、既定の `16` がそのまま読まれる。`setenv(..., 0)` は自プロセスの環境を書き換えるため、子プロセスにも継承される。
- **q8_1 tail の単位。** 16 のときは split 側が 16 列単位で書き、`gr_up_q8_fast_kernel` も同じ 16 列単位で書く（fused_gr.cu:3014-3016, 2899）。

## ログと測定値

変数専用のログ・警告は無い（無効値でも何も出ない）。既定で入った場合だけ、起動時の 1 行 `strata: sm_70 (Volta): N speed switches on by default (STRATA_SM70_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ...` の一覧に `GR_Q8_UP_COLS` が `STRATA_` を落とした形で並ぶ（nv_defaults.cpp:247-253）。

docs/NVIDIA_V100.md:51 は sm_70 の「`STRATA_GR_Q8_DOWN_MODE=2` / `STRATA_GR_Q8_UP_COLS=16` / `STRATA_GR_Q8_UP_MODE=2`」の組み合わせを「Bit-exact to the unfused `Q8_0` HC kernels」としている。表全体は nv_defaults.cpp:137-139 が locked-clock の dual V100-SXM2-16GB で 21 個を検証したと記す。この変数単独の速度差を示す数値は資料にもコードにも無い。

## 根拠

- engine/src/kernels/cuda/fused_gr.cu:3993-4006 — 読み取りと受理値（16/8/4/2）、`up_mode`、static cache
- engine/src/kernels/cuda/fused_gr.cu:4032-4052 — 使用分岐、`q8_mixed` 制約、グリッド、既定の fast カーネル
- engine/src/kernels/cuda/fused_gr.cu:4022-4031, 3962-3988 — HIP q32 と CUDA TC / BF16TC の早期 return
- engine/src/kernels/cuda/fused_gr.cu:404, 2902-2933, 2935-3017, 3138-3229 — `UPM_COLS`、mid / split / split_v2 カーネル
- engine/src/core/nv_defaults.cpp:136-163, 222-256 — sm_70 表の `16`、ユーザー設定の優先、起動時ログ
- engine/src/program/generate.cpp:4420-4443, 5164-5168 と engine/src/core/native_dense.cpp:683-693 — 表の適用時期と `STRATA_HC_Q8` の既定
- docs/NVIDIA_V100.md:51, 55-57 と docs/DETAILS.md:1465 — sm_70 表の記載
