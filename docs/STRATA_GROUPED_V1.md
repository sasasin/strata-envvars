# `STRATA_GROUPED_V1`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA/HIP と SYCL の native grouped-expert カーネルで旧来の V1 実行形を選びます。V1 は可能な group 数 `cap_groups` 分の block row を起動し、SwiGLU と q8_1 量子化を別々のカーネルで全 entry に実行します。通常経路では group 数を絞った grid や融合 SwiGLU/q8_1 カーネルを使える場合があります。ヘッダーの説明と parity 用コードは、この切り替えで出力値が bitwise 同じであることを示していますが、この調査では parity 実行はしていません。

## 値と判定

CUDA/HIP と SYCL の両実装が `env_on("STRATA_GROUPED_V1")` を使います。判定は `getenv()` で値の有無を確認した後、文字列全体を parse せず先頭文字だけを見ます。

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0` | OFF（例: `0`, `0abc`） |
| 先頭文字が `0` 以外で空でない | ON（例: `1`, `2`, `true`, `false`, `off`, ` 1`） |

大文字小文字、空白、後続文字、数値としての妥当性は検査されません。環境変数は `iq_kernels.cu` または SYCL 移植ソースの namespace-scope `g_grouped_v1` 初期化時（共有ライブラリのロード時）に読み取られ、通常はその時点の値が使われます。`native_grouped_set_v1(bool)` による値の上書き API もありますが、調査対象の本番呼び出し元は見つからず、リポジトリ内の parity ハーネスが明示的に切り替えています。

## 有効になる条件

- grouped-expert 経路が実際に `native_expert_grouped()` を呼び出す場合に限り影響します。モデル・層の形式がこの native grouped 経路を使わなければ効果はありません。
- CUDA/HIP 側では、`STRATA_EXPERT_V2=1` の専用条件（`gu_type == 21`, `d_type == 20`, `n_embd == 2560`, `n_ff == 640`）または `STRATA_EXPERT_V2K` 経路が成立すると、V1 判定に到達する前に専用カーネルを起動して return するため、この変数はその呼び出しに効きません。
- CUDA/HIP の gate/up 融合 SwiGLU/q8_1 経路は `!v1` を要求します。V1 が ON なら、その経路を使わず別々の SwiGLU と量子化カーネルに進みます。`STRATA_GU_SWIGLU` が有効でも同様です。
- HIP gfx906 では `STRATA_HIP_SWIGLU_FUSED` が ON でも、`sw_v1 = v1 || !sw_fused` のため V1 が優先して別々のカーネルを使います。
- V1 が ON のとき、`grid_groups` が `cap_groups` より小さくても grid の group 次元は `cap_groups` になります。OFF のときは `grid_groups <= 0` または `grid_groups > cap_groups` なら `cap_groups`、それ以外なら `grid_groups` です。

## 実行時の詳細

`native_expert_grouped()` はまず `cap_groups <= 0` または `cap_entries <= 0` なら何もせず戻ります。その後、CUDA/HIP・SYCL とも `gy` を計算し、gate/up と down の grid の group 次元に使います。V1 の `gy` は常に `cap_groups` なので、呼び出し側が渡した小さな `grid_groups` による grid の縮小は行いません。

CUDA/HIP では V1 が OFF で、対象レイアウト・phase 等の条件も満たす場合、`launch_gu_swiglu()` が SwiGLU と q8_1 化をまとめて実行できます（`STRATA_GU_SWIGLU` の判定は別途行います）。V1 が ON の場合この融合条件が偽になり、gate/up の後に `swiglu_entries_kernel`、続いて `quantize_q8_1_kernel` を実行します。Hadamard-folded down weights の場合は中間に Hadamard 変換も入ります。HIP gfx906 も V1 なら fused SwiGLU を使いません。

SYCL 側も `gy` の選択は同じで、grouped gate/up と down の起動に用います。V1 が OFF で Hadamard 変換も不要なら `swiglu_q8_1_entries_kernel` を使って SwiGLU と q8_1 化を一緒に行います。V1 が ON なら `swiglu_entries_kernel` と `quantize_q8_1_kernel` に分けます。

変数自体に対応するログやエラー出力はありません。通常実行時の変更はカーネルの grid と起動形態です。

## 根拠

- 値判定: `src/kernels/cuda/iq_kernels.cu:3273-3276`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3202`。
- CUDA/HIP での初期値、V2/V2K の先行 return、V1 による grid 選択: `src/kernels/cuda/iq_kernels.cu:5014-5018,5050-5055,5063-5093,5119-5123`。
- CUDA/HIP の融合条件と分離実行: `src/kernels/cuda/iq_kernels.cu:5149-5164,5211-5229`。
- gfx906 の SwiGLU 選択: `src/kernels/cuda/iq_kernels.cu:5212-5219`。
- SYCL での初期値、grid 選択、SwiGLU/量子化の分岐: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5602-5606,5608-5635,5696-5758`。
- 実行形の説明と `native_grouped_set_v1` API: `include/strata/kernels/iq_kernels.hpp:78-85`。parity ハーネスでの明示的な切り替え例: `src/kernels/native_grouped_parity.cpp:193-200`。
