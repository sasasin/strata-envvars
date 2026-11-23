# `STRATA_MMQ_RESIDENT_SORT_NE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

MMQ を使う prompt prefill の expert 行テーブルを、expert ID 順ではなく、ルーティングされた行数が少ない expert から並べ直します。これにより MMQ の expert group の構成順が変わります。並べ替え時に `off`、`slot`、`src` を再構築するため、expert ごとの行対応と expert 内の元の行順は維持されます。CUDA/HIP 共通 prefill 実装では部分 group も含めた全 `order` が対象で、SYCL 実装も同じ helper を呼びます (`engine/src/prefill/mmq_resident_sort.hpp:91-123`, `engine/src/prefill/prefill.cpp:6142-6168`, `engine/sycl/src/prefill/prefill.cpp:4134-4141`)。

## 値と判定

共通 helper は `std::getenv` の結果が null でなく、文字列全体が `"1"` と一致するときだけ有効にします。数値変換や trim はありません。したがって unset、空文字、`0`、`true`、`01`、`1anything`、前後に空白のある `1` は無効で、大文字小文字による別扱いもありません (`engine/src/prefill/mmq_resident_sort.hpp:21-28`)。

| 条件（build / 実行経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 共通 prefill または SYCL prefill の helper が呼ばれる場合 | OFF | 文字列全体が `1` | 空文字、`0`、`true`、`01`、`1anything`、` 1` |

## 有効になる条件

- 対象 layer が MMQ expert 経路を使う必要があります。共通実装の `use_mmq` が false のとき helper は対象外と判定します (`engine/src/prefill/mmq_resident_sort.hpp:63-80`)。通常の MMQ 計画はビルドに MMQ があり、`STRATA_PREFILL_MMQ` が unset または `atoi` で 0 以外の場合に限って MMQ を有効にし、layer ごとに両 product の tile 対応も確認します (`engine/src/prefill/prefill.cpp:2026-2037,2048-2077`)。
- layer の全 expert が GPU cache に resident である必要があります。cache と `layer_resident` が存在し、`layer_stream_empty` が true で、全 expert の resident slot が非負の場合だけ有効です。非 resident expert が一つでもあれば並べ替えません (`engine/src/prefill/mmq_resident_sort.hpp:63-80`)。
- CUDA/HIP 共通 prefill 経路では peer expert が割り当てられた layer は要求を false として渡すため並べ替えません (`engine/src/prefill/prefill.cpp:6151-6157`)。SYCL 経路も `on_peer` が空であることを要求します (`engine/sycl/src/prefill/prefill.cpp:4138-4141`)。
- streamed walk (`stream_all`) では layer の stream 範囲が空であることも必要です。非 streamed walk では caller が `layer_stream_empty` を true として渡しますが、resident cache と全 expert resident 条件は引き続き適用されます (`engine/src/prefill/prefill.cpp:6154-6157`; `engine/sycl/src/prefill/prefill.cpp:4138-4141`)。
- `STRATA_MMQ_TIER_SORT=1` も有効な CUDA/HIP 共通経路では、並べ替え helper に readiness tier 情報も渡され、tier 順（VRAM resident、pinned RAM、その他）の後に行数順となります。全 expert resident 条件が満たされると全員同じ tier なので行数順です (`engine/src/prefill/prefill.cpp:6151-6168`; comparator: `engine/src/prefill/mmq_resident_sort.hpp:97-105`)。
- CUDA/HIP 共通実装では、この変数が有効だと `STRATA_MMQ_GROUP_SORT` のみを使う枝を抑止します。resident sort は全 expert 順を扱うので、group sort の全 group 条件に依存しません (`engine/src/prefill/prefill.cpp:2163-2176`)。

## 実行時の詳細

値は `mmq_resident_sort_requested()` 内の関数ローカル `static const bool` で初回評価時に一度だけ読み取られ、そのプロセス内で cache されます。したがって初回評価後に環境を変更しても反映されません。CUDA/HIP 共通実装では MMQ plan 構築中に group-sort の排他条件で参照される場合があり、実際の sort 判定では prefill の expert 行テーブル構築中に参照されます。SYCL では prefill の行テーブル構築中に参照されます (`engine/src/prefill/mmq_resident_sort.hpp:25-28`; `engine/src/prefill/prefill.cpp:2026-2037,2163-2167,6128-6168`; `engine/sycl/src/prefill/prefill.cpp:4127-4141`)。

並べ替え対象はルーティングされた expert の `order` です。比較は行数昇順、同数なら expert ID 昇順です。その順に `off` の expert 開始位置を更新し、元の route 配列から `slot` と `src` を作り直します。各 expert 内の行順は token/rank traversal のままです。CUDA/HIP 共通経路ではこの並びが後続の MMQ group walk に使われます (`engine/src/prefill/mmq_resident_sort.hpp:82-123`; caller: `engine/src/prefill/prefill.cpp:6121-6179`)。この変数専用の fallback エラーや終了経路はなく、条件を満たさない layer は既存の順序で進みます。

## ログと測定値

この変数を有効・無効にしたことを示す専用 stdout/stderr ログは確認できません。CUDA/HIP 実装の近接ログは `STRATA_MMQ_GROUP_SORT` と `STRATA_MMQ_TIER_SORT` の別設定に対するものです (`engine/src/prefill/prefill.cpp:2174-2185`)。Strata の `docs/DETAILS.md` に本変数固有の説明または測定値は見つかりませんでした。

## 根拠

- 値の厳密比較と static cache: `engine/src/prefill/mmq_resident_sort.hpp:21-28`
- sort の適用条件: `engine/src/prefill/mmq_resident_sort.hpp:63-80`
- sort 比較、行テーブルの再構築: `engine/src/prefill/mmq_resident_sort.hpp:82-123`
- CUDA/HIP 共通経路、他の sort 設定との優先関係: `engine/src/prefill/prefill.cpp:2163-2185,6128-6179`
- SYCL 経路: `engine/sycl/src/prefill/prefill.cpp:4127-4141`
