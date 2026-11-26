# `STRATA_GFX1151_EXP8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP の grouped native expert 計算で、gfx1151（Strix Halo）の既定 EXP_MODE を 8 にする自動判定を無効化する変数。未設定なら gfx1151 は自動的に mode 8 を選び、この値の先頭文字が `0` なら自動選択を止める。mode 8 では条件を満たす gate/up 層を `native_gu_fused_kernel` に送り、gate/up、SwiGLU、q8_1 量子化を一つの kernel launch にまとめる。変数自身は kernel を強制する設定ではなく、層形式・形状などの条件を満たさなければ fused 経路には入らない（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`, `engine/src/kernels/cuda/iq_kernels.cu:6755-6761,7196-7238`）。

同じ gfx1151 判定は down projection の IQ4_NL（type 20）についても LDS down 経路の可否に使われる。EXP8 が有効なときはこの形式を `lds_down_ok` から除外し、mode に応じた後続経路へ進む（`engine/src/kernels/cuda/iq_kernels.cu:7355-7402`）。

## 値と判定

`hip_exp8_auto_enabled()` は `std::getenv` で値を取得し、文字列を数値・真偽値として parse せず、先頭文字だけを `== '0'` で調べる。gfx1151 では値の先頭文字が `0` の場合だけ、この変数が自動 EXP8 を止める。したがって `0` と `0anything` は無効化し、未設定、空文字、`1`、`true`、`false` や先頭文字が `0` 以外の値は、この変数単独では無効化しない。空白は trim されず、` 0` は無効化値として扱われない（`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-748`）。

| 条件 | unset | EXP8 を有効にする値の例 | EXP8 を無効にする値の例 |
|---|---|---|---|
| HIP build、現在の device が gfx1151、関連する無効化変数なし | 有効 | `1`、空文字、`true`（この変数単独では無効化しない） | `0`、`0anything` |
| gfx1151 で `STRATA_HIP_EXP8=0` または `STRATA_GFX11_EXP8=0` | 無効 | この変数を `1` にしても無効 | いずれかの値の先頭が `0` なら無効 |
| gfx1100/1101/1102/1103/1150（参考: gfx1151 以外の gfx11 WMMA device） | 既定で有効 | `STRATA_GFX1151_EXP8` が未設定または先頭文字が `0` 以外 | `STRATA_GFX1151_EXP8=0`、`STRATA_GFX11_EXP8=0`、または `STRATA_GFX11_DEFAULTS=0` |
| gfx12、RDNA2、非 HIP build、gfx906 | この変数は既定判定を変えない | 該当なし | 該当なし |

gfx1151 以外の gfx11 device でも実装は `STRATA_GFX1151_EXP8` を無効化条件として参照する。gfx1151 自身の分岐では `STRATA_GFX11_DEFAULTS` は見ない。共通の `STRATA_HIP_EXP8=0` は先に判定され、対応 device 全体で無効化する（`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-743`）。

## 有効になる条件

- `engine/src/kernels/cuda/iq_kernels.cu` が HIPCC でコンパイルされ、`STRATA_HIP_GFX906` ではないこと。この条件を外れる build では `gfx1151_exp8()` は常に false を返す（`engine/src/kernels/cuda/iq_kernels.cu:6755-6761`）。
- device 番号が 0〜63 で、`hipGetDeviceProperties()` が成功し、device の arch 名が gfx1151 と一致すること。Arch 名は完全一致（または `:` 区切り suffix）で判定する（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`, `engine/include/strata/kernels/hip_unsloth_wmma.hpp:32-45`）。
- `STRATA_HIP_EXP8` と `STRATA_GFX11_EXP8` が先頭文字 `0` でなく、対象変数も先頭文字 `0` でないこと。
- `STRATA_EXP_MODE` が自動選択を上書きしないこと。`exp_mode()` はこの設定を初回に `atoi` し、結果が 0 以上ならその値を使うため、値 `0` や空文字、不正文字列（`atoi` の結果 0）は mode 8 の自動選択を抑止する。負の結果なら device ごとの自動判定へ進む。さらに `native_expert_set_mode()` で 0 以上の mode が設定された場合も `exp_mode()` はそれを優先する（`engine/src/kernels/cuda/iq_kernels.cu:6763-6803,6822-6828`）。
- mode 8 が選ばれても、fused gate/up は nibble layout でなく、Hadamard block がなく、`n_embd <= 4096`、対応する `gu_type`、`n_ff % 32 == 0` を満たす層に限る。条件を満たさない層は通常の分岐に続く（`engine/src/kernels/cuda/iq_kernels.cu:7205-7240`）。

## 実行時の詳細

`native_expert_grouped()` が mode を求めるとき、HIP gfx906 以外では `exp_mode()` が device ごとの自動 mode を決める。`STRATA_EXP_MODE` が非負値ならその値が優先され、自動時には `gfx1151_exp8(dev)` が true の場合に mode 8 を選ぶ（`engine/src/kernels/cuda/iq_kernels.cu:6763-6803,7196-7204`）。

環境変数群は `hip_exp8_auto_enabled(dev)` の初回判定時に読み取られる。判定結果は `static std::atomic<int> cache[64]` に device ごとに保存され、以後同じプロセス・device では環境変数を読み直さない。したがって初回判定後にプロセス環境を変更しても反映されない。device 番号が範囲外、または HIP device property の取得に失敗した場合は false（EXP8 無効）となる（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`）。

gfx1151 で自動 mode 8 になり、層条件も合えば gate/up の fused kernel を起動し、後続で SwiGLU と q8_1 まで処理する。down projection は別の分岐で、`d_type == 20`（IQ4_NL）の LDS kernel は EXP8 判定が true の場合に候補から除外される。これ以外の型は down の mode、対応型、各 kernel 条件によって経路が決まる（`engine/src/kernels/cuda/iq_kernels.cu:7205-7239,7327-7337,7355-7402`）。

## ログと測定値

この変数の判定専用ログや無効値警告はない。device 番号または property 取得に問題があって判定できない場合は false を返すが、この関数では終了・警告を行わない。後続の kernel launch 検査は通常の native expert 経路で行われる（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`, `engine/src/kernels/cuda/iq_kernels.cu:7238-7239,7384-7385`）。

## 根拠

- `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748` — 値の取得、gfx1151 を含む arch 別条件、無効化値、device ごとの cache。
- `engine/include/strata/kernels/hip_unsloth_wmma.hpp:32-49` — 対象 GCN arch 名の分類と文字列判定。
- `engine/src/kernels/cuda/iq_kernels.cu:6755-6803` — HIP build 条件、自動 mode 8 と `STRATA_EXP_MODE` の優先関係。
- `engine/src/kernels/cuda/iq_kernels.cu:7196-7239` — mode 8 の gate/up fused 経路とその層条件。
- `engine/src/kernels/cuda/iq_kernels.cu:7355-7402` — IQ4_NL down projection の LDS 経路条件と後続経路。
