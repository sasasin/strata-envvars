# `STRATA_QI_FAST_LN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象はStrata所有の `tools/image/sdcpp_native` 実装。stable-diffusion.cpp など外部依存の内部動作は対象外。

## 役割

Strata の Qwen Image 2.1 ネイティブ DiT ランナーで、LayerNorm と残差加算を行うカーネルを切り替えます。環境変数が設定されていれば、事前計算済みの `tanh(modulation gate)` を使う float4 カーネルを選びます。未設定なら各要素で gate の `tanh` を計算するカーネルを使います。

## 値と判定

値の内容は parse せず、`getenv("STRATA_QI_FAST_LN") != nullptr` だけを見ます。

| 環境変数の状態 | 選択される経路 |
|---|---|
| 未設定 | 標準の `qi21_res_ln_mod` |
| 任意の値を設定（`1`, `0`, `false`, 空文字を含む） | `qi21_res_ln_mod2` の float4 カーネル |

大文字小文字や数値としての妥当性は関係ありません。ランナーのコンストラクターで一度だけ読み、`fast_ln` メンバーに保存します。ランナー生成後にプロセス環境を変えても、そのインスタンスの選択は変わりません。

## 有効になる条件

- `sd-cli` が CUDA または HIP 対応でビルドされ、Strata の `tools/image/sdcpp_native/apply.py` によりネイティブランナーが組み込まれている必要があります。
- Qwen Image 2.1 で、model args に `qwen_image_2_1_native=1` が渡され、非空の diffusion model path がある場合にだけこのランナーが選ばれます。通常の stock runner ではこの環境変数は読み取られません。
- 実行時の入力条件を満たさず stock runner に切り替わった場合も、`fast_ln` の設定は native runner の処理にしか影響しません。

## 実行時の詳細

ネイティブランナーの生成時に環境変数の有無を `fast_ln` に保存します。各 diffusion step では、modulation tensor 全体について `qi21_tanh` を呼び、gate 値を `gates` tensor に先行計算します。この前計算自体は `STRATA_QI_FAST_LN` の設定にかかわらず行われます。

各 transformer block の residual + LayerNorm 処理では、設定時は `qi21_res_ln_mod2` に事前計算済み gate を渡し、未設定時は `qi21_res_ln_mod` に raw gate を渡します。両カーネルとも残差を `x += h * tanh(gate)` として更新し、LayerNorm の平均・分散を計算して `(x - mean) * rsqrt(variance + eps) * (1 + modulation)` を出力します。標準経路はその場で `tanhf(g[c])` を計算し、mod2 経路は事前計算値を float4 単位で利用します。

ネイティブ実装のカーネル呼び出しが失敗した場合は警告後、その step を stock runner で再計算します。コメントには「3060で2.10対2.10秒/step、差なし」とありますが、測定条件や手順を説明する資料を確認できなかったため、一般的な性能差は結論できません。

## 根拠

- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:55-60,80-90` — `fast_ln` 初期値とコンストラクターでの設定有無判定。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:321-331,341,424,439-442` — residual + LayerNorm の呼び出し箇所、分岐、失敗時の扱い。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:524-527` — modulation gate の事前 `tanh` 計算。
- `tools/image/sdcpp_native/qi21-native.cu:39-78,85-111,573-596` — float4経路と標準経路の計算内容、カーネル選択関数。
- `tools/image/sdcpp_native/apply.py:1-10,27-45,47-51` — native runner の組み込みと CUDA / HIP ビルド条件。
- `serve/images.py:126-128` — serve が native 設定時に model args を渡す箇所。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:445-466,568-574` — native runner の適用条件と stock runner への切り替え。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:88` — 3060に関する測定コメント。別の説明資料で測定条件は確認できず、測定結果としては一般化していません。
