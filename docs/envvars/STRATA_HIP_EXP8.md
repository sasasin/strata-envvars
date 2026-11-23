# `STRATA_HIP_EXP8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP ビルドの AMD GPU で、expert の gate/up + SwiGLU + q8_1 経路に EXP_MODE=8 を自動選択するかを制御する。これは変換値を読む設定ではなく、GPU 世代別の自動選択を全体的に抑止または RDNA2 で明示的に有効化するスイッチである。HIP 以外の build と gfx906 ではこの設定を使った自動選択は行わない。`hip_exp8_auto_enabled()` の判定結果は `gfx1151_exp8()` から `exp_mode()` に渡り、デバイスの既定 mode を選ぶ（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-749`, `engine/src/kernels/cuda/iq_kernels.cu:6755-6802`）。

## 値と判定

文字列全体の parse はせず、GPU 世代ごとに値の先頭文字だけを比較する。空文字は設定済みだが先頭文字が `'0'` / `'1'` ではない値として扱われる。大文字小文字、空白、数値妥当性は検査しない。

| HIP build 上の GPU | unset | `STRATA_HIP_EXP8` で有効になる値 | `STRATA_HIP_EXP8` で無効になる値 |
|---|---|---|---|
| gfx12 WMMA (`gfx1200/1201`) | 自動有効 | 先頭文字が `0` 以外（例: 空文字、`1`, `true`, `anything` は有効） | 先頭文字 `0`（例: `0`, `0anything`） |
| gfx1151 | 自動有効 | 先頭文字が `0` 以外 | 先頭文字 `0` |
| その他 gfx11 WMMA (`gfx1100..1103`, `gfx1150`) | 自動有効 | 先頭文字が `0` 以外 | 先頭文字 `0` |
| RDNA2 (`gfx1030`, `gfx1031`, `gfx1032`, `gfx1034`) | 無効 | 先頭文字 `1` のみ（例: `1`, `1anything`） | 未設定、空文字、`0`, `true`, `01` など先頭が `1` でない値 |
| 上記以外、または GPU 情報取得失敗 | 無効 | なし | なし |

全体設定の先頭文字が `0` なら、個別設定にかかわらず上記の自動選択を止める。個別の抑止設定は gfx12 では `STRATA_GFX12_EXP8=0`、gfx1151 では `STRATA_GFX1151_EXP8=0` または `STRATA_GFX11_EXP8=0`、その他 gfx11 ではそれらに加えて `STRATA_GFX11_DEFAULTS=0`。いずれも先頭文字が `0` の場合だけ抑止し、設定値で既定無効の RDNA2 を有効化することはない。GPU 名は完全一致で判定され、gfx11 WMMA は `gfx1100`, `gfx1101`, `gfx1102`, `gfx1103`, `gfx1150`, `gfx1151`、gfx12 WMMA は `gfx1200`, `gfx1201` に限られる（`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-743`, `engine/include/strata/kernels/hip_unsloth_wmma.hpp:32-48`）。

## 有効になる条件

- HIP の `__HIPCC__` build で、`STRATA_HIP_GFX906` が定義されていないこと。gfx906 向けの compile 分岐では自動判定関数を呼ばず `false` を返す（`engine/src/kernels/cuda/iq_kernels.cu:6755-6761`）。
- デバイス番号が `0..63` であり、`hipGetDeviceProperties()` が成功して、上表の世代判定に入ること。失敗時は無効となる（`engine/src/kernels/hip/hip_unsloth_wmma.cu:718-743`）。
- 自動選択結果を使うには、ベンチマーク API `native_expert_set_mode()` から設定された `g_exp_mode` および `STRATA_EXP_MODE` の非負値で mode を上書きしていないこと。`g_exp_mode` が非負ならそれを優先し、そうでなく `STRATA_EXP_MODE` が非負ならその値を返すため、どちらの場合も自動選択へ進まない（`engine/src/kernels/cuda/iq_kernels.cu:6763-6777`, `engine/src/kernels/cuda/iq_kernels.cu:6822-6829`）。
- この変数は EXP_MODE 自動選択の判定に使われる。その他の model 状態やサーバーモードによる別の判定は、この読み取り関数にはない。

## 実行時の詳細

`hip_exp8_auto_enabled(dev)` の初回呼び出し時に、対象変数と世代別設定を読み、GPU の `gcnArchName` に応じて結果を決める。結果はデバイスごとの `static std::atomic<int> cache[64]` に保存されるため、そのデバイスで一度判定された後の環境変数変更は反映されない。範囲外の `dev` は cache に入らず `false` を返す（`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-749`）。

自動選択が有効になると `exp_mode()` はそのデバイスに mode 8 を設定する。`sw_v1` が false かつ Hadamard-folded down weights (`L.had_block`) を使わない場合は、gate/up 計算後の SwiGLU と q8_1 量子化を融合する経路に進む。これとは別に、この判定は `L.d_type == 20` の down-layout 対応条件にも使われ、auto が有効な場合はその型を LDS down 経路の候補から外す。無効の場合はハードウェア別既定 mode に進む（`engine/src/kernels/cuda/iq_kernels.cu:6771-6802`, `engine/src/kernels/cuda/iq_kernels.cu:7327-7337`, `engine/src/kernels/cuda/iq_kernels.cu:7355-7367`）。

## ログと測定値

通常の自動選択関数はログを出さない。HIP の同梱検証・ベンチマーク実行ファイルは `Device ... | gcnArchName: ... | CUs: ... | WMMA=%d | EXP8_AUTO=%d` を stdout に出し、最後の値にこの関数の結果を表示する（`engine/src/kernels/hip/hip_unsloth_verify.cu:419-427`）。本調査ではこの変数による測定値は記載しない。

## 根拠

- `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-749` — 読み取り、世代別判定、デバイス別 cache。
- `engine/src/kernels/cuda/iq_kernels.cu:6755-6802` — HIP build 条件、mode 8 自動選択と優先順位。
- `engine/src/kernels/cuda/iq_kernels.cu:7327-7337` — mode 8 選択時の SwiGLU/q8_1 fused 経路。
- `engine/src/kernels/cuda/iq_kernels.cu:7355-7367` — `L.d_type == 20` の LDS down 経路条件。
- `engine/src/kernels/hip/hip_unsloth_verify.cu:419-427` — 検証実行ファイルの診断出力。
