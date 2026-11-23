# `STRATA_GFX11_EXP8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の gfx11 系デバイスで、native expert の EXP8 判定を既定で有効にする設定です。unset を含めて既定は有効で、この変数の値が `0` で始まる場合に無効化します。EXP8 判定が有効だと、native expert の自動レイアウト選択で mode 8 を選び、対象形式では gate/up・SwiGLU・q8_1 量子化をまとめた経路を選べます。また、down projection の `d_type == 20` では LDS kernel の候補から外します。これは量子化データ自体や生成 token を直接変更する設定ではなく、該当する native expert kernel の選択条件を変えます。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:6750-6762`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:7200-7214`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:7355-7386`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 値と判定

`hip_exp8_auto_enabled(dev)` は `std::getenv` で対象変数を読み、文字列全体を parse せず、先頭文字が `'0'` かだけを判定します。大文字小文字や数値としての妥当性は検査しません。従って空文字、`1`、`true`、`false`、先頭が空白の ` 0` はこの変数による無効化にならず、`0`、`0anything` は無効化になります。gfx11 以外ではこの変数を参照する分岐に入りません。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-743`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)、[`engine/include/strata/kernels/hip_unsloth_wmma.hpp:32-48`](../../../../Niko1221/Strata/engine/include/strata/kernels/hip_unsloth_wmma.hpp)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP の gfx11 (`gfx1100`–`gfx1103`, `gfx1150`, `gfx1151`)、他の無効化条件なし | EXP8 判定は有効 | 空文字、`1`、`true`、`false`、` 0` | `0`、`0anything` |
| gfx11 で `STRATA_HIP_EXP8` または `STRATA_GFX1151_EXP8` が `0` で始まる | その別変数により無効 | 対象変数の値にかかわらず無効化条件がなければ有効 | 対象変数が `0` で始まる場合も無効 |
| gfx11 のうち `gfx1151` 以外で `STRATA_GFX11_DEFAULTS` が `0` で始まる | gfx11 defaults により無効 | その別変数が無効化していなければ有効 | 対象変数が `0` で始まる場合も無効 |
| gfx12、RDNA2、その他の arch、または device property 取得失敗 | この変数による有効化なし | 該当なし | 該当なし |

`STRATA_HIP_EXP8` が先頭 `0` の場合は全 arch 分岐より先に無効化されます。gfx1151 は `STRATA_GFX1151_EXP8` と対象変数の先頭 `0` を見ますが、`STRATA_GFX11_DEFAULTS` は見ません。gfx11 の他の arch はさらに `STRATA_GFX11_DEFAULTS` を無効化条件として見ます。gfx12 は `STRATA_GFX12_EXP8`、RDNA2 は `STRATA_GFX1030_EXP8` / `STRATA_HIP_EXP8` の別条件で判定され、この変数は使いません。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-743`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)

## 有効になる条件

- 呼び出し側が HIP build であり、`STRATA_HIP_GFX906` build ではないこと。CUDA build や gfx906 build では wrapper が `false` を返します。[`engine/src/kernels/cuda/iq_kernels.cu:6755-6761`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `hipGetDeviceProperties` が成功し、対象 GPU が gfx11 (`gfx1100`, `gfx1101`, `gfx1102`, `gfx1103`, `gfx1150`, `gfx1151`) と分類されること。architecture 名は末尾が `:` または文字列終端の場合に一致します。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:728-743`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)、[`engine/include/strata/kernels/hip_unsloth_wmma.hpp:32-45`](../../../../Niko1221/Strata/engine/include/strata/kernels/hip_unsloth_wmma.hpp)
- `STRATA_HIP_EXP8`, `STRATA_GFX1151_EXP8`、該当する場合の `STRATA_GFX11_DEFAULTS` のいずれも `0` で始まらないこと。後二者の対象範囲は gfx1151 と他の gfx11 で異なります。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-743`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)
- native expert の mode 8 自動選択は、別途 `STRATA_EXP_MODE` が非負値を指定しておらず、`native_expert_set_mode` による明示 mode 指定もなく、native expert 経路で `exp_mode()` が評価されること。さらに部分的な `grid_groups`（`0 < grid_groups < cap_groups`）では `em0` を 0 にする経路があり、mode 8 は選ばれません。[`engine/src/kernels/cuda/iq_kernels.cu:6763-6803`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:6822-6828`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:7196-7204`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- gate/up 側の mode 8 fused kernel は、さらに対応形式、`L.n_embd <= 4096`、`L.n_ff % 32 == 0`、nibble layout / Hadamard 条件などを満たす場合だけです。down 側の `d_type == 20` LDS 経路は EXP8 判定が無効で、`em0d` が 7 または 8 の場合だけ候補になります。[`engine/src/kernels/cuda/iq_kernels.cu:7205-7214`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:7355-7386`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 実行時の詳細

判定は `hip_exp8_auto_enabled` の `static std::atomic<int> cache[64]` に device ごとに保存されます。最初の呼び出し時に環境変数と device properties を読み、その後は同じ process 内で cache を返すため、初回判定後に環境を変更しても反映されません。device 番号が `0..63` の範囲外なら false、property 取得失敗時も false です。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)

この helper は `iq_kernels.cu` の mode 自動判定から呼ばれ、EXP8 が有効なら mode 8 を選択します。mode 8 の gate/up は、条件を満たすと gate/up と SwiGLU、q8_1 量子化をまとめた kernel を使います。down 側では別途 helper の結果を見ており、EXP8 が有効な `d_type == 20` は `lds_down_ok` が false になるため LDS down kernel を使わず、その後の通常 down kernel 選択へ進みます。無効の場合は `em0d` が 7 または 8 なら同じ形式の LDS kernel が候補になります。[`engine/src/kernels/cuda/iq_kernels.cu:6774-6803`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:7205-7238`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)、[`engine/src/kernels/cuda/iq_kernels.cu:7355-7388`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## ログと測定値

production の EXP8 判定 helper に、値や判定結果を出力するログはありません。device property 取得失敗や範囲外 device 番号も false を返すだけです。`hip_unsloth_verify` のスタンドアロン parity / benchmark harness は `EXP8_AUTO=%d` を標準出力に表示しますが、通常の native expert 実行ログではありません。[`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_wmma.cu)、[`engine/src/kernels/hip/hip_unsloth_verify.cu:419-427`](../../../../Niko1221/Strata/engine/src/kernels/hip/hip_unsloth_verify.cu)

`iq_kernels.cu` のコメントには特定の GPU・モデル・実行条件での測定値がありますが、これらはソースコメント上の記録であり、本調査で再測定していません。また、対象変数の一般的な速度・正確性を示す測定値は資料から確認できないため、ここでは性能効果を一般化しません。[`engine/src/kernels/cuda/iq_kernels.cu:6750-6754`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 根拠

- `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748` — 環境変数の読み取り、gfx arch ごとの判定、device ごとの cache。
- `engine/include/strata/kernels/hip_unsloth_wmma.hpp:32-48` — gfx11 / gfx12 / RDNA2 arch の分類。
- `engine/src/kernels/cuda/iq_kernels.cu:6750-6803` — HIP build 条件、mode 8 自動選択、`STRATA_EXP_MODE` の優先。
- `engine/src/kernels/cuda/iq_kernels.cu:7196-7238` — partial grid 条件と mode 8 gate/up kernel。
- `engine/src/kernels/cuda/iq_kernels.cu:7355-7388` — Q2_0 (`d_type == 20`) down kernel の選択。
- `engine/src/kernels/hip/hip_unsloth_verify.cu:419-427` — harness 上の `EXP8_AUTO` 表示。
