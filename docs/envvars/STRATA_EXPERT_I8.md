# `STRATA_EXPERT_I8`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

prompt 中の MoE expert 計算で、Strata 所有の int8 dot-product カーネル `native_expert_i8` を経路候補にするかを制御する。対象は CUDA/HIP のカーネル実装と、それを使う共通 prefill 経路および Qwen 3.6 エンジンである。値を `1` にしても、より優先される fused 経路、未対応の重み形式、または条件を満たさない層・chunk を置き換えるものではない（`include/strata/kernels/i8_expert_rule.hpp:41-57`, `src/prefill/prefill.cpp:5966-5999`, `src/qwen35/q36_engine.cu:1412-1439`）。

## 値と判定

`i8_switch_parse` は文字列全体を parse せず、未設定（null）または空文字なら `-1`、先頭文字が `'0'` なら `0`、それ以外の非空文字列なら `1` とする。大小文字・空白・数字としての妥当性は検査しない。したがって `0` と `0anything` は off、`1`・`true`・`false`・` 0` は on、空文字は unset と同じ扱いになる（`include/strata/kernels/i8_expert_rule.hpp:28-36`）。

| ビルド / 条件 | unset（null または空文字） | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| llama.cpp MMQ あり | HIP `gfx1030` / `gfx1031` / `gfx1032` で対応層に限り既定 on。それ以外は既定 off（MMQ が対応層を取る） | 先頭が `0` でない非空文字列 | 先頭が `0` の文字列 |
| llama.cpp MMQ なし（`-DSTRATA_MMQ=OFF`、または HIP で `STRATA_PREFILL_MMQ` なし） | 既定 on（set 状態 `1` と同じ）。ただし層の形式・サイズ等の適用条件は残る | 先頭が `0` でない非空文字列 | 先頭が `0` の文字列 |

既定判定は `i8_switch_effective` と `i8_expert_class_default` による。MMQ なしの共通エンジンは `STRATA_EXPERT_I8` が未設定の場合だけ状態を `1` に引き上げる。明示した `0` / `1` はどちらのビルドでも優先される。未設定時に既定 on となる GPU クラスは HIP の `gfx1030`・`gfx1031`・`gfx1032` であり、設定値 `1` は他の対応 GPU クラスにも要求できる（`include/strata/kernels/i8_expert_rule.hpp:23-39,54-57`; MMQ なしの設定は `src/prefill/prefill.cpp:204-216`）。

## 有効になる条件

- 実装が組み込まれた CUDA/HIP prompt 経路であること。共有判定部 `src/kernels/cuda/iq_kernels.cu` は CUDA/HIP コンパイル条件を分け、HIP では現在 device の `gcnArchName` を使う。コード上、SYCL の同名環境変数読み取りは見つからない（`src/kernels/cuda/iq_kernels.cu:6247-6265`）。
- 対象層が `native_expert_i8_supported` の重み形式・寸法・共有メモリ条件を満たし、1 launch あたりの expert group entries が 256 以上であること。形式不一致、サイズ不足、共有メモリ不足では選ばれない（`src/kernels/cuda/iq_kernels.cu:6285-6289,6330-6334`; 判定規則は `include/strata/kernels/i8_expert_rule.hpp:20-21,52-57`）。
- 共通 prefill の group walk では fused / staged fused がその層を取らず、WMMA、peer、CPU share、直接 MMQ、tail / Hadamard / nibble 等の除外条件にも当たらないこと。加えて `STRATA_PREFILL_GROUP_GATHER` が未設定、または `atoi` の結果が非ゼロである必要がある（空文字や数値に変換できない文字列は `atoi` で 0 となり、この経路を止める）。該当分岐は `src/prefill/prefill.cpp:5960-5990`。
- Qwen 3.6 では層ごとに `fused > int8（明示 on）> MMQ > int8（switch が off でない場合）> grouped` の順に選ぶ。MMQ の候補には MMQ 対応 build、層の tile 対応、かつ `STRATA_Q36_NO_MMQ` が未設定であることが必要（この別変数は値でなく設定有無を判定）。どれか1層でも最終経路が grouped のみなら Qwen 3.6 は prompt 用 hybrid path を全体で無効にし、全層を grouped 経路に戻す（`include/strata/kernels/q36_prompt_route.hpp:21-34`; `src/qwen35/q36_engine.cu:1396-1399,1412-1442`）。
- 選択後も Qwen 3.6 の few-rows 判定（`STRATA_I8_FEWROWS`）により、その chunk の平均 routed rows が閾値未満なら `native_expert_grouped` に切り替わる（`include/strata/kernels/q36_prompt_route.hpp:36-38`; `src/qwen35/q36_engine.cu:2173-2183`）。

## 実行時の詳細

共通カーネルライブラリでは `i8_switch_raw()` 内の function-local `static const int` が環境値を初回に読み、プロセス内でキャッシュする。device の HIP arch 名も device ごとに一度取得して保存する（`src/kernels/cuda/iq_kernels.cu:6242-6265`）。共通 prefill は層・chunk の経路判定後、対象 token rows を q8_1 形式へ量子化し、group 情報を使って int8 expert kernel を呼び出す。経路決定後に環境を変更しても、共通ライブラリの switch キャッシュには反映されない（`src/prefill/prefill.cpp:5991-6017,6042-6071`）。

Qwen 3.6 は engine 初期化時に `getenv` を直接 parse し、各層の `i8_on` と prompt 経路を決定する。選ばれた層では prompt 実行時に行を量子化して int8 kernel を呼び、few-rows 条件時は grouped kernel を使う。engine 作成後に環境値を変えても、その engine の層別経路は変わらない（`src/qwen35/q36_engine.cu:1412-1442,2173-2183`）。

## ログと測定値

共通 prefill では int8 経路が最初に使われたとき、一度だけ stderr に、既定による選択なら `strata: prompt experts on our own int8 kernels (the default of this build or graphics card; STRATA_EXPERT_I8=0 goes back to the old kernels)`、明示値による選択なら `strata: prompt experts on our own int8 dot-product kernels (STRATA_EXPERT_I8=1)` を出す。MMQ なし build では既定経路のこの行は抑制される（`src/prefill/prefill.cpp:6042-6050`）。Qwen 3.6 のこの switch による経路選択ログは該当コードに見つからない。

共通経路で activation または group record の確保に失敗すると、それぞれ `prefill: int8 experts: no memory for the activations` / `prefill: int8 experts: no memory for the group record` をエラー文字列に設定し処理を失敗させる。実行時に未対応 layout が `native_expert_i8` まで到達した場合は stderr に `native_expert_i8: gate/up type ... is not covered` を出し `exit(1)` する（`src/prefill/prefill.cpp:6052-6066`; `src/kernels/cuda/iq_kernels.cu:6344-6352`）。

## 根拠

- 値の parse、build default、GPU class、256 entries 閾値: `include/strata/kernels/i8_expert_rule.hpp:20-57`。
- switch の cache、device arch、layout 判定: `src/kernels/cuda/iq_kernels.cu:6240-6289,6330-6334`。
- 共通 prefill の適用条件、実行、ログ、失敗経路: `src/prefill/prefill.cpp:5960-6017,6042-6071`。
- Qwen 3.6 の経路順・初期化と実行: `include/strata/kernels/q36_prompt_route.hpp:21-38`; `src/qwen35/q36_engine.cu:1396-1442,2173-2183`。
- Strata の `docs/SETTINGS.md:306` はこの変数を NVIDIA / AMD 向けの `text` として掲載するが、値規則や経路の説明はない。`docs/DETAILS.md` に本変数の説明は見つからなかった。
