# `STRATA_SPEC_MIN_TEMP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP draft layer が sampled request の draft をサンプリングする方式へ切り替わる最低温度を指定します。request の温度がこの値以上なら、既に有効化されている coupled draft / probabilistic draft を使います。下回ると draft layer は argmax draft を使います。

この変数だけでは sampled drafting を有効にしません。MTP の利用に加えて、`STRATA_SPEC_COUPLED`、`STRATA_SPEC_PROB`、または `--coupled-draft` によって coupled sampler の setup が有効になっている必要があります。実装は CUDA MTP drafter にあります。`src/core/mtp.cpp:525-543,565-573,576-581`、`include/strata/core/coupled_draft.hpp:57-79`、`src/program/generate.cpp:2233,4504,11097,12952-12959`。

## 値と判定

値は `std::atof()` で `float` に変換され、範囲検証や clamp はありません。環境変数を unset にした場合は `0.0` です。空文字列や数値に変換できない文字列も `atof()` の結果が `0.0` になります。数値の後ろに文字が続いても数値部分が変換されます（例: `0.9tail` は `0.9`）。`include/strata/core/spec_prob.hpp:67-73`。

| 設定例 | しきい値 | sampled request への結果 |
|---|---:|---|
| unset / 空文字 / `abc` | `0.0` | 温度が正なら条件を満たす |
| `0.9` / `0.9tail` | `0.9` | 温度 `>= 0.9` で条件を満たす |
| `-1` | `-1.0` | 正の温度なら条件を満たす |
| `2` | `2.0` | 通常の温度 `0 < temperature < 2` では条件を満たさない |

draft sampling の有効条件は `!sp.greedy && sp.temperature > 0.0f && sp.temperature >= spec_min_temp()` です。したがって境界値は含みます。Greedy または温度 0 以下では、しきい値が負でも sampled drafting は有効になりません。`src/core/mtp.cpp:576-581`。

## 有効になる条件

- MTP drafter を使用し、`bind()` が成功していること。生成側は MTP オプションが指定されている場合に bind し、各 request の sampler 設定を drafter に渡します（`src/program/generate.cpp:4504,11097,12952-12959`）。
- coupled sampler の setup が有効であること。`STRATA_SPEC_COUPLED` と `STRATA_SPEC_PROB` は unset・空文字・文字列全体が `0` の場合に無効、それ以外の設定値で有効です。CLI の `--coupled-draft` も setup を有効にし、`--no-coupled-draft` は CLI 側の状態を解除します。ただし `STRATA_SPEC_PROB` が有効なら probabilistic draft が setup されます（`include/strata/core/coupled_draft.hpp:57-83`、`src/core/mtp.cpp:682`）。
- draft logits の幅が sampler の上限を超える場合は、stderr に `strata mtp: STRATA_SPEC_COUPLED: ... too wide ...; argmax drafts` を出して coupled sampler を使わず setup を継続します。一方、buffer 確保など `setup_coupled()` 自体が失敗した場合は `bind()` が失敗し、通常の argmax draft への fallback ではなく生成エラーになります（`src/core/mtp.cpp:525-543,682`）。

## 実行時の詳細

`spec_min_temp()` は関数内の `static const float` に変換結果を保存します。値を読むのは初回呼び出し時だけで、以後プロセス内で環境を書き換えても反映されません。対して温度との比較は `set_draft_sampling()` の呼び出しごとに行われます。serve 経路では各 request の sampler 設定を渡し、通常の generate 経路では生成開始時に設定を渡します（`src/core/mtp.cpp:576-581`、`src/program/generate.cpp:11077-11097,12952-12959`）。

条件を満たさない request では `coupled_active_` が false になり、MTP drafter は coupled sampler ではなく通常の argmax draft 経路へ進みます。条件を満たす場合、`STRATA_SPEC_PROB` が有効なら draft head の分布から draft をサンプリングして verifier に分布を渡し、そうでなければ target の sampler chain と draw を用いる coupled draft sampling に進みます（`src/core/mtp.cpp:576-581,999-1009`、`src/program/generate.cpp:12046-12049,13211-13217`）。最終的に出力 token を選ぶのは verify window です。

## 文書との照合

`docs/DETAILS.md:1260` は `STRATA_SPEC_MIN_TEMP=0.9` を「より高温の request に sampled drafting を制限する」例として挙げており、しきい値比較の実装と一致します。同段落の速度比較は RTX 3060、IQ3_XXS、200-token の story/code 回答、temperature 0.3 / 0.7 / 1.0 など記載条件下の測定であり、他の環境の性能を示すものではありません。数値変換と既定値の根拠はソース実装です。

## 根拠

- `include/strata/core/spec_prob.hpp:64-73` — 既定値、`atof()` による変換、しきい値の説明。
- `include/strata/core/coupled_draft.hpp:57-83` — coupled / probabilistic sampler を setup する環境変数と CLI 状態。
- `src/core/mtp.cpp:525-543,565-581,682,999-1009` — setup 条件、温度 gate、draft sampler の選択。
- `src/program/generate.cpp:11077-11097,12046-12049,12952-12959,13211-13217` — request 設定、MTP 呼び出し、verify への分布引き渡し。
- `docs/DETAILS.md:1260` — 利用例と条件付き性能記録。
