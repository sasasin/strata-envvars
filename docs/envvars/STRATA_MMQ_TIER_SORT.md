# `STRATA_MMQ_TIER_SORT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`1` を指定すると、prompt の MMQ expert 処理順を readiness tier（VRAM resident、pinned host RAM、unpinned/file staging）ごとに分け、各 tier 内では routed row 数の昇順に並べます。これは prompt の expert 順序・行テーブル・グループ形成を変える opt-in です。ルーティングされた expert ID、weight、expert 内の token row 順を変える処理ではありません。CUDA の layer-split hand-off では、別 GPU への hidden state 転送に非同期 P2P 経路を試す条件にもなります。実装は `engine/src/prefill/mmq_resident_sort.hpp` と `engine/src/prefill/prefill.cpp` にあります（`engine/src/prefill/prefill.cpp:6142-6168`, `8645-8662`, `7753-7817`）。

## 値と判定

`mmq_tier_sort_requested()` は `std::getenv` の返す文字列全体を `std::strcmp(value, "1") == 0` で比較します。数値変換、前後空白の除去、大文字小文字変換はありません。未設定と空文字は無効で、文字列が厳密に `1` の場合だけ有効です（`engine/src/prefill/mmq_resident_sort.hpp:21-23,40-45`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全呼び出し経路 | off | `1` | 空文字、`0`、`true`、`false`、` 1`、`1 `、`01`、`1anything` |

関数内 `static const bool` に最初の判定を保存します。同じプロセスで後から環境値を変更しても再評価されません。CLI 引数や設定ファイルでこの値を上書きする処理は、候補名の全参照と helper 呼び出しを確認した範囲では見つかりません（同ファイル `:42-44`; 呼び出し箇所は `engine/src/prefill/prefill.cpp:2165-2166,2179,6082,7753,8652`）。

## 有効になる条件

- **通常の chunked/staged prefill**: 対象 layer が MMQ を使い、routed expert があり、CUDA/HIP の `prefill.cpp` の MMQ walk に入る必要があります。MMQ plan は `STRATA_PREFILL_MMQ=0`、MMQ 非搭載 build、または対象 layer の format/GPU で MMQ tile が使えない場合には MMQ layer を作らず、tier sort は適用されません（`engine/src/prefill/prefill.cpp:2026-2037,2048-2079,5676`）。staged walk（`!stream_all`）では partial cache と staged expert を含む順序づけが許可されます（`engine/src/prefill/mmq_resident_sort.hpp:63-79`; 呼び出しは `engine/src/prefill/prefill.cpp:6154-6168`）。
- **stream-all walk**: MMQ が使われるほか、cache と resident map があり、layer 内の全 expert が resident で、当該 layer に別途 streamed expert がない場合だけ sort が eligible です。非 resident expert の streamed 順を保持するため、部分 resident layer は対象外です（`engine/src/prefill/mmq_resident_sort.hpp:75-79`; `engine/src/prefill/prefill.cpp:6154-6157`）。
- **layer-major prefill**: その layer が MMQ であり、FP16 fallback (`fp16_l`) と fused layer (`fz_l`) でない場合に `uniq` を tier-sort します（`engine/src/prefill/prefill.cpp:8637-8662`）。`STRATA_LM_PREFETCH` が未設定または先頭文字が `0` 以外なら、Tier 2 の expert は prefetch job index の順序要件に合わせ ID 順を保ちます。先頭文字 `0` なら Tier 2 も row 数順になります（`engine/src/prefill/prefill.cpp:8582-8586`; `engine/src/prefill/mmq_resident_sort.hpp:125-149`）。
- **他の sort 設定との関係**: `STRATA_MMQ_TIER_SORT=1` は `STRATA_MMQ_GROUP_SORT` より優先され、partial MMQ group も並べ替え対象になります。`STRATA_MMQ_RESIDENT_SORT_NE` が同時に有効でも tier sort の tier 情報が渡されます（`engine/src/prefill/prefill.cpp:2164-2167,6150-6168`）。
- **layer-split の P2P hand-off**: MMQ sort の eligibility とは別に、`hp == 0`、次 stage が別 GPU、次 stage の出力領域が有効、chunk が受け側容量以下で、両方向の CUDA peer access が可能かつ enable に成功した場合に P2P 経路を選びます。条件が不足すれば通常の host hand-off 経路です（`engine/src/prefill/prefill.cpp:7748-7769,7787-7817`）。
- SYCL 側の `engine/sycl/src/prefill/prefill.cpp` には resident sort の呼び出しがありますが、`mmq_tier_sort_requested()` の呼び出しはありません（同ファイル `:4138-4141`）。この候補変数による tier sort を SYCL 経路へ一般化できません。

## 実行時の詳細

共通 sort helper は、各 routed expert を tier 0（expert cache に resident）、tier 1（pinned host RAM）、tier 2（unpinned host/file stager）に分類し、tier 内では row 数昇順、同数なら expert ID 昇順に stable sort します。MMQ row table の `off`、`slot`、`src` を並べ替え後の順序に合わせて再構築し、token-major/rank-major の expert 内 row 順を保持します（`engine/src/prefill/mmq_resident_sort.hpp:47-55,82-123`）。通常の chunked walk では group の expert 列と対応 routing table が変わり、layer-major walk では `uniq` / contiguous row start とその後の group entry 順が変わります（`engine/src/prefill/prefill.cpp:6121-6168,8644-8662,8693-8727`）。

layer-split の P2P 条件が成立すると、現在 stage の stream を必要に応じ同期し、`cudaMemcpyPeerAsync` と event を使って次 GPU の hidden state 領域へ渡します。P2P 経路に入った後の同期、event 作成、copy が失敗すると、それぞれ `prefill: the layer split's P2P hand-off sync: ...`、`prefill: the layer split's P2P hand-off event: ...`、`prefill: the layer split's P2P hand-off copy: ...` をエラーとして返します。peer access が利用できない場合は P2P を選ばず、通常 hand-off に戻ります（`engine/src/prefill/prefill.cpp:7753-7769,7787-7817`）。

## ログと測定値

MMQ plan が有効で、この変数が有効なら、plan 初期化時に stderr へ `strata: prompt MMQ sorts experts by readiness tier and row count (STRATA_MMQ_TIER_SORT=1): <nt> of <layers> layers` を出します。`nt` は MMQ plan に載った layer 数で、plan 初期化時の表示です。MMQ が build にない場合など plan が無効なら、この行は出ません（`engine/src/prefill/prefill.cpp:2026-2027,2179-2186`）。P2P hand-off を選んだという専用の成功ログは該当箇所にありません。失敗時の文言は前節の通りです。

`docs/DETAILS.md` にこの変数の記載は見つかりませんでした。したがって性能値や token 同一性はこの文書では主張しません。

## 根拠

- `engine/src/prefill/mmq_resident_sort.hpp:21-45` — 文字列判定、値の cache。
- `engine/src/prefill/mmq_resident_sort.hpp:47-123,125-149` — readiness tier、row 数 sort と row table の再構築。
- `engine/src/prefill/prefill.cpp:2026-2037,2048-2079,2179-2186` — MMQ plan 条件と有効時ログ。
- `engine/src/prefill/prefill.cpp:6082-6168,8637-8662,8693-8727` — staged / stream-all / layer-major の適用。
- `engine/src/prefill/prefill.cpp:7748-7817` — layer-split P2P hand-off の条件と失敗経路。
- `engine/sycl/src/prefill/prefill.cpp:4138-4141` — SYCL 呼び出しは resident sort helper で、tier sort helper ではない。
