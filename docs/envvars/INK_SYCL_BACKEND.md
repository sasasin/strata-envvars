# `INK_SYCL_BACKEND`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2 の SYCL backend が GPU を列挙・選択するとき、`opencl` と完全一致する値なら OpenCL backend を選び、それ以外は Level Zero を選ぶ。値に応じて Strata は必要なら `ONEAPI_DEVICE_SELECTOR` を設定し、列挙した GPU を対象 backend で絞り込む。これは `INKLING_ENABLE_SYCL` でビルドされた Inkling-2 経路にある実装で、CUDA/HIP/Metal/CPU backend の選択を変えるものではない（`engine/src/inkling2/CMakeLists.txt:206-208`、`engine/src/inkling2/ink_backend.h:146-167`、`engine/src/inkling2/sycl/ink_sy_common.h:82-116`）。

## 値と判定

`std::getenv` の戻り値を文字列全体で `"opencl"` と比較する。大文字小文字を区別し、空白除去・真偽値変換・数値変換はしない。未設定または完全一致以外は Level Zero 側の分岐になる。無効値として拒否する経路はなく、たとえば空文字、`OpenCL`、`level_zero`、`opencl `、`1` はすべて非 OpenCL として扱われる（`engine/src/inkling2/sycl/ink_sy_common.h:85-86,97-105`）。

| 条件 | unset | OpenCL 分岐になる値 | 非 OpenCL 分岐になる値 |
|---|---|---|---|
| Inkling-2 SYCL backend | Level Zero | 文字列全体が小文字の `opencl` | 空文字、`OpenCL`、`level_zero`、`opencl `、`1` など、それ以外すべて |

GPU index が 0 より大きく、要求 GPU 数が 2 未満で、かつ `ONEAPI_DEVICE_SELECTOR` が未設定の場合、`opencl` なら `opencl:<index>`、それ以外なら `level_zero:<index>` を設定する。GPU index 0 または複数 GPU 要求ではこの分岐で selector を設定せず、primary GPU index を保持する（`engine/src/inkling2/sycl/ink_sy_common.h:82-91`）。

## 有効になる条件

- Inkling-2 の SYCL backend がビルドされて使用されること。Inkling-2 CMake は `STRATA_ENABLE_SYCL` の場合にだけ SYCL subdirectory を追加し、そこで `INKLING_ENABLE_SYCL` を定義する（`engine/src/inkling2/CMakeLists.txt:206-208`、`engine/src/inkling2/sycl/CMakeLists.txt:7-9,43-45`）。
- `ONEAPI_DEVICE_SELECTOR` がすでに設定されていれば、Strata は `apply_gpu_index` と `enum_gpu_devices` からこれを上書きしない。判定は `getenv(...)` の非 null 判定なので、空文字でも「設定済み」として Strata による selector 設定を抑止する。一方、デバイス列挙後の対象 backend の判定には引き続き `INK_SYCL_BACKEND` を使う（`engine/src/inkling2/sycl/ink_sy_common.h:84-89,96-109`）。
- `enum_gpu_devices` が対象 backend の GPU を見つけられない場合は、取得した GPU 一覧の先頭デバイスと同じ backend のデバイス群へ fallback する。したがって `opencl` を指定しても列挙結果に OpenCL GPU がなければ OpenCL への切替は保証されない（`engine/src/inkling2/sycl/ink_sy_common.h:100-116`）。
- CLI の GPU 指定は index と GPU 数に作用し、`INK_SYCL_BACKEND` の文字列判定を上書きしない。Inkling-2 の `--gpu`、`--gpus` / `--devices` は `gpu_index` と `req_gpus` を設定し、backend 初期化時に `apply_gpu_index` へ渡す（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-141,164`、`engine/src/inkling2/sycl/ink_sycl_backend.cpp:65-71`）。

## 実行時の詳細

SYCL backend の `init` はモデル読み込み前に `apply_gpu_index` を呼び、単一 GPU の index 指定がある場合は、selector が未設定なら `INK_SYCL_BACKEND` に基づくデバイス selector を設定する。その後の `Q()` 初期化は `enum_gpu_devices` を呼び、selector が未設定なら `opencl:gpu` または `level_zero:gpu` を設定して GPU を列挙する。列挙後は対象 backend のデバイスだけを返し、該当がなければ一覧先頭の backend 群を返す。`Q()` の SYCL queue と `dev_caps()` の情報は関数内 `static` に保存される（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:65-100`、`engine/src/inkling2/sycl/ink_sy_common.h:82-129,196-209`）。

`INK_SYCL_BACKEND` 自体は呼び出しのたびに `getenv` で読み直され、Strata 内にこの値の cache はない。ただし `Q()` と `dev_caps()` の static cache が初期化された後に環境値を変えても、既存 queue や cache 済み device capabilities は作り直されない。selector が Strata により設定された後は `ONEAPI_DEVICE_SELECTOR` の非 null 判定により後続処理で上書きされない。`apply_gpu_index` は backend 初期化時と selfcheck 時に呼ばれる（`engine/src/inkling2/sycl/ink_sy_common.h:82-129,196-209`、`engine/src/inkling2/sycl/ink_sycl_backend.cpp:65-71,195-198`）。

## ログと測定値

`INK_SYCL_BACKEND` の値、選択した backend、または backend fallback を直接報告するログは確認できない。複数 GPU を要求して可視 GPU が 2 台未満の場合は stderr に `[ink_sycl] --gpus %d requested but only %zu SYCL GPU(s) visible; running single-GPU` を出す。2 台目 GPU の EP 初期化で SYCL exception が発生した場合は `[ink_sycl] Dual-GPU EP init on GPU%d failed (%s); falling back to 1 GPU` を出す。これらは GPU/EP 経路のログであり、環境変数値の警告ではない（`engine/src/inkling2/sycl/ink_sy_common.h:827-833`）。測定値の記載はない。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_common.h:82-116` — 環境値の読み取り、selector 設定、backend 絞り込みと fallback。
- `engine/src/inkling2/sycl/ink_sy_common.h:119-129,196-209` — queue と device capabilities の static cache。
- `engine/src/inkling2/sycl/ink_sycl_backend.cpp:65-100,195-198` — 初期化・selfcheck からの GPU index 適用。
- `engine/src/inkling2/ink_backend.h:146-167`、`engine/src/inkling2/CMakeLists.txt:206-208`、`engine/src/inkling2/sycl/CMakeLists.txt:7-9,43-45` — SYCL backend のビルド・選択条件。
