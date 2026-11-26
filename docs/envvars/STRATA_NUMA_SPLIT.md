# `STRATA_NUMA_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CPU expert pool の NUMA 分割を指定する。`1` は実 NUMA node による分割を明示し、`test` は実 node やメモリ配置を使わずスレッド番号で 2 slice を作る。`0` は明示的分割を無効にする値だが、NUMA node が 2 つ以上あり変数が未設定なら pool は自動で分割を試す。その自動動作を止めるのは `STRATA_NUMA_POOL` の off 値である。`ExpertPool` は pool のコンストラクター内で分割を確定し、ワーカー開始後には変更しない（`engine/src/kernels/cpu/pool.cpp:803-821, 924-979`、`engine/include/strata/kernels/cpu/pool.hpp:170-182`）。

実分割が成立すると、pool の native expert row phase（mode 5/6）の仕事を 2 slice に分け、各 slice の thread が自分の task counter から処理する。Linux の native mapped pack では、GPU に常駐しない expert complement の各 slice も対応 node に first-touch する経路がある。pool の分割とメモリ配置は別判定であり、配置できなくても pool 分割自体は有効のまま remote read の可能性をログに出す（`engine/include/strata/kernels/cpu/pool.hpp:408-419`、`engine/src/kernels/cpu/pool.cpp:1328-1335`、`engine/src/core/expert_source.cpp:669-712`）。

## 値と判定

pool コンストラクターが `std::getenv` で値を読み、`1` または `test` を文字列全体の `strcmp` で判定する。数値変換や大文字小文字変換、前後空白の除去はない。空文字は pool の選択処理では未設定と同じだが、後続の既知値判定では off と同じ扱いになる。任意の非空文字列は無効値として分割しない（`engine/src/kernels/cpu/pool.cpp:813-820, 924-930`、`engine/include/strata/kernels/cpu/numa_pool.hpp:65-83`）。

| 条件 | 未設定（または空文字） | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 通常の `ExpertPool` 判定 | Linux で CPU を持つ NUMA node が 2 以上なら自動分割を試行。それ以外は従来どおり | 完全一致の `1` は実 node 分割、`test` は擬似 2 slice | `0` は分割なし。`true`、`01`、`1 `、`TEST` などは未知値として分割なし。空文字は未設定相当 |
| `STRATA_NUMA_POOL` も設定 | 同上。ただし `STRATA_NUMA_POOL` が `0` / `off` / `false` / `no`（大文字小文字不問）なら、2 node 以上または split 値が非空のとき split を抑止 | `1` / `test` でも `STRATA_NUMA_POOL` の off が優先 | off 以外の `STRATA_NUMA_POOL` 値は split 判定を変えない |
| Windows / その他 OS | Windows は `STRATA_NUMA_ARENA` が未設定/先頭文字 `1` 以外なら、未設定 split の自動試行を拒否。その他 OS は実 split を拒否 | Windows は `STRATA_NUMA_ARENA` の先頭文字が `1` または split が完全一致 `1` なら実分割を試す。`test` は実 node 判定を通らず擬似分割 | その他 OS の実分割は未対応。Windows の `1` も他の実 split 条件を満たさなければ拒否 |

`STRATA_NUMA_POOL` の off 値比較は文字列全体を小文字化して行う。たとえば `OFF` は off だが、空文字、`0 `、`false1` は off ではない。off 判定の優先条件は `nodes >= 2 || split_set` であり、1 node で split も未設定なら off ログは出ず従来経路のまま（`engine/include/strata/kernels/cpu/numa_pool.hpp:29-35, 65-83`）。

## 有効になる条件

- `1` の実分割には、pool に少なくとも 2 thread（workers と `host_works` の host を合わせた数）が必要。全 thread が pin 対象 core を持ち、既知の NUMA node に属し、ちょうど 2 node にまたがる必要がある。Windows では加えて `STRATA_NUMA_ARENA` の先頭文字が `1`、または `STRATA_NUMA_SPLIT` が完全一致 `1` であることが必要。OS の分岐は Linux / Windows のみである（`engine/src/kernels/cpu/pool.cpp:671-694, 932-954`、`engine/include/strata/kernels/cpu/numa_pool.hpp:97-149`）。
- node ごとの slice thread 数は、少ない側が多い側の半分以上でなければならない。`STRATA_EXCHANGE_ROTATE=1` は expert slot を移動させる設定として実分割を拒否する。`STRATA_EXCHANGE_ROTATE` も文字列全体が `1` の場合だけ該当する（`engine/include/strata/kernels/cpu/numa_pool.hpp:94-149`）。
- `STRATA_NUMA_SPLIT=test` は上記の実 node 条件を適用せず、thread index の偶奇で slice を作る。ただし thread 数が 2 未満なら分割しない。テスト専用ビルド限定の guard はなく、通常の実行コードにもこの値の分岐がある（`engine/src/kernels/cpu/pool.cpp:930-938`）。
- Linux では `STRATA_NUMA_SPLIT` が unset/空で、CPU を持つ NUMA node が 2 以上、かつ `STRATA_NUMA_POOL` が split を止めない場合、自動分割を試す。自動試行が失敗すると、core 順と既定 worker 数を元に戻して通常 pool として続行する（`engine/include/strata/kernels/cpu/numa_pool.hpp:71-83`、`engine/src/kernels/cpu/pool.cpp:883-900`）。
- 自動・明示分割時の既定 worker 数は、socket/node をまたぐ worker 計画から選ばれる。`--pool-workers N` は正数ならその数を優先し、`--pool-cores` または `STRATA_POOL_CORES` の明示 core list があれば利用 core とその数が使われる。明示 core list の順序は分割時にも並べ替えないため、2 node を十分にまたがない list は分割拒否になり得る。`--pool-affinity` / `--no-host-worker` も候補 core と pool thread 数に影響するため、間接的に分割条件を変える（`engine/src/kernels/cpu/pool.cpp:823-881, 932-954`）。
- pool の分割は全 pool で使われるが、node ごとの row dispatch は native expert row phase の mode 5/6 に限られる。Linux でモデル complement の NUMA 配置が動くのは、配置処理が page-locked complement を作る経路に入り、`NumaComplementPlacement` が per-role byte 情報などを検証できた場合。`test` は実メモリ配置を行わない。別の arena path では pool split が有効でもモデル memory の per-node 配置は行われない（`engine/src/core/expert_source.cpp:669-712, 4328-4372`、`engine/src/program/generate.cpp:9001-9015`）。

## 実行時の詳細

1. `ExpertPool` 構築時に `STRATA_NUMA_SPLIT` と `STRATA_NUMA_POOL` を読み、node 数と pool 計画をもとに自動 / 明示 / off を決める。Linux node 数は sysfs 上で CPU を持つ node directory の数、Windows は `GetNumaHighestNodeNumber` の結果を使う。他 OS は 1 node 扱い（`engine/src/kernels/cpu/pool.cpp:658-668, 803-821`、`engine/include/strata/kernels/cpu/numa_pool.hpp:37-52`）。
2. `1` または自動分割候補なら worker core の順序を node/package 間で交互にし、thread 数を決めて実 node 判定する。`--pool-workers` の明示数は維持される。`--pool-cores` が有効なら利用者指定順を維持する（`engine/src/kernels/cpu/pool.cpp:823-903`）。
3. 分割 plan は pool worker 起動前に確定する。実行中に環境変数を変更しても現在の pool には反映されない。次回 pool 構築時に改めて読み取る。pool の生存中は `active_numa_split()` がその plan を公開し、pool destructor で所有状態を解除する（`engine/src/kernels/cpu/pool.cpp:924-1003`、`engine/include/strata/kernels/cpu/pool.hpp:180-182`）。
4. 実分割中の native mode 5/6 は各 thread の slice に対応する row 範囲と task counter を使う。他 mode は共通 pool head を使う。`test` は 2 slice の scheduler 経路だけを作り、実 node は割り当てず、complement placement も行わない（`engine/include/strata/kernels/cpu/pool.hpp:408-419`、`engine/src/kernels/cpu/pool.cpp:1328-1335`、`engine/src/core/expert_source.cpp:673-675`）。
5. `generate.cpp` は `STRATA_NUMA_SPLIT` の非空設定を「配置をユーザーが指定した」理由として card-node 判定にも渡す。ここでは値を分割の on/off として解釈しない。また `STRATA_NUMA_POOL` を含む pool 判定を使って card-node 判定用 worker 数を計算する（`engine/src/program/generate.cpp:4655-4675`）。この読み取りは pool の判定より早い場合があり、環境値を cache せずその場で読む。

## ログと測定値

- 自動分割が成立すると `strata cpu pool: NUMA pool on: ...`、実分割が成立すると `strata cpu pool: NUMA split on: slice 0 = node ...`、test 分割では `strata cpu pool: NUMA split on (test, no real nodes): ...` を stderr に出す。自動試行の失敗は `NUMA pool off: <理由> (... NUMA nodes found), the pool runs as before`、明示分割の失敗は `NUMA split off: <理由>`。未知値は `unknown STRATA_NUMA_SPLIT value '<値>' (use 1 or test)` と出力する（`engine/src/kernels/cpu/pool.cpp:883-900, 924-979`）。
- `STRATA_NUMA_POOL` が off で分割を止めたときは `strata cpu pool: NUMA pool off (STRATA_NUMA_POOL=0): ...` を出力する（`engine/include/strata/kernels/cpu/numa_pool.hpp:74-79`）。
- 実分割が有効でも complement placement に失敗・不足がある場合、`FileExpertSource: WARNING: NUMA placement FAILED: ...`、空き RAM 不足のリスクには `NUMA placement at risk`、登録ページの node 配置確認が 95% 未満なら `slice ... has ... (< 95 %...)` を stderr に出す。配置できない場合も pool split は解除されず、ログは remote reads の可能性を示す（`engine/src/core/expert_source.cpp:684-687, 748-756, 802-830`）。
- 分割が off の既定値や 1 node の unset 経路では、対応する off/on 行を出さない。1 node かつ `STRATA_NUMA_POOL` off だけでは off 条件を満たさず、元の pool のまま静かに進む（`engine/include/strata/kernels/cpu/numa_pool.hpp:71-83`）。
- `docs/DETAILS.md` の「NUMA-aware CPU pool」節は Linux の自動分割など概略を説明しているが、現行コードは Windows の明示分割経路も持つ。上記は調査対象 commit のコードに基づく（`docs/DETAILS.md:1391-1401`、`engine/src/kernels/cpu/pool.cpp:671-694`）。性能値は文書化していない。

## 根拠

- 値の選択・優先順位・ログ: `engine/include/strata/kernels/cpu/numa_pool.hpp:29-35, 65-83`; `engine/src/kernels/cpu/pool.cpp:803-821, 924-979`
- 実分割条件と balance: `engine/src/kernels/cpu/pool.cpp:671-694`; `engine/include/strata/kernels/cpu/numa_pool.hpp:94-149`; `engine/include/strata/kernels/cpu/pool_plan.hpp:328-330`
- worker/core 計画と slice dispatch: `engine/src/kernels/cpu/pool.cpp:823-903, 1328-1335`; `engine/include/strata/kernels/cpu/pool.hpp:408-419`
- native complement の配置と警告: `engine/src/core/expert_source.cpp:669-712, 748-756, 802-830, 4328-4372`
- 追加の card-node 判定と pool 起動: `engine/src/program/generate.cpp:4655-4675, 9001-9015`
