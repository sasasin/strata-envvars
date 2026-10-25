# `STRATA_MMQ_RESIDENT_SORT_NE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

MMQ を使う prefill で、層内の全 expert が resident の場合に、実行する expert の順番を routed row 数の昇順に並べ替えます。MMQ の expert group ごとの最大 row 数を抑えることを狙った opt-in の最適化です。CUDA 系 `src/prefill/prefill.cpp` と SYCL 系 `sycl/src/prefill/prefill.cpp` が同じ helper を呼びます。

## 値と判定

値は `std::strcmp(value, "1") == 0` で文字列全体を比較します。

| 値 | 要求状態 |
|---|---|
| 未設定 | OFF |
| `1` | ON |
| 空文字、`0`、`true`、`01`、`1 ` など | OFF |

空白除去、数値変換、部分一致、大文字小文字変換はありません。判定結果は `mmq_resident_sort_requested()` の関数内 `static const bool` に保存されます。最初の呼び出し後にプロセス環境を変更しても再評価しません。根拠: `src/prefill/mmq_resident_sort.hpp:12-19`。

## 有効になる条件

値が `1` でも、各 layer で次の条件がすべて成立するときだけ並べ替えます。

- MMQ 経路 (`use_mmq`) である。
- resident cache (`m.cache`) と layer の resident 状態配列がある。
- expert 数が正であり、**その layer の全 expert** の resident 状態が 0 以上である。route が 0 件の expert もこの判定に含みます。
- peer 配置がなく (`on_peer.empty()`)、peer 向けの expert 並べ替えが不要である。
- `stream_all` の場合は、その layer の stream 範囲が空である。

`lay.native` は helper に渡されますが helper 内で明示的に未使用とされており、native layout 自体は除外条件ではありません。条件が不足する layer は従来の ID 順の `order` と row 配置を使います。根拠: `src/prefill/mmq_resident_sort.hpp:21-32`, `src/prefill/prefill.cpp:3254-3269`, `sycl/src/prefill/prefill.cpp:3396-3410`。

## 実行時の詳細

各 prefill layer で route ID を集計した後、`order` には routed row 数が正の expert が ID 順で入ります。条件を満たした場合、stable sort の比較キーを `(count[expert], expert ID)` として `order` を row 数昇順に並べ替えます。同じ row 数なら ID 昇順です。

並べ替え後、helper は `off` を expert ごとの新しい row 開始位置に再構築し、元の route ID 配列を走査して `slot` と `src` を作り直します。走査順は変えず、expert 内の row 順も維持します。route ID と routing weight の配列そのものは書き換えません。その後 `slot` / `src` と MMQ の group bounds を通常の経路でデバイスに転送し、MMQ が並べ替えた `order` で group を構成します。したがって変更対象は expert の処理順と row/group の配置であり、GPU 演算の採用条件や route の選択を変える制御ではありません。根拠: `src/prefill/mmq_resident_sort.hpp:34-59`, `src/prefill/prefill.cpp:3247-3269,3270-3278,3337-3360`, `sycl/src/prefill/prefill.cpp:3389-3412,3437-3467`。

環境変数の判定結果は process 内でキャッシュされ、layer ごとに eligibility は評価されます。ソースにこの opt-in 専用のログ出力は見当たりません。`docs/DETAILS.md` および `docs/` 内の Markdown にはこの変数の説明がなく、ここでは性能向上や出力の同一性を測定済み事実としては述べません。

## 根拠

- `src/prefill/mmq_resident_sort.hpp:12-19` — 完全一致の値判定と process 内 cache。
- `src/prefill/mmq_resident_sort.hpp:21-32` — eligibility の条件。
- `src/prefill/mmq_resident_sort.hpp:38-59` — expert の順序付けと `off` / `slot` / `src` の再構築。
- `src/prefill/prefill.cpp:3254-3269,3270-3278,3337-3360` — CUDA 系 prefill での呼び出しと MMQ group bounds への反映。
- `sycl/src/prefill/prefill.cpp:3396-3412,3437-3467` — SYCL 系 prefill での呼び出しと MMQ group bounds への反映。
