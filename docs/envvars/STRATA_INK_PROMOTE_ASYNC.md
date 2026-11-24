# `STRATA_INK_PROMOTE_ASYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

HIP 版 Inkling の hybrid expert VRAM cache で、非同期 DMA 中の expert をすぐ使えるか poll するかを切り替える。未設定時は DMA 完了まで待つ。値を有効にすると、完了していないコピーを待たず、その呼び出しでは CPU 側の expert 経路へ回す。また victim slot 選択ではコピー中の slot を飛ばす。`ink_hip_promote_async_poll()` が判定し、`HipHybridController::probe_ready()` と `prefetch_async()` が使用する（`engine/src/inkling2/hip/ink_hip_promote_policy.h:18-26`、`engine/src/inkling2/hip/ink_hip_hybrid.hpp:425-444,447-479`）。

この設定は HIP 実装にのみ読み取り箇所がある。コードコメントは CPU と GPU の計算経路が同じ丸めにならず、poll による配置判断はタイミング依存になると説明している。したがって async poll は同じ経路・結果の再現性を保証しない。生成結果が必ず変わる、または特定の性能向上があるとはソースから断定できない（`engine/src/inkling2/hip/ink_hip_promote_policy.h:3-10`）。

## 値と判定

`std::getenv` で得た文字列の先頭一文字だけを比較し、`'1'` の場合だけ true。それ以外の内容は parse せず、空白除去、大文字小文字変換、数値検証、警告もない（`engine/src/inkling2/hip/ink_hip_promote_policy.h:18-22`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP Inkling backend | false（待機） | `1`, `1anything` | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1`, `01` |

値の既定値は false（待機）。CLI 引数や別の環境変数による上書きはこの設定の読み取り・判定経路にはない。無効な文字列は単に false として扱われる（同 `ink_hip_promote_policy.h:18-22`）。

## 有効になる条件

- HIP 対応でビルドされた Inkling を AMD HIP backend で実行すること。この名前を読む Strata 所有コードは `engine/src/inkling2/hip/ink_hip_promote_policy.h` のみで、SYCL 側の実装はない（同 `ink_hip_promote_policy.h:22`、`engine/src/inkling2/hip/CMakeLists.txt:30-32,74-82,96-100`）。
- モデルの expert が VRAM に全て収まらず、RAM 側 expert を持つため hybrid controller が初期化されること。controller は `max_exp_bytes > 0 && vram_experts_loaded_ < n_dir` の場合に初期化される（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1395-1401`）。
- 実際に未完了 DMA を含む cache slot に当たること。cache ring の slot 数は `cache_budget_bytes / slot_stride_` で決まり、0 slot なら promotion cache はない（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:358-389`）。hybrid cache 予算の確保自体も expert 全体が VRAM 予算を超える場合に限られる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1052-1071`）。
- Prefill の RAM expert path と decode の RAM expert path の両方で cache probe が行われる。prefetch は既に RAM にある expert body の一部について起動される。MX8 RAM expert は `is_core_loop_repeat=false` で呼び、decayed frequency が閾値に達したときに限り promotion される（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4468-4487,4514-4521`、`engine/src/inkling2/hip/ink_hip_hybrid.hpp:447-460`）。
- VRAM resident expert には適用されない。SSD cold-store から読み出す経路も `expert_ram_bodies_` に既にある body と異なる分岐で読み出し、ここで直接 `prefetch_async()` を呼ばない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4482-4498,4517-4532`）。

## 実行時の詳細

`probe_ready()` は対象が cache slot にあり DMA 中なら、既定では `hipEventSynchronize()` で完了を待つ。有効値では `hipEventQuery()` を呼び、`hipSuccess` 以外なら cache hit にせず null を返す。呼び出し側はその expert を GPU cache 側へ割り当てず、RAM/CPU または通常の staging 経路へ進む。待機または poll が成功すると `dma_in_flight` を解除し、cache hit として GPU device pointer を返す（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:427-444`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4468-4477,4658-4670`）。

victim slot の選択でも、既定では DMA 中の slot の event を同期してから候補に含める。有効値では poll が未完了の slot を飛ばす。全 slot が使用中または poll 未完了なら victim が決まらず、その prefetch は行わない（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:461-479`）。

読み取り関数自体は都度 `getenv` を呼ぶが、実行時の2箇所はそれぞれ関数内 `static const bool` に保存する。その箇所に初めて入った時点で値が確定し、以後そのプロセス内で環境を変更しても、その static の判定は更新されない。二つの static は別々に初期化される（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:433-434,467-468`）。

## ログと測定値

この環境変数専用の有効・無効・不正値ログはない。`hipEventQuery()` が `hipSuccess` 以外を返した場合は cache hit にせず、待機側の `hipEventSynchronize()` が成功しない場合も `probe_ready()` は null を返す。victim 選択では同期失敗または query 未完了の slot を候補から飛ばす。これらの event 結果を理由とした専用ログや終了処理はない（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:435-440,468-474`）。

設定の効果に関する条件付き測定値は、参照したソースおよび `docs/SETTINGS.md` に記載がない。資料上は `AMD` 向けの `text` 型として登録されているが、実装上の判定は上記の先頭文字比較である（`docs/SETTINGS.md:404`）。

## 根拠

- `engine/src/inkling2/hip/ink_hip_promote_policy.h:1-26` — 値判定と設計上の既定動作。
- `engine/src/inkling2/hip/ink_hip_hybrid.hpp:358-402,425-497` — hybrid/cache の初期化、static cache、probe と victim 選択。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1052-1071,1395-1401,4468-4521,4658-4670` — hybrid 条件、expert 経路と呼び出し元。
- `engine/src/inkling2/hip/CMakeLists.txt:30-32,74-100` — HIP backend のコンパイルとライブラリ構成。
- `docs/SETTINGS.md:404` — 設定一覧との照合。
