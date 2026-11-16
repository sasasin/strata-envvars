# `STRATA_PF_FUSED_IQ2X`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP ビルドで、AMD gfx12（gfx1200 / gfx1201）の IQ2_XXS / IQ2_XS gate/up 層を、既定で fused int8 prompt kernel に載せるかを制御する。値が `0` で始まると、その既定選択を止めて通常の層選択に戻す。対象コードは `gfx12_iq2x_default()` と `native_supported()`（`src/prefill/moe_fused_iq.cu`）である。CUDA ビルドにはこの環境変数の読み取りコードがなく、影響しない（同ファイル 2876-2889、3019-3024）。

この変数単独では fused kernel を新たに opt-in しない。`STRATA_PF_FUSED` が未設定または空で、Linux の gfx12 既定が使われる場合の IQ2X 形式だけを切り替える。明示的な `STRATA_PF_FUSED=1` は対象形式を含む fused 経路を選び、`STRATA_PF_FUSED=0` は fused 経路を止める（同ファイル 2881-2887、2891-2908、3019-3039）。

## 値と判定

`gfx12_iq2x_default()` は `std::getenv` の結果の先頭文字だけを検査し、変数が設定されていて先頭文字が `'0'` の場合に既定を無効にする。数値変換や文字列全体の比較はしない。したがって空文字は「設定あり」でも無効化せず、`0`、`0anything`、`0.5` は無効化する。`1`、`true`、`false`、空白で始まる ` 0` はこの検査では無効化しない。大文字小文字や数値としての妥当性も検査しない（`src/prefill/moe_fused_iq.cu:2881-2887`）。

| 条件 | 対象変数が unset / 空 | 有効になる例 | 無効になる例 |
| --- | --- | --- | --- |
| HIP、Linux、gfx12、`STRATA_PF_FUSED` が unset / 空 | IQ2_XXS / IQ2_XS の fused 既定を有効にする | `1`, `true`, `false`, ` 0`（先頭が `0` 以外） | `0`, `0anything`（先頭が `0`） |
| HIP、Windows、gfx12、`STRATA_PF_FUSED` が unset / 空 | fused 既定は無効。対象変数だけでは有効化しない | なし | すべて。値にかかわらず Windows の既定フラグが false |
| HIP、gfx12、`STRATA_PF_FUSED=1` | 対象変数によらずグローバル opt-in 経路 | fused 対応が揃えば選択可能 | 対象変数の `0` もこの経路を打ち消さない |
| HIP、任意の GPU、`STRATA_PF_FUSED=0` | fused 経路を無効化 | なし | 対象変数によらず無効 |
| CUDA ビルド | 読み取り箇所なし | 対象変数では変化なし | 対象変数では変化なし |

グローバル変数は未設定または空なら `env_set=-1`、先頭が `1` なら `1`、それ以外の非空文字列なら `0` と判定される。したがって `STRATA_PF_FUSED=1anything` も明示 opt-in、`STRATA_PF_FUSED=true` は無効扱いになる。`STRATA_PF_FUSED_NATIVE` が `0` で始まる場合は別の早期条件で native fused を止める（`src/prefill/moe_fused_iq.cu:2891-2908`）。

## 有効になる条件

- 読み取り実装があるのは `__HIPCC__` 分岐のみ。CUDA では IQ2_XXS / IQ2_XS のルールが異なり、この変数は参照されない（`src/prefill/moe_fused_iq.cu:2876-2889`, `3019-3024`）。
- 読み取り関数は `STRATA_FUSED_DECODE_ONLY` が未定義の場合だけコンパイルされる。この macro は decode-only の golden test が同ファイルを include するときに定義するもの（`src/prefill/moe_fused_iq.cu:2853`; `tests/cuda/prefill_decode_golden.cu:6-25`）。通常の実行時ビルドではない。
- 対象変数が既定を有効にできるのは Linux の gfx12。`kGfx12PromptDefaultsOn` は Windows では false、それ以外のプラットフォームでは true と定義される（`include/strata/core/gfx12_platform_defaults.hpp:5-15`）。gfx12 以外では `native_supported()` の最終既定判定が `d.w12` を要求するため、この既定は適用されない（`src/prefill/moe_fused_iq.cu:3034-3039`）。
- グローバル `STRATA_PF_FUSED` が未設定 / 空のときだけ、対象変数による既定判定が使われる。グローバル `=0` は fused 全体を止め、グローバル `=1` はこの変数の `0` より優先して対応形式の opt-in 経路へ進む（`src/prefill/moe_fused_iq.cu:2883-2885`, `2901-2908`, `3038-3039`）。
- `STRATA_PF_FUSED_NATIVE=0` が設定されている場合は `native_supported()` が false を返す（`src/prefill/moe_fused_iq.cu:2891-2908`）。
- gate/up が `T_IQ2_XXS` または `T_IQ2_XS` で、デバイス情報が有効である必要がある。down 形式も `d_covered_on()` が対応していなければならない。通常の HIP gfx12 対応は Q2_0 / IQ4_NL で、Q8_0 down は別途 `STRATA_PF_FUSED_Q8D=1` 等で対応 kernel が設定されている場合に限られる（`src/prefill/moe_fused_iq.cu:2565-2583`, `2689-2705`, `3034`）。
- small-card 用の `pf_fused_override` は HIP では適用されないと実装コメントに記載されている（`include/strata/prefill/pf_fused_override.hpp:26-29`）。CLI 引数からこの変数を上書きする読み取り箇所は見つからなかった。

## 実行時の詳細

`native_supported(gu_type, d_type)` はまずグローバル fused 設定、native 停止スイッチ、gate/up 形式のカバレッジを確認する。グローバル設定が unset 扱いなら、IQ2_XXS / IQ2_XS は `gfx12_iq2x_default()` が true の場合に既定対象形式として例外的に通過する。その後、down 形式の対応と `DevInfo` の有効性を確認し、unset 時は gfx12 (`d.w12`) のみ true を返す。値が既定を無効化した場合、他の明示 opt-in がなければこの経路は false となり、呼び出し元の通常の prefill planner が fused kernel を選ばない。MMQ に tile があれば MMQ を使い、該当形式に MMQ tile がなければ planner の dequantize + FP16 GEMM fallback になる（`src/prefill/moe_fused_iq.cu:2881-2887`, `2891-2908`, `3019-3039`; `src/prefill/prefill.cpp:1987-2011`）。

この設定はリクエスト単位ではない。`gfx12_iq2x_default()` 内の関数ローカル `static const bool` に初回評価結果が保存されるため、最初にこの判定が呼ばれた後のプロセス内環境変更は反映されない。対象値と同時に `STRATA_PF_FUSED` もその初回評価時に読み取られる（`src/prefill/moe_fused_iq.cu:2881-2887`）。

採用時は `experts_native()` の HIP 経路で IQ2_XXS / IQ2_XS の `native_w11_kernel` gate/up と down のカーネルが起動される。値そのものはカーネルへ渡されず、対応する層を fused kernel に割り当てる判定だけに使われる（`src/prefill/moe_fused_iq.cu:3114-3129`, `3164-3170`, `3200-3203`, `3219-3225`）。無効値に対するエラーや専用ログはなく、通常の層選択に戻る。別の理由で `experts_native()` が非対応の形式を直接受け取る場合は `prefill fused experts (native): types %d / %d are not covered here` を stderr に出して終了するが、これは対象変数の値エラーではない（同ファイル 3125-3128）。

`docs/SETTINGS.md` は対象を AMD 向けとして掲載している（335 行）。`docs/DETAILS.md` の 1320-1321 行は NVIDIA sm_120 の fused 既定について IQ2_XXS / IQ2_XS を MMQ のままと説明しており、HIP gfx12 の本変数の経路とは別条件である。ソースコメントには Linux gfx12 / R9700 の IQ3_XXS pack での IQ2_XXS / IQ2_XS fused 経路について、4K / 8K / 20K の prompt が MMQ 比 1.17 / 1.14 / 1.13 倍、gate と first-8K read の確認を通過したとの記載がある（`src/prefill/moe_fused_iq.cu:2876-2880`）。これはソースコメントに記された条件付き測定であり、ここで再測定した値ではない。

## ログと測定値

この環境変数の判定・無効化に固有のログはない。対象形式を通常経路に戻した際に、この変数名や無効化理由を示す警告も出さない（`src/prefill/moe_fused_iq.cu:3019-3039`）。前節の性能値と品質確認は同ファイルのコメントに記載された Linux gfx12 / R9700 / IQ3_XXS pack の結果である。

## 根拠

- `src/prefill/moe_fused_iq.cu:2876-2889` — HIP 限定の IQ2X 既定判定、読み取りとキャッシュ。
- `src/prefill/moe_fused_iq.cu:2853`, `tests/cuda/prefill_decode_golden.cu:6-25` — decode-only test build の除外条件。
- `include/strata/core/gfx12_platform_defaults.hpp:5-15` — Windows とそれ以外での gfx12 既定差。
- `src/prefill/moe_fused_iq.cu:2891-2908`, `3019-3039` — グローバル設定、停止条件、対応形式とデバイス条件。
- `src/prefill/moe_fused_iq.cu:2565-2583`, `2689-2705` — gate/up / down の形式対応。
- `src/prefill/moe_fused_iq.cu:3114-3128`, `3164-3170`, `3200-3203`, `3219-3225` — native expert 処理とカーネル起動。
- `src/prefill/prefill.cpp:1987-2011` — native fused 層を選ぶ呼び出し側と代替経路。
- `include/strata/prefill/pf_fused_override.hpp:26-29` — small-card override の対象外。
- `docs/SETTINGS.md:335`, `docs/DETAILS.md:1313-1321` — 設定一覧および CUDA sm_120 既定についての資料記載。
