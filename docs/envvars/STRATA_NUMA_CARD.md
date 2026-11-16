# `STRATA_NUMA_CARD`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux の非 Metal GPU 実行で、Strata プロセスの CPU affinity を、実行に使う GPU と同じ NUMA node の CPU に自動で絞る処理を止めるスイッチです。未設定時はこの処理を有効にしますが、実際の制限は安全条件をすべて満たした場合だけ行います。GPU 上の計算や CPU pool の NUMA 分割そのものを直接切り替える設定ではありません。適用は `src/program/generate.cpp` の初期化中、pool・host thread・stager の作成および大きな確保より前です（`src/program/generate.cpp:4319-4329`, `include/strata/kernels/cpu/card_node.hpp:1-12`）。

## 値と判定

`std::getenv` の結果を `card_node_switch_off` に渡します。未設定 (`nullptr`) は無効化しません。設定値は文字列全体を小文字化してから比較し、`0`、`off`、`false`、`no` と完全一致する場合だけ機能を止めます（`include/strata/kernels/cpu/card_node.hpp:315-321`）。空文字や `1`、`on`、`yes`、`true`、`2`、`00`、`0anything`、前後に空白のある値はどの停止文字列とも一致しないため、停止しません。比較では大文字小文字を区別しません（例: `OFF` も停止）。数値変換、数値範囲判定、trim はありません。

| 実行条件 | unset | 設定時に NUMA 制限処理を止める値 | 止めない値の例 |
|---|---|---|---|
| Linux かつ `STRATA_GPU_METAL` 以外 | 停止しない（自動判定へ進む） | `0`, `off`, `false`, `no`（大小文字不問） | 空文字、`1`, `true`, `yes`, `00`, `0anything`, ` off ` |
| その他の OS または Metal build | この変数を読むコードがコンパイル対象外 | 該当なし | 該当なし |

## 有効になる条件

変数を未設定または停止文字列以外にしても、以下を満たさなければ CPU affinity は変わりません。判定は `decide_card_node` が最初に該当した理由で終了します（`include/strata/kernels/cpu/card_node.hpp:107-173`）。

- Linux であり、`STRATA_GPU_METAL` build ではないこと（`src/program/generate.cpp:4319`）。
- CPU のある NUMA node が 2 つ以上あり、プロセスの現在の CPU mask が複数 node にまたがっていること。既に `taskset` / `numactl` などで 1 node に限られている場合や、CPU の node が特定できない場合はそのままです（`src/program/generate.cpp:4327-4334`, `include/strata/kernels/cpu/card_node.hpp:121-130`）。
- 実行に使う GPU が少なくとも 1 台あり、対象 GPU の PCI NUMA node がすべて既知かつ同じであること。通常は `STRATA_PRIMARY_DEVICE` が指す primary GPU を調べます。`--layer-split`、`--peer-device`、または remote expert cache が有効なら、見えている GPU 全台を調べます。複数 GPU の node が異なる場合は制限しません（`src/program/generate.cpp:4335-4357`, `include/strata/kernels/cpu/card_node.hpp:131-137`）。
- `/proc/self/status` からメモリ node の許可一覧を読めた場合、GPU の node がその一覧に含まれること。さらに `/sys` から node の空きメモリが読め、`--max-context` に基づく必要量以上であること。必要量は `max(max_context, 0) * 12,700 + 2 GiB` です（`src/program/generate.cpp:4333-4334,4357-4358`, `include/strata/kernels/cpu/card_node.hpp:47-56,138-147`）。
- 利用者が CPU 配置を明示していないこと。`--pool-cores` / `STRATA_POOL_CORES`、空でない `STRATA_NUMA_SPLIT`、または `auto` / `off` 以外の `--aux-cpus` / `STRATA_AUX_CPUS` がある場合は尊重して制限しません（`src/program/generate.cpp:4359-4368`, `include/strata/kernels/cpu/card_node.hpp:148`）。
- hybrid CPU ではないこと。また、GPU node 上に現在の process mask と pool の要件を満たす CPU があること。既定 pool worker 数を減らす必要がある場合は制限しません。`--pool-workers N` 指定時は node に `N + 1` 物理 core が必要です（`src/program/generate.cpp:4369-4379`, `include/strata/kernels/cpu/card_node.hpp:149-170`）。

`STRATA_TRACE` が設定されていると、判定が有効・無効どちらでも診断行を出します。空文字も「設定あり」です。`STRATA_TRACE` が未設定なら、適用を見送った理由を含め、この処理固有のログは出ません（`src/program/generate.cpp:4388-4397`）。

## 実行時の詳細

この値は `generate` 初期化経路に入るたびに `getenv` で読み、関数 static には保存しません。NUMA 判定と affinity 変更はその初期化時に一度行われ、既に動いているプロセスで後から環境値だけを変更しても、適用済み affinity は再評価されません。子プロセスへの環境継承や上書きは、この設定の処理では行いません（`src/program/generate.cpp:4319-4328,4381-4387`）。

停止文字列が設定されている場合は node 探索を行わず、affinity を変更しません。その他の値では `/sys` と `/proc/self/status` を読み、条件が整えば `restrict_process_cpus` が現在存在する全 thread の affinity を GPU node 内の CPU との積集合に変えます。対象 CPU がない thread は維持され、変更を拒否された thread も処理は継続します。後から生成される thread は作成元から制限を継承します（`include/strata/kernels/cpu/card_node.hpp:323-351`）。

停止値でない場合、判定が不成立でも現在の thread CPU mask を `set_home_cpus` に保存します。これは後から affinity を広げる background copy / checkpoint helper の範囲を、GPU node に絞った場合はその CPU 群に、判定不成立時は開始時の mask に保つためです。停止値の場合は home mask を設定せず、従来の広げ方を維持します（`src/program/generate.cpp:4384-4387`, `include/strata/platform/home_cpus.hpp:3-9,34-60`）。

この処理に CLI 引数による直接の上書きはありません。CPU 配置を明示する前掲の CLI 引数や環境変数は、自動 affinity 制限を見送らせます。`STRATA_NUMA_POOL` / `STRATA_NUMA_SPLIT` は pool 計画にも使われますが、ここでは空でない `STRATA_NUMA_SPLIT` が明示配置の印として制限を抑止する点に限って関係します（`src/program/generate.cpp:4360-4379`）。

## ログと測定値

`STRATA_TRACE` が設定されていると、stderr に次の形式で出ます。`restricted to CPUs ...` または `left as is: ...` の理由、変更 thread 数、拒否数が値に応じて入ります。

```text
strata trace: card node: %d nodes with CPUs; cards: %s; card node free %lld MiB, pinned need %llu MiB; pool workers now %d, on the card's node %d (%d cores); %s%s (%d threads changed, %d refused)
```

このログは `src/program/generate.cpp:4388-4397` の文字列です。`STRATA_NUMA_CARD` 自体が直接 stderr に警告・エラーを出したり、失敗時に終了コードを変えたりする経路はありません。`docs/DETAILS.md` の「Two sockets and NUMA」は `STRATA_NUMA_POOL` / `STRATA_NUMA_SPLIT` による CPU pool の分割を説明しており、この affinity 制限の測定値や個別条件は記載していません（`docs/DETAILS.md:1206-1224`）。

## 根拠

- `src/program/generate.cpp:4319-4399` — build guard、値の読み取り、GPU/node 情報の収集、判定・適用、trace 出力。
- `include/strata/kernels/cpu/card_node.hpp:107-173,315-351` — 適用条件、値比較、process thread affinity の変更。
- `include/strata/platform/home_cpus.hpp:3-9,34-60` — 判定後に記録する CPU 範囲と後続 thread への適用。
- `docs/SETTINGS.md:331` — 設定一覧上の候補記載。実挙動の根拠には使用していません。
- `docs/DETAILS.md:1206-1224` — NUMA pool split の記述との照合。
