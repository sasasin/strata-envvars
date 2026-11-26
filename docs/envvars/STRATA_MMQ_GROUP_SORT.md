# `STRATA_MMQ_GROUP_SORT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の prompt prefill において、GPU 上で処理する expert の並び順を、ルーティングされた行数の昇順に並べ替える opt-in フラグ。実装上の対象は MMQ 計画で適格となった層の、先頭から完全な 16 expert グループだけで、端数グループは expert ID 順を保つ。並べ替え後に expert ごとの開始位置 `off` と routing table の `slot` / `src` を再構築する。routing ID、重み、各 expert 内の行順は維持される。値の計算方式を切り替える設定ではない（`engine/src/prefill/prefill.cpp:1913-1922, 6148-6168`; `engine/src/prefill/mmq_resident_sort.hpp:82-121`）。

## 値と判定

`mmq_group_sort_requested()` は `std::getenv` の結果を `mmq_resident_sort_flag()` に渡し、値全体が文字列 `"1"` と一致する場合だけ true とする。数値変換、空白除去、大文字小文字変換はしない。unset、空文字、`0`、`true`、`01`、`1anything` はすべて false。範囲や境界値という数値概念はない（`engine/src/prefill/mmq_resident_sort.hpp:21-23, 35-38`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| フラグ判定 | false | `1` のみ | 空文字、`0`、`true`、`01`、`1 `、`1anything` など |
| `STRATA_MMQ_RESIDENT_SORT_NE` または `STRATA_MMQ_TIER_SORT` も `1` | グループソート分岐に入らない（それらの全範囲ソートが優先） | 同左 | 同左 |
| MMQ 計画が無効 | 並べ替えなし | 値が `1` でも並べ替えなし | 並べ替えなし |

MMQ 計画側では `STRATA_PREFILL_MMQ` が未設定、または `atoi(value) != 0` の場合に MMQ が有効候補となり、`0` や空文字は無効となる。ただしこれは別フラグの判定であり、本変数が MMQ を有効化することはない。build が MMQ/own-only 経路を持つか、各層の形式が経路の条件を満たすかも別途判定される（`engine/src/prefill/prefill.cpp:2026-2037, 2075-2081, 2163-2172`）。

## 有効になる条件

- CUDA/HIP の `engine/src/prefill/prefill.cpp` にある prompt MMQ 計画・実行経路を通ること。SYCL の prefill は `STRATA_MMQ_RESIDENT_SORT_NE` のみを問い合わせ、本変数を参照しない（`engine/src/prefill/prefill.cpp:2163-2172`; `engine/sycl/src/prefill/prefill.cpp:4134-4141`）。
- `STRATA_MMQ_GROUP_SORT` が厳密に `1` であり、`STRATA_MMQ_RESIDENT_SORT_NE` と `STRATA_MMQ_TIER_SORT` のどちらも厳密に `1` でないこと。後二者が有効なら `sort_all` 側が優先され、本変数による full-group 範囲制限は使われない（`engine/src/prefill/prefill.cpp:2165-2167, 6150-6153`）。
- MMQ 計画が on で、その層が計画上 MMQ 対象であること。さらに gate/up と down の両方について `mmq::whole_tiles(..., 16)` が true である必要がある。helper の契約は、各 tile が単一 block で処理され、stream-k による K 分割がなく、visible GPU 間でも tile 構成が同じであること（`engine/src/prefill/prefill.cpp:2168-2172`; `engine/include/strata/prefill/moe_mmq.hpp:158-162`）。
- 実行時に対象層で MMQ を使い、GPU-local な処理対象 expert の順序 `order` が 16 件以上あること。`order` はルーティング行数が正の expert から作られるため、モデル全体の expert 数ではなく、この層・chunk の対象数が条件となる（`engine/src/prefill/prefill.cpp:6128-6157`）。
- 並べ替え可能な対象層の expert がすべて cache 上に resident であること。helper は cache、resident 配列、空の layer stream を要求し、全 expert の resident index が非負であることを確認する。GPU peer が使われている場合も `on_peer.empty()` が必要（`engine/src/prefill/prefill.cpp:6152-6157`; `engine/src/prefill/mmq_resident_sort.hpp:63-79`）。条件を満たさない場合は並べ替えを行わず、専用の理由ログやエラーはない。
- この機能は server 固有ではなく、prompt prefill の経路で計画される。コード上、CLI 引数による本フラグの上書きはない。
- `mmq::whole_tiles` の宣言はありますが、現行 Strata checkout 内で条件を評価する実装定義は見つからず、見つかった定義は MMQ 不在時の false stub です。CMake の説明も 0.2.16 以降の CUDA/HIP build で llama.cpp の MMQ prompt kernels を含めないとしています。そのため、本 checkout の Strata 所有コードだけでは、どの build/GPU で `whole_tiles` が true になって実際にグループソートするかを確定できません。上記の適格条件は呼び出し側が要求する条件であり、実行可能な build での適用確認ではありません（`engine/include/strata/prefill/moe_mmq.hpp:158-162`; `engine/src/prefill/prefill.cpp:144-175`; `engine/src/prefill/mmq_absent.cpp:38-42`; `engine/CMakeLists.txt:104-106`）。

## 実行時の詳細

`mmq_plan()` が on の場合、`mmq_group_sort_requested()` 内の function-local `static const bool` にフラグ値を保存し、そのプロセスでは一度だけ評価する。`mmq_plan()` が off なら `on && ...` の短絡によりこの helper は呼ばれず、本変数も読み取られない。計画は static なので、評価済みなら同じプロセス内で後から環境を変更しても反映されず、層ごとの適格判定も初回計画時に一度行われる（`engine/src/prefill/mmq_resident_sort.hpp:35-38`; `engine/src/prefill/prefill.cpp:2026-2028, 2163-2177, 2187-2189`）。

実行時の `sort_full` は、全 expert sort の設定がなく、MMQ 層の `group_sort` が true で、`order.size() >= 16` の場合に true となる。ソート範囲は `order.size() - order.size() % 16` 件。範囲内を行数昇順、同数なら expert ID 昇順に sort し、端数部分は元の位置のまま残す。`off`、`slot`、`src` を作り直した後に routing table を GPU に転送する（`engine/src/prefill/prefill.cpp:6148-6178`; `engine/src/prefill/mmq_resident_sort.hpp:57-60, 98-121`）。

ソースコメントは full group の launch で expert の行が同じ bit になる設計としている一方、partial group は group の tile 数に応じた stream-k の K 境界が変わり得るため ID 順に保つと説明する（`engine/src/prefill/mmq_resident_sort.hpp:30-34`; `engine/include/strata/prefill/moe_mmq.hpp:158-162`）。ただし、前節のとおり現行 checkout には `whole_tiles` の実装定義がなく、build や実行による数値・出力比較もしていないため、実際にこの設計条件を満たす経路は確認できていない。

## ログと測定値

グループソートのフラグが `1` で、全 sort フラグが無効かつ MMQ 計画が on の場合、計画構築時に stderr へ次の行を出す。`ns` は gate/up と down の `whole_tiles` 条件をともに満たした層数、`layers` は expert layout の総層数。設定がない場合や全 sort フラグが優先される場合、この行は出ない。`whole_tiles` が false の build では行は `0 of <layers>` となる。本 checkout には同関数の適格判定実装がないため、`ns` が正になる条件はここでは確定できない。

```text
strata: prompt MMQ sorts the full expert groups (STRATA_MMQ_GROUP_SORT=1): <ns> of <layers> layers
```

同じ条件で manifest も記録する。`ns == 0` の理由文字列は `STRATA_MMQ_GROUP_SORT=1, but whole tiles are not guaranteed on every GPU`。層や chunk の cache / peer 条件によって実際の sort がない場合も、stderr の件数は `mmq_plan` 時点の形式判定数であり、chunk ごとの実行件数を表すログではない（`engine/src/prefill/prefill.cpp:2163-2177`）。関連資料 `docs/SETTINGS.md:178` は NVIDIA / AMD 向けの候補として列挙するのみで、測定値や詳しい挙動を記載していない。`docs/BATCHING.md:115-132` の opt-in 一覧にも本変数の説明はない。

## 根拠

- `engine/src/prefill/mmq_resident_sort.hpp:21-38` — 厳密な文字列判定と static cache。
- `engine/src/prefill/prefill.cpp:2026-2037, 2163-2177` — MMQ 計画、他の sort フラグとの優先関係、層単位の判定とログ。
- `engine/src/prefill/prefill.cpp:6128-6178` — expert 対象列、sort 適格条件、routing table 再構築・転送。
- `engine/src/prefill/mmq_resident_sort.hpp:57-60, 63-79, 82-121` — 範囲、resident 条件、並べ替えと routing table 更新。
- `engine/include/strata/prefill/moe_mmq.hpp:158-162` — `whole_tiles` の契約。
- `engine/src/prefill/prefill.cpp:144-175`; `engine/src/prefill/mmq_absent.cpp:38-42`; `engine/CMakeLists.txt:104-106` — MMQ 不在 stub と build 構成について確認できた範囲。
- `engine/sycl/src/prefill/prefill.cpp:4134-4141` — SYCL が本変数を参照しないこと。
- `docs/SETTINGS.md:178`; `docs/BATCHING.md:115-132` — 関連資料との照合。
