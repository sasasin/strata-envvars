# `STRATA_PF_FUSED_NATIVE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

native 形式の MoE prompt expert が対応する fused int8 kernel を選べるかを拒否するための切替です。`STRATA_PF_FUSED_NATIVE` が設定され、その先頭文字が `0` の場合、`native_supported()` は他の条件を調べる前に `false` を返します。その結果、対象 layer は fused native kernel の候補から外れ、通常の dispatch に戻ります。MMQ が使える layer は MMQ、使えない layer は FP16 経路などを選ぶ既存の fallback に従います。この変数自体は fused kernel を有効化せず、`0` 以外の値も有効化を保証しません。CUDA/HIP の実装は `engine/src/prefill/moe_fused_iq.cu:3415-3432` にあります。

## 値と判定

関数内 `static const bool` の初期化時に `std::getenv` で読み、値の先頭 1 文字だけを比較します。文字列全体の parse、数値検査、空白除去、大文字小文字変換はありません。

| 条件 | unset | 対象経路を拒否する値 | 拒否しない値の例 |
|---|---|---|---|
| `moe_fused_iq.cu` が組み込まれた CUDA/HIP 実装 | 拒否しない（この変数による追加 veto なし） | 先頭文字が `0`。例: `0`, `00`, `0anything` | 空文字、`1`, `true`, `false`, ` 0`, `2` |

空文字は未設定とは区別されますが、先頭文字が `0` ではないため拒否しません。`false` も拒否値ではありません。先頭が `0` なら後続文字列の妥当性にかかわらず拒否します。別の値が有効かどうかは `native_supported()` 内の形式・device・他設定の条件で決まります（同ファイル `:3416-3419,3425-3432`）。

## 有効になる条件

- fused native kernels を含む CUDA または HIP の build で `native_supported()` が実装版に到達する必要があります。該当コードは CUDA backend の `strata_pf_own` に含まれ（`engine/cmake/backends/cuda.cmake:135-142`）、HIP backend でも同ソースを含みます（`engine/cmake/backends/hip.cmake:30-44`）。fused 実装を含まない build では `prefill.cpp` の stub が常に `false` を返します（`engine/src/prefill/prefill.cpp:180-200`）。
- `STRATA_PF_FUSED_NATIVE` が先頭 `0` でなければ veto はありませんが、対象形式の kernel がその device/build で対応・setup 済みであり、`STRATA_PF_FUSED` 等の通常条件を満たす必要があります。CUDA/HIP で対応形式・device 条件を評価する分岐は `engine/src/prefill/moe_fused_iq.cu:3433-3561` 以下にあります。
- `STRATA_PF_FUSED` が `native_supported()` のキャッシュ値として `0` になる場合、または small-card prompt override が `0` の場合は、この変数が `0` でなくても `false` になります（同ファイル `:3425-3432`）。
- `native_supported()` の結果は layer ごとの prompt dispatch 判定に使われます。通常の MoE prompt walk では `fused_nat` 条件の一つであり、偽なら native fused kernel を選びません（`engine/src/prefill/prefill.cpp:5686-5704`）。MMQ のない形式で native fused を使う計画も同じ判定に依存します（同ファイル `:2062-2072`）。
- Qwen3.6 用の形状別 kernel copy は `moe_fused_iq.cu` を別 namespace で include するため、同じ veto 判定を持ち、独立した関数内 static cache を使います（`engine/src/prefill/moe_fused_iq_q36.cu:1-6,33-39`）。

## 実行時の詳細

環境値は `native_supported()` が最初に呼ばれたときに関数内 `static` として評価され、そのプロセス内の同じ実装 copy では以後キャッシュされます。実行中に環境値を変更しても、その copy の判定には反映されません。Qwen3.6 用 copy は別 translation unit 内で元ソースを再コンパイルするため、初回評価も別です（`engine/src/prefill/moe_fused_iq.cu:3415-3419`; `engine/src/prefill/moe_fused_iq_q36.cu:33-39`）。

`native_supported()` が `false` になると fused native 対応判定から外れます。通常経路では `fused_nat` が成立せず、layer は MMQ または既存の FP16 fallback に進みます（`engine/src/prefill/prefill.cpp:2062-2072,5698-5704`）。native pack 全体で fused layout を使えるかの判定も全 layer に対する `native_supported()` に依存するため、この変数で一部 layer が拒否されると fused layout を選ばない場合があります（同ファイル `:782-806`）。

## ログと測定値

この変数の veto 自体について、該当コードに専用ログ、警告、終了処理はありません。呼び出し側が返り値に応じて別の経路を選びます（`engine/src/prefill/moe_fused_iq.cu:3415-3432`; `engine/src/prefill/prefill.cpp:5698-5704`）。既存資料には関連する fused prompt 経路の説明・測定がありますが、ここではこの変数を設定した場合の独立した測定値として扱える根拠は確認できません。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:3415-3432` — 対象変数の読み取り、先頭文字判定、他の fused 条件との合成。
- `engine/src/prefill/moe_fused_iq.cu:3433-3561` — 形式、backend、device、kernel setup ごとの追加条件。
- `engine/src/prefill/prefill.cpp:180-200,2062-2072,5686-5704,782-806` — 実装のない build の stub、layer dispatch/fallback、native pack 全体の layout 判定。
- `engine/src/prefill/moe_fused_iq_q36.cu:1-6,33-39` — 同じ実装の Qwen3.6 用 copy。
- `engine/cmake/backends/cuda.cmake:135-142`; `engine/cmake/backends/hip.cmake:30-44` — CUDA/HIP backend のソース組み込み。
