# `STRATA_MMQ_GROUP_SORT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の prompt prefill で MMQ が使われる場合に、GPU に常駐する experts の順序を routed row 数の昇順に並べ替え、16 expert 単位の完全なグループをその順で実行します。各 expert の routed row 数に近い `max_rows` のグループにまとめる狙いです。最終の16未満の端数グループは ID 順を維持し、その結果を含む MMQ の計算順も従来のままにします。

## 値と判定

`mmq_group_sort_requested()` は `getenv()` の値を `strcmp(value, "1") == 0` で判定します。文字列全体が ASCII の `1` 一文字と一致するときだけ要求扱いです。

| 値 | 要求扱い |
|---|---|
| 未設定 | いいえ |
| `1` | はい |
| 空文字、`0`、`01`、`1x`、`true`、前後に空白がある値 | いいえ |

要求値は関数内の `static const bool` に保存されます。初回評価後にプロセス内で環境変数を変更しても再評価されません。

## 有効になる条件

要求があっても、次の条件が必要です。

- `mmq::built()` が真で、対象 layer が `STRATA_PREFILL_MMQ` による MMQ 経路を使う。MMQ が使えないビルドや MMQ 対象外の layer では並べ替えない。
- `STRATA_MMQ_RESIDENT_SORT_NE` が有効でない。この変数が完全一致の `1` で有効な場合、そちらが優先され、こちらのグループ単位モードは計画されない。
- 両方の積（gate/up と down）について、その layer の形式・形状が全 GPU で `mmq::whole_tiles()` の条件を満たす。条件を満たさない layer は対象外。
- 実行時に対象 layer の全 experts が cache に常駐し、peer GPU の経路を使っていない。stream-all の場合はその layer に streamed expert がない。
- 並べ替え対象の GPU expert 数が16以上である。

コード上、`-DSTRATA_MMQ_TAB=ON` はこの変数の判定条件ではありません。`STRATA_MMQ_TAB` は pointer-table MMQ を構築する別機能です。`docs/BATCHING.md:127` はこの変数も同ビルドオプションが必要であるかのように同じ表の項目へ記していますが、ここで確認した分岐ではその依存は確認できません。MMQ 自体が構築・利用可能である必要はあります。

## 実行時の詳細

prefill の MMQ plan は static 初期化され、環境変数の要求と layer ごとの `whole_tiles` 判定を plan に記録します。変数が要求され、`mmq_plan()` が有効な MMQ 経路で評価されると、stderr に `strata: prompt MMQ sorts the full expert groups (STRATA_MMQ_GROUP_SORT=1): N of M layers` を出します。`N` は対象条件を満たした MMQ layer 数、`M` はレイアウト上の layer 数です。全ての実行条件を満たす layer があることを保証するログではありません。

実行対象 layer では `order` の先頭から `order.size() - order.size() % 16` 件だけを `stable_sort` します。キーは routed row 数の昇順、同数の場合は expert ID の昇順です。残る端数は元の ID 順のままです。並べ替え後に expert offset と routing slot/source table を再構築し、トークン・rank 順の expert 内 row 順は保ちます。eligibility 条件を満たさないときは元の順序を使います。

## 根拠

- 値の完全一致と static cache: `src/prefill/mmq_resident_sort.hpp:13-15,27-30`。
- MMQ plan、別変数との優先関係、GPU・型ごとの layer 判定とログ: `src/prefill/prefill.cpp:1129-1138,1175-1189`。
- 16 expert group と端数維持の並べ替え、常駐・peer・stream 条件: `src/prefill/prefill.cpp:3678-3700`, `src/prefill/mmq_resident_sort.hpp:22-48,60-78`。
- `whole_tiles` が対象デバイス、quant type、tile・stream-k 条件を調べる実装: `src/prefill/moe_mmq.cu:508-538`。MMQ がないビルドの stub は `src/prefill/prefill.cpp:64-94`。
- 関連資料: `docs/BATCHING.md:127`。この記述は `STRATA_MMQ_TAB` と本変数を同じ条件として記載していますが、ソース上では `STRATA_MMQ_TAB` の有効性を本変数の分岐条件にしていません。
