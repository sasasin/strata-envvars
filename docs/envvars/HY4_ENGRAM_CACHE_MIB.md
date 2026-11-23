# `HY4_ENGRAM_CACHE_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Engram shard のホスト側 LRU 行キャッシュ容量を MiB 単位で指定する。`strata-hy4` の Runner 初期化時に MiB をおよそ 116 bytes/row で行数へ切り捨て変換し、その行数を `EngramIO::open` に渡す。0 は LRU キャッシュなしになるが、モデル Section 2 の seed が使える場合はその検索は残る。Engram の計算内容や GPU キャッシュ容量を直接指定する変数ではない（`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676`、`engine/src/hy4flash/run/hy4_engram.h:18-21,89-96`、`engine/src/hy4flash/run/hy4_engram.cpp:492-504,576-595,657-665`）。

同じ値は expert の host RAM 予算推定にも使われる。RAM 予算を自動計算するとき、Engram 用としてこの値を GiB 換算して差し引き、ホスト常駐 experts がその予算を超えると CPU + SSD cold-expert 経路へ切り替える条件に影響する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:802-834,842-848`）。

## 値と判定

環境変数を読む2箇所はいずれも `getenv` で設定有無を判定し、設定値を `atof` で変換する。文字列全体の数値妥当性は検査しない。数値として読める先頭部分が使われ、後続文字は無視される。空文字や数値で始まらない文字列は `atof` により 0 となる。環境変数を直接設定した負値も `std::max(0.0, ...)` で 0 に丸められる（`engine/src/hy4flash/run/hy4_graph.hip.h:1663-1666`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-815`）。

| 条件 | unset | 設定値の扱い | 例 |
|---|---|---|---|
| HIP/CUDA の `strata-hy4` で Engram shard を開く | `ram_limit_gb()` に応じた自動値。RAM ≤20 GiB: 128 MiB、≤40 GiB: 256 MiB、≤72 GiB: 512 MiB、それより大きい場合: `ENGRAM_DEFAULT_LRU_ROWS` の 6,000,000 行（概算 836 MiB） | `atof` の結果を 0 以上に丸め、`(size_t)(MiB × 1,048,576 / 116)` 行へ切り捨てる | `64` → 約64 MiB分、`0` / 空文字 / `abc` → 0行、`-1` → 0行、`64junk` → 約64 MiB分 |
| tiered expert の RAM 予算を自動計算 | `ram_limit_gb()` に応じて 128 / 256 / 512 / 850 MiB を Engram 使用量として見積もる（境界は上と同じ） | `atof` の結果を 0 以上に丸め、1024 で割って GiB 換算する | `64junk` → 64 MiB相当、空文字 / `abc` / 負値 → 0 MiB相当 |

CLI の `--engram-cache-mib VALUE` は別途 `atof(VALUE) >= 0.0` を満たす場合に限って、この環境変数へ値を設定する。したがって負値は既存の環境値を上書きせず、空文字や `abc` は 0 として設定される。数値の後ろに文字があっても先頭の数値で判定される。複数回指定した場合は最後に有効だった指定が残る（`engine/src/hy4flash/run/hy4_main.hip.cpp:467-470`）。

## 有効になる条件

- CMake の `STRATA_BUILD_HY4` が有効で、CUDA または HIP backend として構成した `strata-hy4` が対象。CMake は CUDA/HIP のどちらかを必須とし、別スクリプトの Metal / SYCL runner は別実装である（`engine/CMakeLists.txt:846-851,884-908`）。
- LRU 容量への適用には、Runner 初期化へ空でない Engram shard パスが渡される必要がある。`--no-engram` が指定されると空パスを渡すため、この変数による LRU 初期化・設定ログは発生しない（`engine/src/hy4flash/run/hy4_main.hip.cpp:563-564,703-705`、`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676`）。サーバーモードでも `--no-engram` がなければ同様に Engram パスを渡す（`engine/src/hy4flash/run/hy4_serve.hip.h:314-317`）。
- expert RAM 予算への反映は、experts を tiered load する経路で、かつ `HY4_RAM_BUDGET_GB` と `STRATA_HY4_RAM_GB` のどちらも未設定で自動 RAM 予算を計算するときに限る。いずれかが設定されているとその値を優先して予算を作るため、この変数はその計算では参照されない。さらに `--ram-experts-gb` は `STRATA_HY4_RAM_GB` を設定し、RAM cap としても作用する。`--ssd-experts` は `HY4_RAM_BUDGET_GB=0` を設定する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-832`、`engine/src/hy4flash/run/hy4_main.hip.cpp:455-465`）。この上書きは expert RAM 予算の計算に限られ、Engram LRU 容量設定は独立して環境値を読む。
- `--engram-cache-mib` を受け付けても、SYCL runner は値を読み捨てるだけで環境変数を設定せず、Metal runner は「not used by the Metal runner」と stderr に出す。これらの runner にこの変数の Strata 側読み取りはない（`engine/src/hy4flash/sycl/sy_main.cpp:140-143`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1601-1608`）。

## 実行時の詳細

`strata-hy4` は引数解析中に `--engram-cache-mib` の値をプロセス環境へ設定し、その後、モデル load と Runner 初期化に進む。Windows では `hy4_setenv` が `_putenv_s`、それ以外では `setenv(..., 1)` を使うため、CLI の有効値は既存の同名環境値を上書きする。環境値をプロセス起動後に外部から変更した場合の再読込経路はなく、expert 予算は model load 時、LRU 行数は Runner 初期化時に読み取られる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-411,1267-1275,810-815`、`engine/src/hy4flash/run/hy4_main.hip.cpp:467-470,649-659,692-705`）。

LRU 容量は shard を開くときに確定する。0 行では `EngramIO::open` が LRU 配列を確保せず、fetch 時も LRU lookup / insert を飛ばして seed と shard 読み取りを使う。正の行数では指定行数分の100-byte row領域と索引領域を確保する。値による容量制限はこのホスト LRU に適用される（`engine/src/hy4flash/run/hy4_engram.cpp:446-504,576-595,657-665`）。

## ログと測定値

Engram shard を開くとき、環境変数が設定されていれば stderr に `[engram] cache budget %.0f MiB -> %zu LRU rows`、未設定なら RAM に応じて `[engram] auto cache %.0f MiB (RAM %.0f GiB) -> %zu LRU rows` を出す（`engine/src/hy4flash/run/hy4_graph.hip.h:1663-1675`）。値が 0 でも設定時ログは出る。

Engram 初期化失敗は通常 CLI で `init: <error>` と stderr に出て終了コード 1、serve では `ERR init: <error>` の protocol 応答で終了コード 1 になる（`engine/src/hy4flash/run/hy4_main.hip.cpp:703-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:314-317`）。Strata の資料に、この変数を用いた性能測定値は見つからなかった。

## 根拠

- 全参照と値設定: `engine/src/hy4flash/run/hy4_main.hip.cpp:467-470`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-411`
- Engram cache の値判定、既定値、初期化・ログ: `engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676`、`engine/src/hy4flash/run/hy4_engram.h:18-21,89-96`、`engine/src/hy4flash/run/hy4_engram.cpp:446-504`
- Cache lookup と 0 行時の経路: `engine/src/hy4flash/run/hy4_engram.cpp:576-595,657-665`
- RAM 予算、優先環境変数、tiered fallback: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:802-848,1490-1502`
- build/backend と他 runner の CLI 扱い: `engine/CMakeLists.txt:846-851,884-908`、`engine/src/hy4flash/sycl/sy_main.cpp:140-143`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1601-1608`
