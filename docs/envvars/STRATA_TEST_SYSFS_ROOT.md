# `STRATA_TEST_SYSFS_ROOT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Linux の CPU expert pool が NUMA topology を読む sysfs のルートを差し替えるフックです。未設定または空文字なら `/sys`、空でない値ならその文字列をルートとして使います。ソースコメントは架空の NUMA topology を使うテスト用とし、「実機では設定しない」としています。環境変数の読み取り自体は `__linux__` の実装にあり、テスト専用ビルド macro による制限はありません。

## 値と判定

| 環境の状態 | 使われるルート |
|---|---|
| unset | `/sys` |
| 空文字 | `/sys` |
| 空でない文字列 | 値をそのまま使用 |

値の parse、trim、絶対パス検査、ディレクトリ検証はありません。たとえば ` /tmp/fake ` のような値も空白を含んだパスとして扱われます。末尾の `/` も除去されません。ルート配下のファイルが存在しない・読めない場合は探索結果に反映されます。

## 有効になる条件

- `src/kernels/cpu/pool.cpp` が Linux 向けにコンパイルされていること。Windows は `GetNumaHighestNodeNumber`、その他の OS は 1 ノードを返す別経路で、この変数を読みません。
- CPU expert pool の構築中に NUMA ノード数または CPU の NUMA node ID を調べること。
- 自動 NUMA pool は、検出した CPU 付き NUMA node が2つ以上で、`STRATA_NUMA_SPLIT` が未設定の場合に試されます。したがって、この変数で node 数や node 対応を差し替えると、自動分割の試行条件と分割可否が変わり得ます。

この変数自体は NUMA 分割を強制しません。分割には別途、CPU pool の pinning、worker と host thread の配置、対応する NUMA topology などの条件があります。`STRATA_NUMA_POOL` や `STRATA_NUMA_SPLIT` の選択、`STRATA_EXCHANGE_ROTATE=1`、2 node ちょうど・slice の均衡などにより、分割が無効になったり、従来の pool に戻ったりします。

## 実行時の詳細

Linux では `sysfs_root()` が `getenv("STRATA_TEST_SYSFS_ROOT")` を呼び、未設定または先頭文字が NUL のとき `/sys` を返します。読み取り値を static cache する実装ではありません。pool 構築時、まず `root + "/devices/system/node"` を走査してノード数を数えます。`node` に数字だけが続く名前のディレクトリを対象とし、その `cpulist` の最初の行に数字があれば CPU 付き node と数えます。ディレクトリが無い・走査できない・該当 node が無い場合は数が0となり、呼び出し元で最低1として扱われます。

NUMA split の候補を評価するときは、各 CPU について `root + "/devices/system/cpu/cpu<番号>/node<番号>"` を node 0 から63まで確認し、最初に存在した番号をその CPU の NUMA node とします。見つからなければ node 不明（-1）です。読み取りが失敗して自動分割を実行できない場合、pool は元の placement に戻り、stderr に `strata cpu pool: NUMA pool off: ... (N NUMA nodes found), the pool runs as before` を出します。分割を明示要求している経路では、理由に応じて `strata cpu pool: NUMA split off: ...` が出ます。

値は pool の構築中に参照され、NUMA plan は worker thread 起動前に確定します。構築後にプロセス環境を変更しても既存 pool の plan は更新されません。子プロセスへの転送や上書きはこの読み取り箇所にはありません。

## 文書との照合

`docs/DETAILS.md` は Linux で `/sys/devices/system/node/node*/cpulist` を数える NUMA pool の自動試行条件と、実行できない場合の fallback を説明しています。`STRATA_TEST_SYSFS_ROOT` によるルート差し替えはその説明には記載されていません。リリースノートにも変数固有の性能値はありません。この調査では当該フックの性能や実機での使用結果を確認していません。

## 根拠

- `src/kernels/cpu/pool.cpp:593-599` — Linux 限定の `sysfs_root()`、環境変数の読み取り、unset/empty 時の `/sys` fallback。
- `src/kernels/cpu/pool.cpp:601-610` — CPU ごとの `node0`〜`node63` 検索。
- `src/kernels/cpu/pool.cpp:614-624` — Linux/Windows/その他 OS の node 数取得経路。
- `src/kernels/cpu/pool.cpp:750-760,820-839,856-910` — pool 構築時の node 数・分割判定・fallback と stderr ログ。
- `include/strata/kernels/cpu/numa_pool.hpp:37-52,94-149` — node directory の数え方、および pinned thread、node 対応、2 node と均衡を要求する分割判定。
- `docs/DETAILS.md:2199-2203` — NUMA pool の既定動作と適用条件。
