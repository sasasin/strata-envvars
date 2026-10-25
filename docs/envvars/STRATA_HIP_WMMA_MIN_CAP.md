# `STRATA_HIP_WMMA_MIN_CAP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`STRATA_HIP_WMMA=auto` のとき、HIP の QSA prompt attention が matrix-core WMMA kernel を選ぶ追加条件として、呼び出しの `cap` に下限を設けます。`cap` は QSA selection のセル幅で、通常の prompt 経路ではモデル形状と最大セル数から計算された選択バッファ幅です。`n_q` による下限は別変数 `STRATA_HIP_WMMA_MIN_Q` が担当します。

## 値と判定

値は `std::atoll` で `int64_t` に変換されます。文字列全体の妥当性検査、clamp、警告はありません。`atoll` は先頭の空白と符号を許し、数字の並びを変換し、数字が始まらない文字列では0を返します。数字の後ろにある文字列は判定に使われません。

| 環境変数の状態 | `min_cap` | `cap` 条件 |
|---|---:|---|
| unset | 0 | `cap >= 0` |
| 空文字 | 0 | `cap >= 0` |
| 数値文字列 | 変換した符号付き整数 | `cap >= min_cap` |
| 数字で始まらない文字列 | 0 | `cap >= 0` |

例として `12junk` は12、`-1` は-1として扱われます。QSA WMMA 経路に入る前提として `cap > 0` が別途検査されるため、負値や0の下限はその正の `cap` を追加で除外しません。正の下限を指定した場合、`cap` が下限未満の呼び出しでは WMMA を選びません。

## 有効になる条件

この下限が選択に影響するのは、次の条件を満たす場合です。

- HIP ビルドの QSA prompt attention 経路を実行している。
- `STRATA_HIP_WMMA` が完全一致で `auto` と判定されている。
- 現在の GPU が gfx12（RDNA4）として識別される。
- QSA prompt attention が int8 KV で、head dimension・head 数、selection buffer などの kernel 前提を満たす。

`STRATA_HIP_WMMA=1` は `min_cap` を参照せず、適格な gfx11/gfx12 で WMMA を強制します。`STRATA_HIP_WMMA` が未設定の場合は gfx12 のビルド既定に従い、既定 ON のビルドなら `min_cap` による選別なしで WMMA を使います。`STRATA_HIP_WMMA=0` や `auto` 以外の値では WMMA を選びません。CUDA ビルドではこの HIP 固有判定は使われません。

## 実行時の詳細

`hip_wmma_usable()` は `STRATA_HIP_WMMA=auto` の場合に `hip_wmma_auto_pick()` を呼びます。同関数はまず arch が gfx12 かを確認し、それ以外なら `min_cap` を読みません。gfx12 では `min_q` と `min_cap` をそれぞれ関数内 static として初回評価時に読み、以後の同プロセス内の呼び出しで値を再評価しません。従って、初回評価後の環境変更は反映されません。

自動選択条件は `n_q >= min_q && cap >= min_cap` です。`min_cap` 条件を満たさない場合、WMMA 呼び出しを行わず、呼び出し元の prefill 経路が通常の `qsa_decode_attn_batch()` に進みます。WMMA launch 自体が失敗した場合は、この変数による選択とは別に、WMMA をプロセス残りで停止して FP32 prompt attention に fallback します。

`docs/AMD_HIP.md` は `auto` の `STRATA_HIP_WMMA_MIN_Q` 条件と kernel の既定・fallback を説明していますが、`STRATA_HIP_WMMA_MIN_CAP` の下限は記載していません。ソース上、この変数の直接読み取りは `src/kernels/cuda/qsa_prompt_attn.cu` の一箇所です。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:2224-2229`: gfx12 限定、`STRATA_HIP_WMMA_MIN_CAP` の `atoll` 変換と `cap >= min_cap` 判定。
- `src/kernels/cuda/qsa_prompt_attn.cu:2186-2194,2230-2240`: 親スイッチ `STRATA_HIP_WMMA` の値判定、auto/default/forced 経路。
- `src/kernels/cuda/qsa_prompt_attn.cu:2372-2380`: HIP prompt attention の WMMA 条件と、条件不成立時に `false` を返す経路。
- `src/prefill/prefill.cpp:1576-1578,3468-3475`: 通常の prompt 経路における `cap` の算出と、WMMA 経路不成立時の `qsa_decode_attn_batch()` fallback。
- `include/strata/kernels/qsa.hpp:160,346`: `cap` が selection width であること。
- `src/kernels/cuda/qsa_prompt_attn.cu:2258-2263`: WMMA launch 失敗時にプロセス内で WMMA を停止する処理。
- `docs/AMD_HIP.md:518-522`: `auto`、`STRATA_HIP_WMMA_MIN_Q`、launch failure の説明。`MIN_CAP` は説明されていません。
