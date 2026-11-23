# `INK2_CPU_NODES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA EP backend の hybrid doorbell CPU expert pool が扱う NUMA ノード数に上限を設ける。Linux x86 では `/sys/devices/system/node/nodeN/cpulist` を node 0 から連続して読み、最初に空の内容となった番号で検出を止める。その検出数とこの変数の正の整数変換値の小さい方を採り、さらに実装上限 2 に制限する。結果は host expert のノード割り当てと、そのノードごとの doorbell pool 作成に使われる。CPU worker 数そのものや、GPU に置く expert 数をこの変数が指定するわけではない（`engine/src/inkling2/hybrid_doorbell.cu:534-543`、`engine/src/inkling2/ep_dual_gpu.cu:970-972,1011-1019,1037-1058`、`engine/src/inkling2/hybrid_doorbell.h:31,63-73`）。

## 値と判定

Linux x86 の場合、`std::getenv` で設定有無を調べ、設定されていれば `std::atoi` を適用する。値全体の数値妥当性は検査しない。`atoi` が読む先頭の整数部分が使われ、空白と符号を含む先頭部分は変換され、変換後は最低 1 に丸められる。従って、未設定は検出数のまま、空文字・非数値先頭・0・負数は 1 ノード、`2` や `2tail` は最大 2 ノードとなる。大文字小文字の比較はない。検出数や最終値は最大 2 なので、`2` より大きい値で 2 ノードを超えることはない。たとえば `3` と `2` は同じ結果になり、検出ノード数が 1 なら設定値にかかわらず 1 となる。`atoi` の範囲外入力について、コードに明示的な検査や規定された fallback はない（`engine/src/inkling2/hybrid_doorbell.cu:534-543`、`engine/src/inkling2/hybrid_doorbell.h:31`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・結果 |
|---|---|---|---|
| Linux x86、`STRATA_NUMA_POOL` が厳密に `"0"` でない | sysfs 検出数を 1..2 に制限 | 先頭が正の整数となる値。例: `1`, `2`, `2tail`; 結果は検出数以下かつ最大 2 | 空文字、`0`, `-1`, `true`, `0anything`, 数字で始まらない値は 1 ノード。検出数が 1 なら正数でも結果は 1 |
| その他の OS / CPU アーキテクチャ | 1 | 該当なし | この build 分岐では環境変数を読まず常に 1 |
| Linux x86、`STRATA_NUMA_POOL=0` | 1 | 該当なし | `INK2_CPU_NODES` の読み取り自体を短絡するため常に 1 |

## 有効になる条件

- `engine/src/inkling2/CMakeLists.txt:153-181,193-195` の任意 CUDA EP backend が build に含まれ、`hybrid_doorbell.cu` がコンパイルされている必要がある。ソースでの NUMA sysfs 実装は `__linux__` かつ `__x86_64__` / `__i386__` のときだけ有効で、それ以外は `numa_node_count()` が 1 を返す（`engine/src/inkling2/hybrid_doorbell.cu:27-35,534-543`）。
- 実行時には `EpDualGpuCudaBackend::init` が選ばれ、GPU が 1 台で、VRAM に載らない host experts があり、`opts.cpu_threads > 0` であることが必要。これを満たさない場合 `doorbell_active_` は false で、host expert のノード数は 1 に固定される（`engine/src/inkling2/ep_dual_gpu.cu:719-735,970-973`）。CPU thread 数は CLI の `--cpu-threads` から設定され、既定値は 0（`engine/src/inkling2/ink_main.cpp:441-442`、`engine/src/inkling2/ink_backend.h:26-28`）。
- `STRATA_NUMA_POOL` が値 `"0"` と完全一致すると、`numa_node_count()` は sysfs の走査と `INK2_CPU_NODES` の取得より先に 1 を返す。空文字や `"00"` はこの完全一致条件にはならない（`engine/src/inkling2/hybrid_doorbell.cu:63-66,534-540`）。
- 検出数は 0 から始まる連続 node 番号の sysfs 内容を数える。node 0 の読み取りが空などで検出数が 0 になっても、最後に最低 1 に丸める。環境変数は検出数を増やせず、実装上限も `kMaxNumaNodes == 2`（`engine/src/inkling2/hybrid_doorbell.cu:56-61,537-540`、`engine/src/inkling2/hybrid_doorbell.h:31`）。

## 実行時の詳細

`numa_node_count()` の呼び出しごとに環境を読み、static cache はない。backend 初期化では doorbell が有効な場合に一度呼ばれ、その数を `n_numa` として host expert descriptor の `key % n_numa` に記録する。さらに `start_doorbell_pool()` 内でも同関数が呼ばれ、各 node の bell が設定されている場合だけ pool を作る（`engine/src/inkling2/ep_dual_gpu.cu:970-973,1011-1019,1037-1058`、`engine/src/inkling2/hybrid_doorbell.cu:604-640`）。

通常の初期化中は環境値を変えずに両方の呼び出しを行う想定のコードだが、呼び出し間でプロセス環境が変更された場合の整合性処理はない。通常の利用では初期化時に読まれる設定であり、expert descriptor と worker pool 作成後に値を変えても、それらの割り当てを再計算する処理はこの箇所にはない。

設定値が使われると、host expert の `numa_node` は expert key の剰余で選ばれ、pool は node ごとに worker を起動する。worker 数は別途 `opts.cpu_threads` と各 node の physical core 数から決まるため、この環境変数は thread 数の指定ではない（`engine/src/inkling2/ep_dual_gpu.cu:1011-1019`、`engine/src/inkling2/hybrid_doorbell.cu:612-640`）。

## ログと測定値

この変数専用の警告・エラーはない。backend 初期化時の stderr ログ `[inkling2-ep] Loaded ... (doorbell=%s, numa=%d, thr=%d) ...` に、最終的に使う `n_numa` が `numa=` として表示される。`device_info()` が返す backend 情報も doorbell 有効時に `Graph-Doorbell NUMA=<n>` を含む（`engine/src/inkling2/ep_dual_gpu.cu:699-703,1064-1068`）。

`docs/DETAILS.md` にこの環境変数固有の説明や測定値は見つからず、測定値は記載しない。

## 根拠

- `engine/src/inkling2/hybrid_doorbell.cu:27-35,534-543` — Linux x86 build 条件、`STRATA_NUMA_POOL` の短絡、sysfs 検出、`INK2_CPU_NODES` の `atoi` と clamp。
- `engine/src/inkling2/hybrid_doorbell.cu:604-640` — node 数に応じた CPU pool 構築。
- `engine/src/inkling2/ep_dual_gpu.cu:719-735,970-973,1011-1019,1037-1068` — CUDA EP 初期化条件、host expert の node 割り当て、pool 起動、観測ログ。
- `engine/src/inkling2/hybrid_doorbell.h:31,63-83` — 最大 NUMA node 数と pool 設定。
- `engine/src/inkling2/ink_backend.h:17-28`、`engine/src/inkling2/ink_main.cpp:441-442` — CPU thread 設定と CLI 引数。
- `engine/src/inkling2/CMakeLists.txt:152-181,193-195` — CUDA EP target への実装組み込みと compile definition。
