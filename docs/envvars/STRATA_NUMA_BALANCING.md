# `STRATA_NUMA_BALANCING`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux の対象ビルドでは、カーネルの `/proc/sys/kernel/numa_balancing` が正の値で、呼び出しスレッドのメモリポリシーが `MPOL_DEFAULT` の場合に、Strata は `set_mempolicy` でそのスレッドのポリシーを `MPOL_LOCAL` にする。環境変数を厳密に `keep` にすると、この変更を抑止して既定ポリシーを保つ。変数は NUMA balancing のカーネル設定自体を書き換えない。実装は `strata::platform::numa_balancing::keep_scanner_off()`。`engine/include/strata/platform/numa_balancing.hpp:35-42,71-95`

Strata のソースコメントは、この処理の目的を AMD HIP の GPU 読み取り対象ホストメモリに対するカーネルスキャンとキュー停止の回避と説明している。ここで Strata が実行する処理として確認できるのは、条件判定、現在ポリシーの照会、`MPOL_LOCAL` の設定、stderr への結果出力である。ドライバー内部の動作はこの文書では Strata の挙動として扱わない。`engine/include/strata/platform/numa_balancing.hpp:1-18,71-95`

## 値と判定

`std::getenv` の戻り値を `std::strcmp(e, "keep") == 0` で比較する。文字列全体が大文字小文字も含め完全一致したときだけ抑止する。数値や真偽値への変換はない。`engine/include/strata/platform/numa_balancing.hpp:73-80`

| 条件 | unset | 変更を抑止する値 | 抑止しない値の例 |
|---|---|---|---|
| Linux かつ `SYS_set_mempolicy` / `SYS_get_mempolicy` が定義されたビルド | `keep` ではないものとして判定 | `keep` のみ | 空文字、`KEEP`、`Keep`、`1`、`0`、`true`、`false`、`keep ` |
| 上記以外のビルド | 関数本体の環境変数読み取りがコンパイルされず、何もしない | 該当なし | 該当なし |

「抑止しない値」は、それだけでポリシー変更を保証しない。カーネル設定は `fscanf` の `%ld` で読み、正の値で、現在ポリシーが `MPOL_DEFAULT` の場合にだけ設定を試みる。この変換は整数の先頭部分を読むため、たとえばファイル内容 `1x` でも `1` の変換が成功する。ファイルが開けない・数値の先頭部分を読めない場合は `-1`、`get_mempolicy` が失敗した場合はモード `-1` として扱われ、変更しない。`engine/include/strata/platform/numa_balancing.hpp:38-42,62-68,73-80`

## 有効になる条件

- Linux で、`SYS_set_mempolicy` と `SYS_get_mempolicy` が定義されたビルドであること。条件外では関数は空文字を返し、環境変数を読み取らない。`engine/include/strata/platform/numa_balancing.hpp:27-31,73-95`
- `/proc/sys/kernel/numa_balancing` から正の整数が読めること。0、負数、読み取り失敗、数値を読めない場合は設定しない。`engine/include/strata/platform/numa_balancing.hpp:62-68,80`
- `get_mempolicy` で取得した現在のモードが `MPOL_DEFAULT` であること。既に別のポリシーが設定されている場合、Strata は上書きしない。`engine/include/strata/platform/numa_balancing.hpp:35-42,78-80`
- `STRATA_NUMA_BALANCING=keep` では上記条件にかかわらず設定を試みない。CLI 引数や別の環境変数による上書き処理は、この実装にはない。`engine/include/strata/platform/numa_balancing.hpp:73-80`
- `set_mempolicy` が成功すること。失敗時はメモリポリシーを変更できず、失敗理由を含む行を呼び出し元が stderr に出す。`engine/include/strata/platform/numa_balancing.hpp:80-86`

## 実行時の詳細

ヘルパーは呼び出されるたびに環境変数、カーネル設定ファイル、現在のポリシーを読み直す。関数内の static cache はなく、値をプロセス起動時に保存する実装でもない。環境変数やカーネル設定の変更は、その後の呼び出しに反映され得る。`engine/include/strata/platform/numa_balancing.hpp:62-80`

確認できた呼び出し箇所は次のとおり。

- `engine/src/program/generate.cpp:3662-3677`: Linux HIP ビルドで `main` の早い段階に呼び出し、空でない結果を stderr に出す。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:334-341`: Linux かつ `!HY4_CUDA` の `main` で呼び出し、空でない結果を stderr に出す。
- `engine/src/inkling2/ink_main.cpp:360-365`: Linux かつ `INKLING_ENABLE_HIP` の `main` で呼び出し、空でない結果を stderr に出す。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-560`: Linux の HIP backend `init` でも呼び出す。初期化のたびに再判定し、空でない結果を stderr に出す。

`set_mempolicy` は呼び出したスレッドのポリシーを設定する。ヘッダーのコメントと各エントリポイントの配置は、スレッド生成・メモリ確保より前に実行する意図を示している。ただし Inkling HIP backend の `init` 呼び出しは後段にもあるため、その時点で既に複数スレッドが存在すれば、変更が及ぶのは呼び出しスレッドだけである。ヘルパーは `/proc/self/task` のスレッド数を数え、2 以上なら追加の警告行を返す。`engine/include/strata/platform/numa_balancing.hpp:44-59,71-91`; 呼び出し順: `engine/src/program/generate.cpp:3665-3678`, `engine/src/hy4flash/run/hy4_main.hip.cpp:334-341`, `engine/src/inkling2/ink_main.cpp:360-365`, `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-560`

## ログと測定値

設定に成功すると、stderr に次の行を出す。`STRATA_NUMA_BALANCING=keep`、カーネル設定値が正でない場合、現在ポリシーが `MPOL_DEFAULT` でない場合、または前提情報を読めない場合は、このヘルパーから出力する行はない。

```text
strata: numa: kernel.numa_balancing is on: this process uses MPOL_LOCAL (the same placement, but the kernel no longer scans the memory the GPU reads, which stalled the GPU queues; STRATA_NUMA_BALANCING=keep: off)
```

設定 syscall が失敗した場合は `strerror(errno)` を含む `strata: numa: kernel.numa_balancing is on and MPOL_LOCAL could not be set (...): GPU queues can stall while the kernel scans host memory` を返し、呼び出し元が stderr に出す。設定後の `/proc/self/task` に2スレッド以上ある場合は、既定ポリシーのまま残るスレッド数と、カーネルがそれらをスキャンし得る旨の `strata: numa: WARNING: ...` 行も出す。`engine/include/strata/platform/numa_balancing.hpp:80-91`; 出力先: `engine/src/program/generate.cpp:3675-3676`, `engine/src/hy4flash/run/hy4_main.hip.cpp:338-340`, `engine/src/inkling2/ink_main.cpp:362-364`, `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:557-559`

ヘッダーコメントには、Radeon PRO W7900D (gfx1100)、2ソケットホスト、Qwen3.8-Flash-Next IQ3_S、各条件20回の新規1Kプロンプトで、既定ポリシー時に7回の watchdog 停止とエンジン起動ごと77–236秒のキュー退避、変更後に停止0回・退避1秒未満・decode不変だったという記載がある。これはソースコメントに記録された測定報告であり、この調査で再測定・独立検証した値ではない。`engine/include/strata/platform/numa_balancing.hpp:8-11`

`docs/DETAILS.md` には NUMA pool/split の説明があるが、この環境変数や `keep_scanner_off()` の記述は見当たらない。NUMA pool/split は別機能であり、上記の動作根拠には用いていない。

## 根拠

- 環境変数判定、条件、システム設定の読み取り、ポリシー照会と設定、ログ: `engine/include/strata/platform/numa_balancing.hpp:35-95`
- エントリポイントとビルド条件: `engine/src/program/generate.cpp:3662-3677`; `engine/src/hy4flash/run/hy4_main.hip.cpp:334-341`; `engine/src/inkling2/ink_main.cpp:360-365`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-560`
- 測定報告の記載: `engine/include/strata/platform/numa_balancing.hpp:8-11`
