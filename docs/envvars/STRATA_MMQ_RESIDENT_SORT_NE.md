# `STRATA_MMQ_RESIDENT_SORT_NE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

MMQ を使う prompt prefill の MoE 層で、常駐 expert の処理順を、その層で各 expert に割り当てられた routed row 数の昇順に並べ替える opt-in です。CUDA系実装では `STRATA_MMQ_GROUP_SORT` が選ぶ「16 expert の完全な group だけ」の並べ替えより優先され、最後の不完全 group も含めて active expert 全体を並べ替えます。SYCL にも同じ resident-sort helper を使う経路があります。

並べ替えは expert ID・routing weight・各 expert 内の row 順を変更せず、MMQ に渡す `order` と、それに整合する `off`、`slot`、`src` を作り直します。環境変数だけで MMQ が有効になるわけではありません。

## 値と判定

値は `std::getenv` で取得し、`std::strcmp(value, "1") == 0` で文字列全体を比較します（`src/prefill/mmq_resident_sort.hpp:13-19`）。数値変換、前後空白の除去、大文字小文字変換はありません。

| 環境値 | 要求フラグ |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`true`、`01`、`1x`、その他の文字列 | 無効 |

要求フラグは `mmq_resident_sort_requested()` 内の `static const bool` に保存されます。初回評価後にプロセス環境を変更しても再読込されません。CLI 引数による上書きはこの helper にはありません。

## 有効になる条件

要求フラグが有効でも、層ごとに次の条件を満たさなければ並べ替えません。

- その層が MMQ を使う (`use_mmq`)。
- cache と層の resident 情報があり、expert 数が正である。
- resident 情報上、層の**全 expert**が常駐している（`layer_resident[e] >= 0`）。一部だけ常駐する層では無効。
- CUDA系の prompt prefill では peer 分割/peer 処理がない（`on_peer.empty()`）。
- stream-all 経路では、その層に stream 対象がない。実装は `!stream_all || seq_start[l] == seq_start[l + 1]` を helper に渡す。

CUDA系ではさらに、`STRATA_MMQ_GROUP_SORT` が有効でも resident-sort の要求が優先されます。resident-sort が要求されると `sort_full` は偽になり、resident-sort が適格なら `order` 全体を対象にします。不適格なら `STRATA_MMQ_GROUP_SORT` の group-sort に切り替わるのではなく、その層の並べ替え自体が行われません (`src/prefill/prefill.cpp:1404-1415,4552-4566`)。SYCL 側には `STRATA_MMQ_GROUP_SORT` による代替分岐がなく、resident-sort の適格性だけを確認します (`sycl/src/prefill/prefill.cpp:3700-3707`)。

MMQ 自体が利用可能であることも必要です。CUDA系の MMQ plan は `mmq::built()`、`STRATA_PREFILL_MMQ`、層の形式・shape 適合性から層ごとに作られます。`STRATA_PREFILL_MMQ=0` は MMQ plan を無効にし、未設定なら build が MMQ を含む場合に有効候補になります (`src/prefill/prefill.cpp:77-91,1348-1380`)。SYCL でも呼び出し側の `use_mmq` が偽なら適格性判定を通りません。

## 実行時の詳細

CUDA系では各 prompt prefill 層で routed ID の出現数 `m.cnt` を数え、resident/stream/peer/CPU の分類と expert の `order` を作った後に判定します。適格なら `mmq_resident_sort_rows` が `order` の対象範囲を `count` 昇順（同数なら expert ID 昇順）に安定 sort し、`off` を再構成してから routing table の `slot` と `src` を再構築します。`sort_all` の経路では `sort_full` の span 制限がないため、partial group も対象です (`src/prefill/prefill.cpp:4537-4566`, `src/prefill/mmq_resident_sort.hpp:51-79`)。この後 `slot` と `src` は GPU に転送されます (`src/prefill/prefill.cpp:4567-4575`)。

SYCL も routing 情報と order の作成後、同じ helper で適格性を判定し、適格なら `slot/src/off/order` を再構築してから routing table を転送します (`sycl/src/prefill/prefill.cpp:3693-3732`)。helper は host 側の sort と配列再構成を行います。device 計算式や精度を変える処理はこの helper にはありません (`src/prefill/mmq_resident_sort.hpp:1,56-79`)。

この変数専用の有効・無効ログや警告、無効値エラーは見つかりません。並べ替えが不適格でも、その理由をこの変数名で出力する分岐はありません。CUDA系の MMQ plan には `STRATA_MMQ_GROUP_SORT` が有効で resident-sort が要求されていない場合に group-sort の層数を stderr に出すログがありますが、resident-sort の動作を示すログではありません (`src/prefill/prefill.cpp:1404-1415`)。

## 根拠

- 文字列判定と static cache: `src/prefill/mmq_resident_sort.hpp:13-19`。
- 適格条件: `src/prefill/mmq_resident_sort.hpp:38-49`。
- stable sort と routing table の再構築: `src/prefill/mmq_resident_sort.hpp:51-79`。
- CUDA系 MMQ plan の作成と group-sort との優先関係: `src/prefill/prefill.cpp:1348-1418,4552-4575`。
- SYCL 側の呼び出しと転送: `sycl/src/prefill/prefill.cpp:3693-3732`。
