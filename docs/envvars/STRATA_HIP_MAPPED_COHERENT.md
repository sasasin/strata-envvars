# `STRATA_HIP_MAPPED_COHERENT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows の HIP 経路で、mapped host allocation を行うときに Strata が HIP の割り当て関数へ渡す flags に `hipHostMallocCoherent` を加えるかを切り替える。設定を有効にすると、mapped flag を含む割り当てに coherent flag を OR する。`0` で始まる値なら追加しない。割り当てサイズやポインターはこの変数では変更しない。CUDA 専用ビルドではこの変数を読む Strata のコードはなく、通常の HIP の Windows 以外でも flag 判定は呼ばれない。共通経路は `strata::hip_compat::host_alloc`、HY4 HIP 経路は `hy4::hy4_hip_host_malloc_wddm` が処理する（`engine/include/strata/hip_compat/cuda_runtime.h:2,130-148`; `engine/src/hy4flash/run/hy4_gpu.h:324-385`）。

`docs/SETTINGS.md:382` は対応欄を「NVIDIA and AMD」としているが、この commit の Strata ソースで環境変数を読む箇所は HIP の 2 経路であり、CUDA 専用経路の読み取りは確認できない。

## 値と判定

どちらの実装も `getenv` の結果が未設定であるか、先頭文字が `'0'` かだけを判定する。未設定・空文字・先頭が `0` 以外の任意の文字列は有効扱い。文字列全体の比較、数値変換、大小文字や後続文字の検査はしない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Windows の HIP 共通 `cudaHostAlloc` 経路 | 有効（coherent flag を追加） | 空文字、`1`、`true`、`false`、` 0` など、先頭文字が `0` 以外 | `0`、`0anything` など、先頭文字が `0` |
| Windows の HY4 HIP `hipHostMalloc` 経路 | 有効（coherent flag を追加） | 空文字、`1`、`true`、`false`、` 0` など、先頭文字が `0` 以外 | `0`、`0anything` など、先頭文字が `0` |
| Windows 以外、または CUDA 専用経路 | Strata の判定箇所は実行されない | 該当なし | 該当なし |

表中の `0anything` は無効例、` 0` は先頭が空白なので有効例。共通経路は `v == nullptr || v[0] != '0'`（`engine/include/strata/hip_compat/cuda_runtime.h:131-136`）、HY4 経路は `v == nullptr || v[0] != '0'`（`engine/src/hy4flash/run/hy4_gpu.h:374-380`）で判定する。

## 有効になる条件

- 対象は Windows 上の HIP ビルドであること。共通ヘッダーは HIP 専用であり、flag の追加処理は `_WIN32` 条件内にある（`engine/include/strata/hip_compat/cuda_runtime.h:2,138-148`）。HY4 の独自処理も `_WIN32` 条件内にある（`engine/src/hy4flash/run/hy4_gpu.h:371-385`）。
- 実際の割り当て flags に `cudaHostAllocMapped` / `hipHostMallocMapped` が含まれること。共通ヘルパーはこの bit がある場合だけ判定し、HY4 ヘルパーも mapped bit がある場合だけ判定する（`engine/include/strata/hip_compat/cuda_runtime.h:138-146`; `engine/src/hy4flash/run/hy4_gpu.h:374-380`）。
- 追加の CLI 引数や別の環境変数による優先順位・上書きは、これらの読み取り箇所にはない。mapped bit がない割り当てには影響しない。たとえば共通ヘッダーの `cudaMallocHost` は別の `malloc_host` 経由で default flags を渡し、この変数を参照しない（`engine/include/strata/hip_compat/cuda_runtime.h:87,151-153`）。

## 実行時の詳細

共通 HIP 互換層では `cudaHostAlloc` が `strata::hip_compat::host_alloc` にマクロ展開される。Windows で mapped bit があるとき、関数内 static の `mapped_coherent_enabled()` が環境を読み、真なら `hipHostMallocCoherent` を flags に OR してから `hipHostMalloc` を呼ぶ。関数内 static のため判定結果はプロセス内で初回呼び出し時に一度だけ初期化され、その後の環境変更は反映されない。mapped bit がない呼び出しでは判定関数に到達しない（`engine/include/strata/hip_compat/cuda_runtime.h:69,131-148`）。

HY4 HIP には別の Windows 用ラッパーがあり、mapped bit のある `hipHostMalloc` で関数内 static `coherent_win` を初期化する。こちらも初回の該当割り当て以降は値を再読込しない。両経路とも最終的に割り当て関数の戻り値をそのまま返す（`engine/src/hy4flash/run/hy4_gpu.h:371-385`）。

## ログと測定値

この変数の読み取りや flag の追加だけを理由にしたログ、警告、終了処理はない。割り当てエラーは HIP 割り当て関数の戻り値として呼び出し元へ返るため、その後の扱いは各呼び出し元による（`engine/include/strata/hip_compat/cuda_runtime.h:144-148`; `engine/src/hy4flash/run/hy4_gpu.h:374-382`）。Strata の資料に、この変数に結びついた条件付き測定値は確認できない。

## 根拠

- `engine/include/strata/hip_compat/cuda_runtime.h:2,69-77,130-153` — HIP 限定の互換層、`cudaHostAlloc` の転送、値判定、mapped flags への追加、戻り値。
- `engine/src/hy4flash/run/hy4_gpu.h:324-385` — HY4 HIP 分岐の Windows 用読み取りと mapped allocation ラッパー。
- `engine/CMakeLists.txt:104,146-149` — HIP と CUDA を別 backend とする設定条件。
