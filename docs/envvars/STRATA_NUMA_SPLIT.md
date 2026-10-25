# `STRATA_NUMA_SPLIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU expert pool のスレッドと一部の expert 行処理を、2つの NUMA slice に分けます。実 NUMA モードでは、各 slice のスレッドをそれぞれの NUMA node に固定し、native expert の行範囲を node ごとに処理します。常に起動時の `ExpertPool` 構築時に一度判定し、その pool の存続中は再評価しません。

## 値と判定

値は数値として parse せず、文字列全体を大文字小文字を区別して比較します。

| 値 | 判定 |
|---|---|
| 未設定または空文字 | 明示的な split 要求なし。CPU node が2つ以上で、`STRATA_NUMA_POOL` が無効値（`0` / `off` / `false` / `no`）でなければ自動試行。それ以外は split なし。 |
| `0` | split なし。通常この値自体のログは出ません。 |
| `1` | 実 NUMA split を要求。実行条件を満たさなければ理由を stderr に出して split を断念します。 |
| `test` | thread index を交互に2 slice へ割り当てるテスト用 split。実 NUMA node の参照やメモリ配置はしません。 |
| その他（例: `true`, `01`, `Test`, 空白付きの値） | 無効値。`strata cpu pool: NUMA split off: unknown STRATA_NUMA_SPLIT value '…' (use 1 or test)` を stderr に出します。 |

`STRATA_NUMA_POOL=0`、`off`、`false`、`no`（大文字小文字を区別しない）は、対象マシンでの split を無効化し、`STRATA_NUMA_SPLIT=1` / `test` より優先されます。ただし `STRATA_NUMA_POOL` の無効値が効くのは、CPU node が2つ以上ある場合、または `STRATA_NUMA_SPLIT` に空でない値が設定されている場合です。単一 node で両方とも未設定なら従来の pool 経路のままで、何もログしません。

## 有効になる条件

- 自動試行は、CPU を持つ NUMA node が2つ以上あり、`STRATA_NUMA_SPLIT` が未設定または空文字で、`STRATA_NUMA_POOL` が無効値でないときに行います。`STRATA_NUMA_POOL` に `1` など無効値以外の文字列が設定されていても自動試行します。試行時は全 socket を使う worker 数を計画し、split が成立しなければ元の topology と通常の worker 計画へ戻します。
- 実 NUMA split は Linux のみです。`STRATA_NUMA_SPLIT=1` で要求しても、Windows など Linux 以外では `the split needs Linux` の理由で実行されません。node 数の数え方は Linux では sysfs の node `cpulist`、Windows では `GetNumaHighestNodeNumber`、その他の OS では1です。
- 実 split には2つ以上の pool thread、pinning、全 thread の既知の CPU/node、ちょうど2つの node、均衡した slice が必要です。`STRATA_EXCHANGE_ROTATE=1` の場合も固定 slot が必要なため拒否します。
- `STRATA_NUMA_SPLIT=1` を明示した経路では、実 split が拒否されても worker 数計画と CPU の interleave は split 要求ありとして進みます。自動試行経路だけが失敗時に元の topology と worker 数計画へ戻ります。
- `test` は実 node 条件と pinning を必要としませんが、pool の合計 thread 数は2以上必要です。これは slice ごとの scheduling 用です。
- NUMA pool の分割は pool の native row phases（modes 5/6）を node ごとの行範囲と task counter に分けます。NUMA 配置処理は resident complement 経路に結びついています。`docs/DETAILS.md` は arena 経路と `cudaHostAlloc` 経路では expert の配置 split を行わないと説明しています。

## 実行時の詳細

`ExpertPool` の constructor が `getenv("STRATA_NUMA_SPLIT")` を読み、同時に node 数と `STRATA_NUMA_POOL` を確認します。split の有無は worker 数計画の決定前に評価されます。auto モードでは interleave した worker 候補で split 可否を先に判定し、失敗したら topology をコピー前の状態に戻します。実 split の可否は worker thread 起動前に確定し、以後変更しません。

有効時は worker と host thread を node ごとに slice へ割り当てます。`test` は thread `j` を `j % 2` の slice に割り当てます。pool は起動時に `strata cpu pool: NUMA split on: ...`、テストモードでは `strata cpu pool: NUMA split on (test, no real nodes): ...` を stderr に出します。自動試行時にはその前に `strata cpu pool: NUMA pool on: ...` も出ます。自動試行ができない場合は `strata cpu pool: NUMA pool off: <理由> (<N> NUMA nodes found), the pool runs as before`、明示要求の失敗は `strata cpu pool: NUMA split off: <理由>` を出します。

実 NUMA 配置のロード時処理は `FileExpertSource` が行います。配置が始まるとモデルファイルの cached pages を解放し、必要な空き容量を確認し、complement を段階的に page-lock する経路を選びます。`STRATA_PIN_GUARD=0` はこの配置経路では上書きされます。詳細と配置失敗時の記録は `docs/DETAILS.md` にあります。

## 根拠

- `src/kernels/cpu/pool.cpp:616-640` — OS ごとの node 数と、Linux 限定の実 split 判定。`STRATA_EXCHANGE_ROTATE` は文字列全体が `1` の場合に拒否条件となります。
- `src/kernels/cpu/pool.cpp:743-760,819-842,856-910` — 読み取り時点、値の比較、自動試行の fallback、明示要求時の worker 計画、ログ、および worker 起動前に固定する split plan。
- `include/strata/kernels/cpu/numa_pool.hpp:29-35,55-84,94-149` — `STRATA_NUMA_POOL` の無効値、auto/off の優先順位、実 split の pinning/node/均衡条件。
- `include/strata/kernels/cpu/pool.hpp:169-181,370-374` — `test` の意味、native row phases の slice 処理。
- `src/core/expert_source.cpp:3733-3765` — resident complement の NUMA 配置が選ばれたときの cache drop、空き容量確認、paced/page-lock 経路と `STRATA_PIN_GUARD=0` の扱い。
- `docs/DETAILS.md:2185-2205` — NUMA 配置が対象とする expert 経路、ログ、資料内の測定条件。記載された性能値は同資料の報告であり、今回の調査で再測定した値ではありません。
