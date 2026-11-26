# `STRATA_TEST_SYSFS_ROOT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Linux 版 CPU expert pool が NUMA ノード数と各論理 CPU の NUMA ノードを調べるときの sysfs ルートを差し替える、テスト用フックです。未設定時は `/sys` を使い、設定すると `<値>/devices/system/node` と `<値>/devices/system/cpu/cpuN/nodeK` を参照します。これ自体が NUMA 分割を強制するものではなく、分割判断に使う NUMA 情報を変えます。コードコメントは「テストが架空の 2 ノード機を与えるため」「実機利用者は設定しない」と位置づけています（`engine/src/kernels/cpu/pool.cpp:637-643`）。

## 値と判定

`sysfs_root()` は `std::getenv` で取得し、ポインターが null でなく、先頭文字が NUL でもない場合に値全体を `std::string` として返します。それ以外は `/sys` です。空白除去、パス正規化、存在確認、文字列形式の検証はしません。相対パスや空白を含む非空文字列もそのまま接頭辞になります（`engine/src/kernels/cpu/pool.cpp:640-643`）。

| 条件 | 未設定 | 有効になる値（例） | 空文字・無効値の扱い |
|---|---|---|---|
| Linux で NUMA 情報を読むとき | `/sys` を参照 | `/tmp/fake-sysfs` なら `/tmp/fake-sysfs/devices/system/...` を参照 | `""` は `/sys` に戻る。`" "`、`0`、`false` なども非空なので文字どおりのパス接頭辞として使われる。値の妥当性検査はなく、対象を読めなければ NUMA ノード数は最終的に 1、CPU のノード番号は不明になり得る |
| Windows・Linux 以外 | NUMA 情報取得経路でこの変数を読まない | 該当なし | 該当なし |

ノード数の走査は `node` の後ろが数字だけのディレクトリを対象とし、その `cpulist` の先頭行に数字が一つでもあると CPU を持つノードとして数えます。ディレクトリを開けない場合や該当するノードがない場合、helper は 0 を返し、呼び出し側が最低 1 にします（`engine/include/strata/kernels/cpu/numa_pool.hpp:37-53`; `engine/src/kernels/cpu/pool.cpp:660-668`）。CPU の所属は `node0` から `node63` のパスを順に `access(..., F_OK)` で確認し、最初に見つかった番号を返します。どれもなければ `-1` です（`engine/src/kernels/cpu/pool.cpp:645-655`）。

## 有効になる条件

- NUMA sysfs override として使われるのは `__linux__` のビルドだけです。Windows は `GetNumaHighestNodeNumber` と Windows 専用の CPU node lookup を使い、その他の OS はノード数を 1 とします（`engine/src/kernels/cpu/pool.cpp:637-669`）。
- `ExpertPool` の構築時に NUMA ノード数を読み、分割の試行時には各 CPU のノード情報を参照します。自動分割は `STRATA_NUMA_SPLIT` が未指定または空で、`STRATA_NUMA_POOL` が off 値ではなく、指定 sysfs が 2 以上の CPU 保有ノードを示す場合に候補になります（`engine/src/kernels/cpu/pool.cpp:803-820`; `engine/include/strata/kernels/cpu/numa_pool.hpp:65-84`）。
- 自動分割には、少なくとも 2 スレッド、pool thread の pinning、全スレッドの CPU と NUMA node が判明すること、pool threads がちょうど 2 node にまたがり slice が均衡すること、および `STRATA_EXCHANGE_ROTATE` が文字列全体で `1` でないことも必要です。満たさない場合、自動分割は取り消されて従来の pool 配置に戻ります（`engine/include/strata/kernels/cpu/numa_pool.hpp:94-149`; `engine/src/kernels/cpu/pool.cpp:671-695,883-900`）。
- 明示的な `STRATA_NUMA_SPLIT=1` の実分割判断でも CPU node lookup に使われます。`STRATA_NUMA_SPLIT=test` は実ノード lookup を使わずテスト用 slice を構成します。`STRATA_NUMA_POOL` は複数ノード条件などで分割を無効にできます（`engine/src/kernels/cpu/pool.cpp:813-820,927-978`; `engine/include/strata/kernels/cpu/numa_pool.hpp:65-84`）。
- override は CPU の package/core 検出自体には適用されません。Linux の物理 CPU topology 検出は別に `/sys/devices/system/cpu/cpuN/topology/...` を直接読みます（`engine/src/kernels/cpu/pool.cpp:445-457`）。また `--pool-cores` が明示されていると自動分割用の worker core 並べ替えは行われません（同 `:823-839,844-864`）。

## 実行時の詳細

読み取り箇所は Linux 専用 `sysfs_root()` 一か所で、関数内 `static` cache はありません。ノード数判定、CPU node lookup、worker core の node 別並べ替えから呼ばれるたびに `getenv` を評価します。これらは通常 `ExpertPool` 構築中に行われ、構築後の split plan は固定されます。プロセス起動後に環境を変更しても、すでに構築済み pool の判断は更新されません。後続の pool 構築はその時点の環境値を読み直します（`engine/src/kernels/cpu/pool.cpp:640-655,660-668,803-820,844-864,883-989`）。

この変数を読む Strata の箇所に CLI 引数・設定ファイルからの上書きや子プロセスへの転送はありません。指定パスの sysfs 形式が不完全でも値を拒否する分岐はなく、読み取れたノード数・CPU node 情報に基づいて NUMA の候補判定が進みます。自動分割が不成立なら元の配置に戻ります。明示的な `STRATA_NUMA_SPLIT=1` で node 情報が不明などの場合は plan が成立せず、split off の経路になります（`engine/src/kernels/cpu/pool.cpp:883-900,927-978`）。

## ログと測定値

この変数そのものの値を表示するログはありません。自動分割の候補が成立せず理由がある場合、stderr に `strata cpu pool: NUMA pool off: <理由> (<ノード数> NUMA nodes found), the pool runs as before` が出ます。成立すれば `strata cpu pool: NUMA pool on: <ノード数> NUMA nodes found, one slice of the pool per node (STRATA_NUMA_POOL=0 turns it off)` が出ます。1 node で自動分割しない場合はこの経路のログはありません。明示的な split の経路では成功時に slice と node 番号、失敗時には `strata cpu pool: NUMA split off: <理由>` が出ます（`engine/src/kernels/cpu/pool.cpp:883-900,967-978`）。

## 根拠

- `engine/src/kernels/cpu/pool.cpp:637-669` — Linux 専用 root override、CPU-to-node lookup、OS 別 node count。
- `engine/include/strata/kernels/cpu/numa_pool.hpp:37-53,65-84,94-149` — sysfs node count の読み方、pool 選択、分割条件。
- `engine/src/kernels/cpu/pool.cpp:803-820,844-864,883-900,927-989` — pool 構築時の判断、core 並べ替え、分割・fallback・ログ。
- `engine/src/kernels/cpu/pool.cpp:445-457` — override の対象外である Linux の物理 CPU topology 読み取り。
