# `STRATA_Q36_NO_MMQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 エンジンの prompt expert 経路選択で、MMQ を各レイヤーの候補から外す開発・調整用スイッチ。`strata-q36` と、Qwen3.6 (`qwen35moe`) の GGUF を `strata` から実行する専用エンジン `engine/src/qwen35/q36_engine.cu` の `Engine::init()` が参照する。MMQ をビルドしていない場合や、fused 経路が先に選ばれるレイヤーには効果がない（`engine/cmake/strata_gpu_engine.cmake:565-583`; `engine/src/program/generate.cpp:3804-3818`; `engine/src/qwen35/q36_engine.cu:1962-1968,1996-2029`）。

この変数が無効にするのは Qwen3.6 の prompt expert 用 MMQ 候補である。decode 経路全般や他モデルの MMQ 設定を変える読み取りは、この名前については見つからない。MMQ を候補から外したレイヤーは、条件に応じて Strata の int8 expert kernels または native grouped kernels に回る（`engine/include/strata/kernels/q36_prompt_route.hpp:3-9,23-29`）。

## 値と判定

`std::getenv(...) == nullptr` だけを調べる。文字列を parse せず、値の内容、数値としての妥当性、大文字小文字、空白を検査しない。そのため、**未設定だけ**が MMQ を許可し、空文字を含む設定済みの値は何であっても MMQ を候補から外す（`engine/src/qwen35/q36_engine.cu:1996`）。

| 条件 | unset | MMQ を候補にする値 | MMQ を候補から外す値 |
| --- | --- | --- | --- |
| MMQ 対応 build | MMQ は他の条件も満たせば候補 | `STRATA_Q36_NO_MMQ` 未設定 | 空文字、`0`、`1`、`false`、`0anything`、その他すべての設定値 |
| MMQ 非対応 build | 候補なし | なし | 設定有無による追加の変化なし |

ここでいう「候補」は実際の選択を保証しない。MMQ がビルド済みでも、レイヤーの gate/up と down の型が MMQ に対応し、各行数が `MMQ::fits()` を満たす場合にだけ MMQ 候補になる（`engine/src/qwen35/q36_engine.cu:1997-1999,2024-2025`; `engine/include/strata/prefill/moe_mmq.hpp:15-24`）。

## 有効になる条件

- Qwen3.6 専用 engine が組み込まれた CUDA または HIP build で、Qwen3.6 (`qwen35moe`) をその engine で初期化すること。HIP gfx906 build ではこの engine target 自体を作らない（`engine/cmake/strata_gpu_engine.cmake:565-583`）。
- `MMQ::built()` が true であること。false の場合は `mmq_avail` が false なので、この変数を設定しても MMQ の有無は変化しない（`engine/src/qwen35/q36_engine.cu:1996,2014-2015`）。
- 少なくとも対象レイヤーで fused 経路が先に選ばれず、gate/up と down の型が `MMQ::supported()` に該当し、`MMQ::fits()` が両方の寸法を受け入れること（`engine/src/qwen35/q36_engine.cu:1997-2011,2024-2025`）。
- `STRATA_EXPERT_I8=1` で対応 int8 経路が使えるレイヤーでは、その経路が MMQ より先に選ばれるため、この変数を未設定にしても当該レイヤーは MMQ に行かない。MMQ が候補から外れた後も、`STRATA_EXPERT_I8` の状態と int8 kernel の対応可否により int8 または grouped が選ばれる（`engine/include/strata/kernels/q36_prompt_route.hpp:5-9,23-29`; `engine/include/strata/kernels/i8_expert_rule.hpp:29-37`）。
- 1 レイヤーでも最終経路が grouped のみになると、エンジン全体で `use_pf` を false にし、全レイヤーを native grouped 経路に戻す。したがって、MMQ を外した結果 int8 の対応外レイヤーが残る場合、ほかのレイヤーが MMQ / int8 対応でも prompt path 全体が切り替わる（`engine/include/strata/kernels/q36_prompt_route.hpp:32-34`; `engine/src/qwen35/q36_engine.cu:2022-2041`）。

## 実行時の詳細

`Engine::init()` の初期化時に一度読み、`mmq_avail` に値を保持してレイヤーごとの `mmq_takes` 判定に渡す。request ごと・prompt chunk ごとの再読み取りや、この変数名を保存する static cache はない。選択済み engine の初期化後に環境を変更しても、この `mmq_avail` の判定は変わらない（`engine/src/qwen35/q36_engine.cu:1962-1968,1996-2029`）。

レイヤーごとの順序は fused → `STRATA_EXPERT_I8=1` で対応する int8 → MMQ → switch が 0 でない状態で対応する int8 → native grouped。MMQ を禁止した場合、最後の2つのどちらかへ進む。MMQ または int8 の経路を使う場合はそれらの prompt 用バッファを初期化する。全レイヤーに grouped 以外の経路があれば hybrid prompt path を使い、そうでなければ全 prompt chunk を grouped kernels に送る（`engine/include/strata/kernels/q36_prompt_route.hpp:23-34`; `engine/src/qwen35/q36_engine.cu:2022-2075`）。

このコードから確認できる対象は prompt expert の kernel 経路であり、token 選択や出力が同一であるという保証や、性能差の測定は示されていない。`docs/QWEN36.md` は専用 engine の利用経路と prompt chunk を説明するが、このスイッチの測定値は記載していない（`docs/QWEN36.md:7-24`; `engine/src/qwen35/q36_engine.cu:1996-2041`）。

## ログと測定値

初期化時に選ばれた経路の集計が stderr に出る。int8 経路が1層以上なら `strata-q36: prompt experts: %zu of %zu layers on the fused int8 kernels, %zu on our int8 kernels, %zu on MMQ (int8)`、全層 fused なら `strata-q36: prompt experts on the fused int8 kernels`、fused と MMQ の混在なら `strata-q36: prompt experts on the fused int8 kernels (%zu of %zu layers), the rest on MMQ (int8)`、その他は `strata-q36: prompt experts on %s`（`MMQ (int8)` または `the native grouped kernels`）となる。これらは最終経路を示すもので、変数の設定値自体を表示するログではない（`engine/src/qwen35/q36_engine.cu:2077-2086`）。

この変数による性能・精度の測定値は、対象ソースおよび関連する `docs/QWEN36.md` / `docs/DETAILS.md` から確認できなかった。エラー時に限らない、変数専用の警告や終了経路もない。

## 根拠

- `engine/src/qwen35/q36_engine.cu:1962-1968,1996-2029` — 初期化時の設定有無判定、MMQ と int8 のレイヤー別ルート選択。
- `engine/include/strata/kernels/q36_prompt_route.hpp:3-9,19-34` — ルートの優先順位と prompt path 全体の条件。
- `engine/src/qwen35/q36_engine.cu:2033-2042,2058-2075` — grouped 経路による prompt path の fallback と MMQ 用リソース初期化。
- `engine/src/qwen35/q36_engine.cu:2077-2086` — stderr の経路ログ。
- `engine/cmake/strata_gpu_engine.cmake:565-583` — Qwen3.6 engine の build target と gfx906 除外。
- `engine/include/strata/kernels/i8_expert_rule.hpp:29-37` — 相互作用する `STRATA_EXPERT_I8` の parse と MMQ 非対応 build での既定値。
