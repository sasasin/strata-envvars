# `STRATA_COPY_ENGINE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の prompt / prefill 経路で、専門家 (expert) データをステージング領域へ移す際のコピー用キューを、Level Zero の copy-only command queue group 上に作るかを制御する。キューを作れた場合、prefill が `m.copy` に積む expert blob の `memcpy` と関連 barrier がそのキューを使う。通常の計算用キューや expert の選択をこの変数が切り替える処理はない（`engine/sycl/src/core/copy_queue.cpp:76-81, 90-136`、`engine/sycl/src/prefill/prefill.cpp:1467-1481, 3200-3228`）。

## 値と判定

数値や真偽値への変換はせず、C 文字列の先頭 1 文字を比較する。最初の `make_copy_engine_queue()` 呼び出しで `STRATA_COPY_ENGINE` の先頭が `0` なら、関数内 `static` の `off` が真になり、そのプロセスでは以降の呼び出しも直ちに `nullptr` を返す。空文字や未設定は `off` にならない（`engine/sycl/src/core/copy_queue.cpp:76-81`）。

| 条件 | unset | copy queue を要求する値 | copy queue を止める値 |
|---|---|---|---|
| Battlemage と判定される Level Zero GPU | off 判定は偽。後述の API / queue 条件を満たせば有効 | 特別な値は不要。`1` も有効 | 先頭が `0`。例: `0`, `0anything` |
| Battlemage 以外の Level Zero GPU | off 判定は偽だが、世代条件で無効 | 先頭が `1`。例: `1`, `1anything` | 先頭が `0`。例: `0`, `0anything` |
| Level Zero 以外、または `STRATA_HAVE_ZE_API` なし | 専用 queue は作られない | 値にかかわらず専用 queue は作られない | 値にかかわらず専用 queue は作られない |

先頭文字以外は判定に使わない。したがって `false`、`on`、`true`、空文字、空白始まりの値は「off」でも「強制 on」でもなく、世代の既定判定に従う。大文字小文字・前後の空白・文字列全体の妥当性検査はない。先頭が `0` なら `0anything` も停止し、先頭が `1` なら `1anything` も非 Battlemage で強制要求になる（`engine/sycl/src/core/copy_queue.cpp:77-78, 94-96`）。

## 有効になる条件

- `engine/sycl` の SYCL 実装で `Prefill::init()` が呼ばれる必要がある。同ファイルの CMake target に `src/core/copy_queue.cpp` が含まれる（`engine/sycl/CMakeLists.txt:290-305`）。
- `STRATA_HAVE_ZE_API` が定義される必要がある。これは `<level_zero/ze_api.h>` が利用可能な場合にだけ定義される。定義されない build では専用 queue を使わず `nullptr` を返す（`engine/sycl/src/core/copy_queue.cpp:8-13, 79-82`）。
- 対象 device の SYCL backend が Level Zero であること。さらに `STRATA_COPY_ENGINE` が先頭 `1` でない場合は `strata::intel_gpu_gen(dev)` が Battlemage であること。Xe3 を Battlemage と判定する通常判定や `STRATA_INTEL_GEN` の override がこの条件に影響する。`STRATA_INTEL_GEN` は `battlemage` / `alchemist` / `unknown` の完全一致で判定され、関数内 static に一度保存される（`engine/sycl/src/core/copy_queue.cpp:90-96`、`engine/sycl/include/strata/sycl_queue.hpp:139-156, 169-171`）。
- `SYCL_UR_USE_LEVEL_ZERO_V2` が未設定、空、または先頭が `0` 以外であること。Strata は先頭 `0` の場合に明示的な copy queue の作成を見送る（`engine/sycl/src/core/copy_queue.cpp:98-103`）。
- Level Zero loader と必要な関数シンボルを取得でき、device が compute 専用ではない copy-only queue group を持ち、immediate command list と SYCL queue の作成が成功すること（`engine/sycl/src/core/copy_queue.cpp:42-56, 102-130`）。
- キューの作成だけでなく、prefill が非 resident expert の blob を staging する経路に入る必要がある。resident expert は `stage_one` で転送前に戻る（`engine/sycl/src/prefill/prefill.cpp:4660-4685`）。CLI の prompt 経路では `generate.cpp` から prefill の `init()` が呼ばれる。別の CLI 引数がこの環境変数の判定値を上書きする処理は確認できない（`engine/sycl/src/program/generate.cpp:7484-7504, 13352-13359`）。

## 実行時の詳細

`make_copy_engine_queue()` の最初の呼び出し時に `off` を一度評価するため、その後プロセス内で環境を書き換えても、最初に先頭 `0` だった場合は有効化できない。一方、先頭 `0` でない場合、強制指定の再確認は未登録 device ごとに行われる。device は条件判定の前に `dev_queues` へ登録され、成功した queue も `nullptr` も device 単位で再利用されるため、その device で最初に試した後の環境変更では再判定されない（`engine/sycl/src/core/copy_queue.cpp:76-97`）。

専用 queue が返れば `Prefill::init()` は `m.copy` に採用し、expert blob の転送と順序 barrier に使う。返り値が `nullptr` の場合、`STRATA_SYCL_PREFILL_COPY_PROFILING` が文字列全体で `0` と等しければ profiling 無効の in-order queue を作り、それ以外は `create_queue(true)` に fallback する。通常 queue の作成にも失敗した場合は `err = "prefill: copy stream"` として init を失敗させる（`engine/sycl/src/prefill/prefill.cpp:1470-1481`、`engine/sycl/include/strata/prefill_copy_queue.hpp:7-12`）。

専用 queue を作る途中の loader / symbol / queue group / Level Zero API の失敗は、ほとんどが理由ログなしで `nullptr` を返して prefill 側の fallback に進む。例外を捕捉した場合は下記の stderr を出して `nullptr` を返す。別 GPU・別 build・未対応 queue group の fallback 理由を個別に表示するログはない（`engine/sycl/src/core/copy_queue.cpp:79-82, 90-116, 125-140`）。

## ログと測定値

専用 queue がプロセス内で初めて作成されたときだけ stderr に次の形式を一度出す。`what` は呼び出し側が渡した `the prompt path's expert`、`ord` は選んだ queue group の ordinal である（`engine/sycl/src/core/copy_queue.cpp:133-136`）。

```text
strata: copy engine: %s copies run on the GPU's copy engine (queue group %d), not the compute engine (STRATA_COPY_ENGINE=0 turns it off)
```

queue 作成中に C++ 例外を捕捉すると、stderr に次を出す（`engine/sycl/src/core/copy_queue.cpp:138-140`）。

```text
strata: copy engine queue not available (%s): ordinary queue
```

`docs/INTEL.md:222-224, 451` は Battlemage での既定、`=1` の強制、`=0` の停止を説明している。コードはさらに先頭文字判定、Level Zero / API / queue 条件と fallback を定めている。対象変数を on/off 比較した条件付き測定値は確認できなかったため、性能値は記載しない。

## 根拠

- 値の判定、device ごとの queue 作成・cache・ログ: `engine/sycl/src/core/copy_queue.cpp:76-140`
- Level Zero API の有無と loader: `engine/sycl/src/core/copy_queue.cpp:8-13, 37-56`
- 世代判定と `STRATA_INTEL_GEN`: `engine/sycl/include/strata/sycl_queue.hpp:139-156, 169-171`
- SYCL build での組み込み: `engine/sycl/CMakeLists.txt:290-305`
- prefill での採用・fallback: `engine/sycl/src/prefill/prefill.cpp:1467-1481`
- staging 転送での利用と resident expert の早期 return: `engine/sycl/src/prefill/prefill.cpp:4660-4685`
- 通常 prefill / split prefill からの呼び出し: `engine/sycl/src/program/generate.cpp:7484-7504, 13352-13359`
