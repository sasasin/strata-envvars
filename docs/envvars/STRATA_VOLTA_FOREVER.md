# `STRATA_VOLTA_FOREVER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`STRATA_VOLTA_FOREVER` は、CUDA 13 対応 shim「volta-forever」が有効かどうかを Strata 側で判定するための明示 override です。判定結果が有効なら、対象の CUDA 起動経路で `CUDA_MODULE_LOADING` の既定値を `LAZY` にし、CUDA Graph 内で 1024-thread block を避ける分岐を選びます。shim 自体をロードしたり、GPU の能力を変えたりする変数ではありません。判定 helper は `engine/include/strata/core/volta_forever.hpp` にあります（同ファイル:40-66, 74-103）。

## 値と判定

`volta_forever_active()` は呼び出しごとに `std::getenv` で `STRATA_VOLTA_FOREVER`、`LD_PRELOAD`、`VOLTA_FOREVER` を読み、POSIX では shim の version symbol も調べます。値は数値や真偽値として parse せず、override は文字列の先頭または全体を比較します（`engine/include/strata/core/volta_forever.hpp:25-66`）。

| 条件 | `STRATA_VOLTA_FOREVER` | 結果 |
|---|---|---|
| 未設定、または空文字 | override を使わず次の検出方法へ進む | shim の version symbol が非空、`LD_PRELOAD` に `libvolta_forever` が含まれる、または `VOLTA_FOREVER` が後述の有効値なら有効。それ以外は無効 |
| 非空で先頭文字が `0` | `0`, `00`, `0anything` など | 無効を即時返却し、他の検出情報も調べない |
| 非空で先頭文字が `0` 以外 | `1`, `true`, `false`, `anything` など | 有効を即時返却。文字列全体の妥当性や大文字小文字は検査しない |

override が空または未設定のとき、`VOLTA_FOREVER` は空でなく、文字列全体が厳密に `0` でなければ有効扱いです（例: `00`、`false` も有効）。この legacy 名が `0` でも、それだけでは後続の symbol / `LD_PRELOAD` 判定を無効にしません。`STRATA_VOLTA_FOREVER=0` だけが他の判定より優先して無効を返します（同ファイル:42-58）。

## 有効になる条件

- `STRATA_VOLTA_FOREVER` の override 判定自体に OS、GPU、backend、build macro の追加条件はありません。ただし効果が現れるのは、この helper を組み込んで呼び出す実行経路です。
- `CUDA_MODULE_LOADING` の既定設定は `strata` generate、HY4 CUDA、Inkling CUDA 系、`strata-q36` の各起動コードから呼ばれます。HIP-only の HY4 / Inkling 経路では起動時の呼び出しがコンパイル条件で除かれます（`engine/src/program/generate.cpp:3765-3771`; `engine/src/hy4flash/run/hy4_main.hip.cpp:342-346`; `engine/src/inkling2/ink_main.cpp:366-370`; `engine/src/inkling2/cuda/ink_cuda_main.cu:38-41`; `engine/src/qwen35/q36_engine.cu:5421-5423`）。
- `CUDA_MODULE_LOADING` がすでに環境に設定されている場合、空文字を含めて Strata は上書きしません。したがって override が有効でも、利用者が同変数を設定済みなら Strata は `LAZY` を設定せず、その理由ログも出しません。未設定で shim 判定が無効なら同じ helper が既定の `EAGER` を設定します（`engine/include/strata/core/volta_forever.hpp:74-94`）。
- 1024-thread CUDA Graph 制限の判定は、compute capability が `7.0` で shim 判定も有効な場合に限り 512 を安全上限として扱います。他の capability または無効判定では上限は 1024 です（同ファイル:96-103）。HY4 CUDA と Inkling CUDA でこの条件を使います。Inkling はさらに `model_.ep2_active` と `model_.ls_active` のどちらも false のときだけ `use_cuda_graph` を true にします（`engine/src/hy4flash/run/hy4_graph.hip.h:1717-1733`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:233-240`）。
- `strata-q36` は Graph instantiate が失敗したとき、shim 判定が有効なら Graph を無効化して stream launch に切り替えます。無効判定の場合は通常の `CK(ei)` エラー経路です（`engine/src/qwen35/q36_engine.cu:3612-3634`）。

## 実行時の詳細

判定関数内に `static` cache はなく、環境値と POSIX symbol probe は `volta_forever_active()` を呼ぶたびに評価されます。起動時の `apply_default_cuda_module_loading()` はその時点の判定を取り、`CUDA_MODULE_LOADING` が未設定なら有効時に `LAZY`、無効時に `EAGER` を設定します。Windows では `_putenv_s`、それ以外では `setenv(..., 0)` を使います。関数は shim 判定が有効で設定を行った場合に `true` を返します（`engine/include/strata/core/volta_forever.hpp:25-37, 61-94`）。

このため、起動時に設定された `CUDA_MODULE_LOADING=LAZY` は環境内に残ります。後続の呼び出しで `STRATA_VOLTA_FOREVER` を変更しても、すでに設定された `CUDA_MODULE_LOADING` はこの関数では置き換わりません。一方、Graph 判定など後から `volta_forever_active()` を呼ぶ経路は、その呼び出し時点の環境を読み直します。子プロセスへの環境転送はこの helper にはありません。

override の有効判定だけで shim をロードしたり、compute capability の報告値を一律に remap することはありません。`generate.cpp` にある 7.5 から 7.0 への表示用 remap は別の `strata::volta_forever_active()` 判定と version 関数を使い、この `STRATA_VOLTA_FOREVER` helper の結果を直接参照していません（`engine/src/program/generate.cpp:8495-8500`; `engine/include/strata/core/emulate.hpp:18-56, 68-80`）。

## ログと測定値

起動時に shim 判定が有効で、かつ `CUDA_MODULE_LOADING` が未設定の場合にのみ、呼び出し元が次の stderr ログを出します。ログに version symbol があればその文字列、なければ `env` を表示します。

- `strata: volta-forever detected (%s): setting CUDA_MODULE_LOADING=LAZY` (`engine/src/program/generate.cpp:3768-3770`)
- `[gpu] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY` (`engine/src/hy4flash/run/hy4_main.hip.cpp:343-345`)
- `[inkling] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY` (`engine/src/inkling2/ink_main.cpp:367-369`)
- `[inkling-cuda] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY` (`engine/src/inkling2/cuda/ink_cuda_main.cu:39-41`)
- `strata-q36: volta-forever detected: setting CUDA_MODULE_LOADING=LAZY` (`engine/src/qwen35/q36_engine.cu:5421-5423`)

HY4 CUDA / Inkling CUDA で `sm_70` かつ有効判定の場合は 1024-thread Graph の既定無効化ログを出します。HY4 の `HY4_GPU_GRAPH`、`HY4_CUDA_GRAPH`、`HY4_HIP_GRAPH` のうち最初に設定された値が Graph 選択に使われ、非ゼロなら既定の無効化を上書きできます。分散 HY4 で remote experts を使い、`HY4_CUDA_GRAPH` と `HY4_GPU_GRAPH` の両方が未設定なら、さらに Graph を無効にします（`engine/src/hy4flash/run/hy4_graph.hip.h:1714-1736`）。`strata-q36` は `--no-graph` で Graph を使わない設定にできます（`engine/src/qwen35/q36_engine.cu:5371, 5474`）。これらの Graph 選択は helper の 512-thread 安全上限自体を変更しません（`engine/src/hy4flash/run/hy4_graph.hip.h:1717-1733`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:234-239`）。`strata-q36` の instantiate 失敗時は CUDA エラー名と `running stream launches` を stderr に出します（`engine/src/qwen35/q36_engine.cu:3619-3632`）。この調査では性能値を記載していません。

## 根拠

- 判定、override の優先順位、環境変数の読み取り、module-loading fallback: `engine/include/strata/core/volta_forever.hpp:25-94`
- Graph block 上限: `engine/include/strata/core/volta_forever.hpp:96-103`
- generate の起動処理とログ: `engine/src/program/generate.cpp:3765-3771`
- HY4 CUDA の起動処理と graph 条件: `engine/src/hy4flash/run/hy4_main.hip.cpp:342-346`, `engine/src/hy4flash/run/hy4_graph.hip.h:1714-1733`
- Inkling CUDA の起動処理と graph 条件: `engine/src/inkling2/ink_main.cpp:366-370`, `engine/src/inkling2/cuda/ink_cuda_main.cu:38-41`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:233-240`
- q36 の起動処理と Graph 失敗時 fallback: `engine/src/qwen35/q36_engine.cu:3612-3634, 5421-5423`
- 別 helper による compute capability 表示 remap: `engine/src/program/generate.cpp:8495-8500`, `engine/include/strata/core/emulate.hpp:18-56, 68-80`
