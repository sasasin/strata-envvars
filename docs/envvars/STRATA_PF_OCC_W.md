# `STRATA_PF_OCC_W`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の native fused prefill expert カーネルで、一部の型の launch grid を決める「1 WGP あたりの block 数」を正の数で上書きする実験用設定。正の値は gate/up と down の対象 occupancy variant に共通して使われる。対象の `occ_gu` / `occ_d` が偽の型には影響しない。CUDA build では読み取り箇所が `__HIPCC__` 内にあるため使われない。`engine/src/prefill/moe_fused_iq.cu:2831-2845, 3759-3777`

## 値と判定

`occ_blocks` 内の関数ローカル `static const int` 初期化時に `std::getenv` と `std::atoi` で読み、結果が `> 0` のときだけ上書きに使う。未設定は `0`、空文字や数値に変換できない文字列も `atoi` の結果が `0` となり、型ごとの既定値に戻る。`atoi` は数値全体の厳密な妥当性検査をしないため、先頭の空白や符号付き整数を変換し、数値の後ろに文字があっても数値部分を使う（例: `3tail` は `3`）。`0`、負数、数値で始まらない値は上書きにならない。範囲 clamp やエラー報告はない。`engine/src/prefill/moe_fused_iq.cu:2832-2837`

| 条件 | unset / 非正値 | 正の変換結果 |
|---|---|---|
| HIP build、`STRATA_W_NO_OCC` 未定義、occupancy variant 対象型 | gate/up は Q4_K / Q5_K が 3、IQ2_S / IQ2_XS が 3、それ以外の対象 gate/up 型は 4。down は Q5_1 が 3、それ以外の対象 down 型は 4。 | 変換された値を WGP あたりの block 数に使用 |
| HIP build、`STRATA_W_NO_OCC` 定義 | occupancy variant が無効になり、この変数を読む launch 経路に入らない | 影響なし |
| CUDA build | 読み取りも適用もない | 影響なし |

実際の既定値は `occ_blocks` の分岐に基づく。`w12` 引数は渡されるが分岐に使われないため、この関数内では gfx11 / gfx12 による既定値の差はない。ソースコメントには gfx11 の既定値について相違する説明もあるが、実行コードは上記の型分岐で決まる。`engine/src/prefill/moe_fused_iq.cu:2826-2845`

## 有効になる条件

- HIP build であること。CUDA build では対象の `getenv` と `occ_blocks` 定義がコンパイル対象外。`engine/src/prefill/moe_fused_iq.cu:2813-2814, 2846`
- 現在の GPU がこの HIP native WMMA 経路の対象であること。`dev_info()` は gfx11 WMMA または gfx12 WMMA と実カーネル属性を確認し、その他は `d.ok` を立てない。`engine/src/prefill/moe_fused_iq.cu:2858-2885`
- レイヤーが `native_supported` により native fused prefill に選ばれ、`experts_native` が呼ばれること。非対応の形式ペアや無効な device setup はこの経路を使わない。gfx12 で既定有効かどうかは OS 条件を含む `kGfx12PromptDefaultsOn` によって異なり、明示的な `STRATA_PF_FUSED` の値も選択に関与する。`engine/src/prefill/moe_fused_iq.cu:3415-3432, 3562-3586, 3686-3700`
- `STRATA_W_NO_OCC` が build macro として定義されていないこと。定義されている場合、`occ_gu` と `occ_d` はともに false となる。`engine/src/prefill/moe_fused_iq.cu:3759-3768`
- gate/up の対象型は IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S / IQ4_XS / Q2_0。Q4_K / Q5_K は別の `STRATA_PF_KQ_OCC` が先頭文字 `1` である場合に加わる。down の対象型は Q2_0 / Q8_0 / IQ4_NL。Q5_1 は同じく `STRATA_PF_KQ_OCC` が有効な場合に加わる。これら以外では `STRATA_PF_OCC_W` は使われない。`engine/src/prefill/moe_fused_iq.cu:3762-3768`
- P1A または `STRATA_PF_F16=2` の HIP 専用経路が各条件を満たして先に return する呼び出しでは、W kernel の occupancy grid 計算に到達しない。`engine/src/prefill/moe_fused_iq.cu:3703-3752`

## 実行時の詳細

`occ_blocks` の static 初期化により、各関数実体で最初にこの関数が呼ばれたときの値が保存され、以後の呼び出しでは環境を再読しない。従って、その後プロセス内で環境を変更しても反映されない。対象型でない最初の呼び出しでも関数が評価されれば値を cache する。`engine/src/prefill/moe_fused_iq.cu:2832-2837, 3774-3777`

対象の gate/up と down ごとに、カーネル grid は `min(tiles × その投影の行数係数, multiprocessor 数 × block 数/WGP)` で決まる。環境値が正なら block 数/WGP にその値を使い、そうでなければ `occ_blocks` の型別既定値を使う。従って値は grid 上限を変えるが、batch のタイル数が上限より小さければ grid はそのタイル数で制限される。`engine/src/prefill/moe_fused_iq.cu:3774-3777`

## ログと測定値

この変数の設定値、採用された grid、無効値を通知するログは実装にない。カーネル起動後は `cudaGetLastError()` を `ck(..., "experts_native")` で確認するが、エラー時の処理内容は同ファイルの `ck` 定義に従い、この変数専用の警告や fallback 分岐はない。`engine/src/prefill/moe_fused_iq.cu:3852, 3948-3949`

ソースコメントは gfx12 の一部 IQ2 gate/up で 3 block/WGP と 4 block/WGP の測定差（R9700、IQ2_S / IQ4_NL、1 layer、4 回）を記し、gfx11 IQ2_S の比較（16K tokens、1 layer）も記す。これらは特定条件でのコメント上の測定であり、`STRATA_PF_OCC_W` の一般的な性能効果を示すものではない。`engine/src/prefill/moe_fused_iq.cu:2826-2839`

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:2813-2846` — HIP 専用の値読み取りと既定値
- `engine/src/prefill/moe_fused_iq.cu:2858-2885` — HIP GPU / WMMA 対象の確認
- `engine/src/prefill/moe_fused_iq.cu:3415-3432, 3562-3586` — native fused route の選択条件
- `engine/src/prefill/moe_fused_iq.cu:3686-3700, 3703-3777` — early return、型 gate、および grid 計算
- `engine/src/prefill/moe_fused_iq.cu:3852, 3948-3949` — launch 後のエラー確認
