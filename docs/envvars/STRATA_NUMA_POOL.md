# `STRATA_NUMA_POOL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CPU expert pool を NUMA node ごとの2 sliceに分ける自動動作の停止スイッチです。0.2.2 以降、CPUを持つ NUMA node が2つ以上あり、`STRATA_NUMA_SPLIT` が未設定なら、Strata は NUMA split を自動で試します。`STRATA_NUMA_POOL` に停止値を設定するとこの自動 split を止め、`STRATA_NUMA_SPLIT=1` や `test` による要求も優先して無効にします。

この変数自身が worker 数や配置を指定するわけではありません。停止値でない設定値も split の明示要求にはならず、`STRATA_NUMA_SPLIT` が未設定で2 node以上なら自動試行を許します。

## 値と判定

`numa_switch_off()` は文字列全体を小文字化してから比較します。前後の空白を除去せず、数値変換もしません。

| `STRATA_NUMA_POOL` | 判定 |
|---|---|
| 未設定、空文字 | 停止値ではない。`STRATA_NUMA_SPLIT` も未設定で、CPUを持つnodeが2つ以上なら自動試行 |
| `0`, `off`, `false`, `no` | 大文字小文字を区別せず停止値。例: `OFF`, `False`, `NO` も該当 |
| その他の文字列 | 停止値ではない。`1` だけを有効値とする parse ではない。例: `1`, `true`, `0 `, `0anything` は停止値ではない |

停止値かどうかは `STRATA_NUMA_SPLIT` との組み合わせでも効き方が変わります。

| NUMA node 数と `STRATA_NUMA_SPLIT` | 停止値を設定したとき |
|---|---|
| 2以上 | 常に split を止める。`STRATA_NUMA_SPLIT=1` / `test` より優先 |
| 0または1、`STRATA_NUMA_SPLIT` が空または未設定 | split 要求がないため、pool choice は従来どおり。停止ログも出さない |
| 0または1、`STRATA_NUMA_SPLIT` が非空 | その明示要求を止め、停止ログを出す |

Linux では sysfs の `node*/cpulist` を調べ、CPUを持つ node 数を数えます。見つからない場合などの0件は1に丸められます。Windows では `GetNumaHighestNodeNumber()` の戻り値に1を足して数えます。その他のOSでは1 nodeとして扱われます。

## 有効になる条件

停止値でなければ、次のどちらかで NUMA split の通常経路が判断されます。

- CPUを持つ node が2つ以上で、`STRATA_NUMA_SPLIT` が未設定または空: 自動 split を試行。
- `STRATA_NUMA_SPLIT` に非空値がある: 既存の明示設定経路。`STRATA_NUMA_POOL` は停止値でない限り、その値の意味を変えません。

自動 split は node 数だけでは有効になりません。pool の thread が2つ以上であること、pinning が有効で全 thread の CPU と NUMA node を特定できること、thread がちょうど2 nodeにまたがり、slice 数が極端に偏らないことが必要です。Linux 以外では実 split を実行できません。また `STRATA_EXCHANGE_ROTATE=1` のときは固定 slot を必要とする split を拒否します。明示経路の通常値は `STRATA_NUMA_SPLIT=1` または `test` で、他の非空文字列は未知値として split を無効にします。

自動試行が成立しない場合、pool は試行前の topology に戻して通常の worker 数・配置で動きます。`STRATA_NUMA_POOL` が停止値でないことだけでは split の成立を保証しません。

## 実行時の詳細

値は `ExpertPool` のコンストラクターで `std::getenv()` により読み取られ、同時に NUMA node 数を調べます。リクエストごとの読み取りや static cache ではありません。実行中の環境変更は既存 pool の判断を変えず、後から構築される pool は構築時の環境を読みます。

停止値かつ停止条件に該当すると stderr に `strata cpu pool: NUMA pool off (STRATA_NUMA_POOL=0): <node数の説明>, the pool runs as before` 形式の行を出し、`STRATA_NUMA_SPLIT` の値を無効化します。停止値でない設定で自動 split が成立すると `strata cpu pool: NUMA pool on: N NUMA nodes found, one slice of the pool per node (STRATA_NUMA_POOL=0 turns it off)` と続けて slice の node と thread 数を出します。自動試行が要件を満たさないと `NUMA pool off: <理由> (N NUMA nodes found), the pool runs as before` を出します。

split が成立すると pool は各 node の slice ごとに native expert の行計算を分配します。Linux の `FileExpertSource` では、GGUF-mapped native pack の complement を page-locked する経路で、slice ごとの範囲を node 上の pinned thread が first-touch する配置処理も試します。配置条件を満たさない pack、arena expert source、または page-lock されない経路ではメモリ配置が行われないか失敗警告が出ます。pool の split 自体と、expert memory の node-local 配置の成否は別です。

## 文書・測定との照合

`docs/DETAILS.md` は停止値を `0`, `off`, `false`, `no` と説明し、2 node以上での自動試行、Linux限定の split、成立条件を記載しています。実装の停止文字列 parse と一致します。ただし同資料の「1 nodeでは何も読まず、何も記録しない」という説明は現行ソースと厳密には一致しません。`ExpertPool` 構築時に環境変数と node 数は調べますが、明示 split 要求もない1 node環境では `STRATA_NUMA_POOL` に停止値を設定しても choice は `Unchanged` で、pool の挙動とログは変わりません。

`docs/DETAILS.md` には dual Xeon Gold 6226 / RTX 3090 での decode 測定（12 sample median、split 59.3 tok/s、0.2.0 default 54.05 tok/s、+9.7%）が記録されています。同資料はこの NUMA split をプロジェクト側では2 socket機で実行していないとも記しています。これは資料に記載された報告値であり、今回のソース調査で再測定・検証した値ではありません。

## 根拠

- `include/strata/kernels/cpu/numa_pool.hpp:29-35,65-84` — 停止値の正確な parse、停止条件と優先順位、自動選択。
- `src/kernels/cpu/pool.cpp:593-625,743-760` — Linux / Windows / その他の node 数、構築時の読み取り、停止値による `STRATA_NUMA_SPLIT` の無効化。
- `include/strata/kernels/cpu/numa_pool.hpp:94-149` — pinning、rotate、2 node、slice balance の成立条件。
- `src/kernels/cpu/pool.cpp:819-839,856-910` — 自動試行時の rollback、通常経路への fallback、ログと split 作成。
- `src/core/expert_source.cpp:571-615,648-659,3731-3765,3780-3783` — expert memory の配置条件、page-lock の paced path、配置失敗時の警告。
- `docs/DETAILS.md:2185-2206` — 設計説明と測定条件、未検証範囲。
