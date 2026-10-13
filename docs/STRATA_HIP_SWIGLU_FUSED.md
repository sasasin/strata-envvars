# `STRATA_HIP_SWIGLU_FUSED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバーの動作は対象外。

## 役割

MoE expert の gate/up（SwiGLU）→ q8_1 量子化を、gfx906 ビルドに限り 2 回 pass（`swiglu_entries_kernel` + `quantize_q8_1_kernel`）ではなく、RDNA の one-pass fused kernel（`swiglu_q8_1_entries_kernel`）で実行する opt-in。fused kernel は出力が bitwise 同一（「bitwise the same」）で、結果を変えず pass 構成を変える。既定は 2-pass（A/B baseline）。

読み取りは `src/kernels/cuda/iq_kernels.cu` の `native_expert_grouped()` 1 箇所（`env_on` 経由、SYCL に同一ロジックのミラー `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5144`）。

## 値と判定

`env_on(name)` は `v != nullptr && v[0] != '\0' && v[0] != '0'`（`src/kernels/cuda/iq_kernels.cu:1951-1954`）。先頭文字だけを見る。

| 状態 | 判定 |
|---|---|
| 未設定（`nullptr`） | 無効（既定） |
| 空文字 `""` | 無効（`v[0]` は `\0`） |
| 先頭文字が `0`（`0`, `0anything`） | 無効 |
| 先頭文字が `0` でも `\0` でもない非空文字列（`1`, `true`, `false`, `2`, `a` など） | 有効 |

`false` は先頭文字 `f` なので有効、`0` は無効。数値 parse・大文字小文字・空白は検査しない。

根拠: `src/kernels/cuda/iq_kernels.cu:3568`（`env_on`）、`1951-1954`（`env_on` 定義）。

## 有効になる条件

- ビルドが gfx906 用 macro（`#if defined(STRATA_HIP_GFX906)`）。それ以外のビルドでは `sw_v1 = v1`（`iq_kernels.cu:3571`）で、この変数は効かない。
- `v1`（`g_grouped_v1`）が false であること。`sw_v1 = v1 || !sw_fused`（`iq_kernels.cu:3569`）。`v1` が true なら fused path を通らない。`g_grouped_v1` は `env_on("STRATA_GROUPED_V1")`（`iq_kernels.cu:3446`）または `native_grouped_set_v1` で決まる。
- 判定結果は `static const bool sw_fused` に保存され、プロセス内で最初に呼ばれたとき一度だけ環境を読む。以後の環境変更は反映されない。

## 実際の挙動

fused path（`sw_v1` が false）のとき `swiglu_q8_1_entries_kernel` を launch（`iq_kernels.cu:3577-3578`）。2-pass path（`sw_v1` が true）のとき `swiglu_entries_kernel` と `quantize_q8_1_kernel` を launch（`iq_kernels.cu:3574-3575`）。両者は同じ `hq`（q8_1 量子化された hidden）を産む（bitwise 同一）。

## 測定値

Strata の docs（`docs/AMD_HIP.md`、`docs/DETAILS.md`）にこのスイッチの性能数値の記載はない。実装注釈（`iq_kernels.cu:3566-3567`）は gfx906 で 2-pass を A/B baseline、fused を「bitwise the same」の one-pass kernel として説明する。向上幅はコードから確認できない。

## 相互作用

- `STRATA_GROUPED_V1`（`env_on`）: 有効（true）なら `sw_v1` が true になり、`STRATA_HIP_SWIGLU_FUSED` の値にかかわらず 2-pass path。fused path は `STRATA_GROUPED_V1` が off のときだけ選ばれる。

## 根拠

- 読み取り・判定: `src/kernels/cuda/iq_kernels.cu:3568`、`env_on` 定義 `1951-1954`。
- path 分岐と kernel: `src/kernels/cuda/iq_kernels.cu:3565-3578`。
- `v1` の由来: `src/kernels/cuda/iq_kernels.cu:3446,3492`。
- SYCL ミラー: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5143-5144`。
