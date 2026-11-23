# `STRATA_GFX1030_EXP8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の RDNA2 (`gfx1030` など) で、grouped native expert の EXP_MODE 8 を自動選択させる opt-in 変数。EXP_MODE 8 では対応する gate/up 経路が SwiGLU と q8_1 量子化を `native_gu_fused_kernel` にまとめる。候補環境変数が直接参照されるのは `hip_exp8_auto_enabled()` で、判定結果は `iq_kernels.cu` の `exp_mode()` から grouped expert のレイアウト選択に使われる（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`、`engine/src/kernels/cuda/iq_kernels.cu:6755-6803,7205-7238`）。

gfx1030 は WMMA を持たない RDNA2 として扱われるが、この変数の判定自体は WMMA 可否判定と別である。gfx1030 でこの変数を有効にしても WMMA カーネルを選ぶ設定ではなく、EXP_MODE 8 の grouped expert レイアウトを選ぶ（`engine/include/strata/kernels/hip_unsloth_wmma.hpp:10-14,252-258`、`engine/src/kernels/hip/hip_unsloth_wmma.cu:30-40,740-742`）。

## 値と判定

コードは文字列を数値変換せず、`getenv` が返す文字列の先頭 1 文字が `'1'` かを比較する。unset、空文字、先頭が `1` 以外なら、この変数単独では gfx1030 を有効化しない。大文字小文字、後続文字、数値としての妥当性は検査しない。したがって `1`、`11`、`1anything` は有効、`0`、`true`、` 1`、空文字はこの変数単独では無効（`engine/src/kernels/hip/hip_unsloth_wmma.cu:726,731-742`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP の RDNA2 (`gcnArchName` が `gfx1030` / `gfx1031` / `gfx1032` / `gfx1034`) | 既定で無効 | 先頭文字が `1` | 空文字、`0`、`true`、` 1` など先頭文字が `1` 以外 |

この分岐は `STRATA_HIP_EXP8` の全体停止判定より後に評価される。`STRATA_HIP_EXP8` が設定され先頭文字 `0` なら、`STRATA_GFX1030_EXP8=1` でも無効。逆に `STRATA_HIP_EXP8` の先頭文字が `1` なら gfx1030 でも有効になる。`STRATA_GFX11_EXP8`、`STRATA_GFX1151_EXP8`、`STRATA_GFX12_EXP8`、`STRATA_GFX11_DEFAULTS` は gfx1030 分岐では参照されない（`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-742`）。

## 有効になる条件

- HIP でビルドされた経路であること。`iq_kernels.cu` の橋渡し関数は `__HIPCC__` かつ `!STRATA_HIP_GFX906` の場合に helper を呼び、それ以外は `false` を返す。CUDA ビルドではこの変数は grouped expert の自動判定に使われない（`engine/src/kernels/cuda/iq_kernels.cu:6755-6761`）。
- 実行 device の arch 名が RDNA2 判定に一致すること。対象分岐は gfx1030、gfx1031、gfx1032、gfx1034 であり、それ以外の arch ではこの変数を見ても有効にならない（`engine/include/strata/kernels/hip_unsloth_wmma.hpp:34-40`、`engine/src/kernels/hip/hip_unsloth_wmma.cu:740-742`）。
- `STRATA_EXP_MODE` が自動選択を上書きしていないこと。`atoi(STRATA_EXP_MODE) >= 0` ならその数値が優先され、`0` なら EXP_MODE 8 は選択されない。未設定または `atoi` が負になる値は自動選択へ進む。文字列全体の検証はなく、例えば `bad` は `atoi` により 0 となり自動選択を抑止する（`engine/src/kernels/cuda/iq_kernels.cu:6763-6767`）。ベンチ用内部変数 `g_exp_mode >= 0` も同様に先に優先する（同 `:6763-6767`）。
- grouped native expert の通常レイアウト選択まで処理が進むこと。先行する V2 / V2K 経路が条件を満たして return すると EXP_MODE 判定を通らない（同 `:7121-7132,7138-7182`）。また通常の HIP 経路でも `grid_groups > 0 && grid_groups < cap_groups` の場合は `em0=0` とされ、自動選択値は使われない（同 `:7196-7203`）。
- モデルの expert weight 型・形状が fused gate/up の条件に合うこと: `nib_layout` でなく、Hadamard block がなく、`em0==8`、`n_embd<=4096`、対応する `gu_type`、`n_ff % 32 == 0`（同 `:7205-7214`）。条件に合わなければ当該 fused gate/up 分岐は実行されず、後続レイアウト選択へ進む。

## 実行時の詳細

`native_expert_grouped()` が選択する `exp_mode()` は `STRATA_EXP_MODE` を関数内 static に一度読み、device ごとの mode も `per_dev[64]` に保持する。自動判定では `gfx1151_exp8()` から `hip_exp8_auto_enabled(dev)` を呼び、helper は各 device の結果を atomic cache に保存する。したがって候補変数を含む環境変数群は device ごとの初回判定時に読み取られ、その後プロセス内で環境を変更しても同じ device の判定は更新されない（`engine/src/kernels/cuda/iq_kernels.cu:6764-6803`、`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`）。

EXP_MODE 8 と条件が揃うと gate/up 形式ごとに `native_gu_fused_kernel` を起動し、その後の down projection は別の分岐・kernel 選択を行う。設定は grouped native expert 経路に限られ、CLI 引数やサーバーモードが直接この変数を読む箇所はない（`engine/src/kernels/cuda/iq_kernels.cu:7205-7238,7355-7385`）。

## ログと測定値

通常の grouped expert 経路では、この変数の値や有効化理由を出力するログは確認できない。HIP の Unsloth parity / benchmark harness は `EXP8_AUTO=%d` として判定結果を標準出力に表示するが、これは harness の出力で、通常の engine 起動ログではない（`engine/src/kernels/hip/hip_unsloth_verify.cu:419-427`）。この変数固有の測定値は `docs/DETAILS.md` と `docs/AMD_HIP.md` では確認できなかった。

## 根拠

- `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748` — 環境変数群の読み取り、device arch ごとの判定、per-device cache。
- `engine/src/kernels/cuda/iq_kernels.cu:6755-6803,7196-7238` — HIP 経路からの呼び出し、`STRATA_EXP_MODE` の優先順位、EXP_MODE 8 の grouped expert 利用箇所。
- `engine/include/strata/kernels/hip_unsloth_wmma.hpp:10-14,34-40,252-258` — WMMA 対応 arch と RDNA2 arch 判定の区別。
- `engine/src/kernels/hip/hip_unsloth_verify.cu:419-427` — harness の `EXP8_AUTO` 表示。
