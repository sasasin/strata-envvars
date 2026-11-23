# `STRATA_KVA_GDN_NORM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

KVA が近似対象の GDN 層を state-only で処理するとき、GDN の出力正規化を含む通常の recurrence を選ぶための A/B 用スイッチ。未設定または整数変換結果が 0 の場合は `gdn_recurrence_state_only`、非 0 なら gate projection と通常の `gdn_recurrence` を使う。GDN の recurrent state を更新する一方、KVA state-only の層で residual への書き込みや MoE half を実行しない点は変わらない（`engine/src/prefill/prefill.cpp:5183-5220`）。

## 値と判定

`std::getenv` で値を取得し、`std::atoi(v) != 0` で判定する。名前の設定有無ではなく、先頭から `atoi` が変換した整数が 0 かどうかである。unset は false。空文字、数値に変換できない文字列、`0`、`0tail` は false。`1`、`-1`、`2tail` は true。先頭空白と符号は `atoi` の整数変換として扱われ、数字の後ろは判定に使われない。大文字小文字の文字列判定、全体の文字列検証、clamp はない。`atoi` が表現できない範囲の値について Strata は検査していないため、その結果は保証しない（`engine/src/prefill/prefill.cpp:5185-5188`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| GDN を含む batched prefill の実行経路 | false | `1`, `-1`, `2tail` | 空文字, `0`, `0tail`, `true`, `false`, `abc` |

## 有効になる条件

- 値が非 0 で、KVA が近似対象の GDN 層を state-only で処理するときに、通常 recurrence と gate projection が選択される。KVA は `STRATA_KVA` が未設定・空文字・先頭文字が `0` のいずれでもなく、engine がその経路を許し、cold read、全 trunk、画像なし、DFlash2 tap なし、prompt 長が `STRATA_KVA_MIN_PROMPT` 以上かつ exact suffix より 64 token を超えて長い場合に適用される。未測定のモデル形状は `STRATA_KVA_ANY_MODEL=1` がない限り対象外。split 以降の対象層と exact suffix より前の chunk にだけ近似が適用される（`engine/include/strata/prefill/kva.hpp:77-90,104-133,149-156`; `engine/src/prefill/prefill.cpp:4227-4246,4405-4408,4997-5006`）。
- `STRATA_KVA_ONLY=qsa` では GDN 層が近似対象にならないため、この変数は GDN の処理に影響しない。既定の `all` または `STRATA_KVA_ONLY=gdn` なら GDN 層も対象になり得る（`engine/include/strata/prefill/kva.hpp:89-90,183-187`; `engine/src/prefill/prefill.cpp:4997-5005`）。
- `STRATA_KVA_SKIP=moe` では attention half を含む層の計算を残すため `kva_state_only` が false となり、この変数による gate projection / recurrence の切り替えは実質的に発生しない（`engine/include/strata/prefill/kva.hpp:72-75,182`; `engine/src/prefill/prefill.cpp:5002-5005,5189-5209`）。
- state-only カーネルを持たない Metal build では KVA backend 自体が無効。KVA は CUDA/HIP の経路で、SYCL は別の prompt path を使う（`engine/include/strata/prefill/kva.hpp:43-49`; `docs/KVA.md:99-104`）。

CLI 引数によるこの変数の上書きは見つからない。KVA の適用条件と相互作用は `KVA` 側の設定（上記）に従う。

## 実行時の詳細

読み取り箇所は `engine/src/prefill/prefill.cpp:5185-5188` の一箇所。GDN 層の batched prefill 処理中、QKV projection 後に初めてこの箇所へ到達したときに評価され、関数内の `static const bool` にプロセス内で保持される。それ以降に環境を変更しても値は再読込されない。KVA 設定自体は `kva_config()` の static cache で別途プロセスにつき一度読み込まれる（`engine/include/strata/prefill/kva.hpp:149-195`）。

state-only で本変数が false のときは gate projection を省略し、正規化出力を作らない `gdn_recurrence_state_only` を実行する。true のときは gate projection を行い `gdn_recurrence` を実行する。alpha/beta projection と `gdn_gates`、GDN convolution、state の更新は両方の分岐にある。state-only の層はその後 GDN index を進め、expert transfer を解放して層処理を抜け、gated residual write と MoE half を行わない（`engine/src/prefill/prefill.cpp:5189-5220`）。projection が失敗するとこの prefill 処理は `false` を返し、projection 側が設定した `err` が呼び出し元へ伝わる（`engine/src/prefill/prefill.cpp:5190`）。値が false でも state-only でない層では通常の gate projection と recurrence が実行されるため、この変数はその通常経路を無効化しない。

## ログと測定値

この変数専用のログ、警告、失敗文言はない。KVA が適用された場合は `strata prefill: KVA on: ...` の共通ログが出るが、この変数の値や選択した GDN recurrence はログに表示されない（`engine/src/prefill/prefill.cpp:8008-8019`）。関連資料は本変数を off が既定で、full GDN recurrence を維持する設定として記載している（`docs/KVA.md:122`）。同資料の性能値は本変数単独の比較として示されていないため、ここでは個別の性能効果を断定しない。

## 根拠

- `engine/src/prefill/prefill.cpp:5183-5220` — 変数の読み取りと parse、gate projection、recurrence の選択、state-only 層の後続処理。
- `engine/src/prefill/prefill.cpp:4227-4246,4405-4408,4997-5006` — KVA 適用可否、chunk、近似対象層の判定。
- `engine/include/strata/prefill/kva.hpp:43-49,69-90,104-195` — backend、関連設定、適用条件、環境設定の読み取りと cache。
- `engine/src/prefill/prefill.cpp:8008-8019` — KVA 共通ログ。
- `docs/KVA.md:99-104,122` — backend に関する資料上の説明と本変数の記載。
