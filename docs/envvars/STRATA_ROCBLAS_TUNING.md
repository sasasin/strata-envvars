# `STRATA_ROCBLAS_TUNING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP engine の prompt FP16-in / FP16-out GEMM で、指定された rocBLAS tuning table に shape 別の solution index があれば、その index を rocBLAS に渡す。対象は `Gemm::f16_inplace` の GEMM で、該当 table が無い shape や利用できない table では既定の GEMM 経路へ戻る。環境変数自体は計算モードを FP16 に切り替えず、その経路は別の `STRATA_HIP_PROMPT_F16` と device 条件で決まる（`engine/src/prefill/gemm.cu:628-677, 681-709, 1460-1471`）。

## 値と判定

値は on/off 文字列ではなく、table ファイルまたはディレクトリへのパス。`std::getenv` の結果が null（未設定）または先頭文字が NUL（空文字）の場合は state を作らず、table を使わない。この場合の明示的な警告はない。`0`、`1`、`true`、`false` を含む空でない値は、特別な boolean parse をされず、その名前の相対パスまたはファイル名として扱われる。前後の空白除去や値の正規化も行わない（`engine/src/prefill/gemm.cu:563-566, 585-592`）。

| 条件 | unset | 設定時に有効になる値 | 無効値・fallback |
|---|---|---|---|
| HIP build で rocBLAS table 対応あり | table state なし。FP16 GEMM は既定経路 | 開ける table ファイルのパス、または table ファイルを含むディレクトリ | 空文字は未設定と同じ。存在しないパス、形式・arch・rocBLAS version が一致しない table はログを出して既定経路へ戻る |
| 非 HIP build、または `STRATA_ROCBLAS_AVAILABLE` なし | 読み取り・適用箇所なし | 該当なし | 値はこの機能には使われない |

指定先がディレクトリなら実行中 device の arch と rocBLAS version を使い、`<arch>-rocblas-<version>.txt`（version 末尾の `.` は除去）を選ぶ。ファイル先頭の有効行は `STRATA_ROCBLAS_TUNING_V1 <arch> <version>` でなければならず、余分な field、arch/version 不一致、無効行、重複 key などは table 全体の読み込み失敗になる。row は `f16o N K ldy token_bucket solution` 形式で、`N/K/token_bucket > 0`、`ldy >= N`。solution は `default` または十進整数で、整数は `int` 範囲内。`default` 行はその shape/bucket で既定 kernel を使う印である（`engine/src/prefill/rocblas_tuning.hpp:31-99`）。

## 有効になる条件

- HIP build で `STRATA_ROCBLAS_AVAILABLE` が定義されていること。CMake は ROCm HIP を有効にし、rocBLAS package target がある場合に `strata_prefill` へこの macro を定義する。rocBLAS が見つからない build では table 機能は利用できない（`engine/cmake/hip_backend.cmake:95-100`, `engine/cmake/strata_gpu_engine.cmake:501-505`）。
- `STRATA_HIP_PROMPT_F16` と device 判定により prompt FP16 I/O 経路が有効であること。その判定は HIP の device ごとに一度 cache され、未設定時は gfx1103 統合 GPU の Linux、および gfx1030/1031/1032 の GPU で有効。それ以外は未設定なら無効で、設定値は先頭文字が `1` の場合だけ有効（`engine/src/prefill/gemm.cu:681-709`, `engine/include/strata/core/arch_defaults.hpp:79-90`）。
- `f16_inplace` に到達する prompt GEMM であること。`f16()` は `f16_io_ && beta == 0` の場合にこの関数へ進み、BF16 prompt 経路も `f16_io_` のとき FP16-in/out GEMM を呼ぶ。通常の GEMMや `beta != 0` の `f16()` 呼び出しは table dispatch の対象外（`engine/src/prefill/gemm.cu:1169-1180, 1318-1320, 1460-1471`）。
- `STRATA_AMD_COMMUNITY_TUNING` が `0` / `off` / `false` / `no` のいずれかと完全一致する場合、community table として登録された gfx1030 / rocBLAS `5.4.0.ad84daa81c` または `5.2.0.dabb6df2b98-dirty` の組み合わせは拒否される。他の値（未設定・空文字を含む）ではこの gate は通る。community 登録外の arch/version はこの gate の対象外（`engine/include/strata/core/amd_community.hpp:32-37, 55-73`）。
- setup は HIP で、検出した GPU arch と一致する `tools/hip/<arch>-rocblas-*.txt` がある場合に限り、run config の `env` に `STRATA_ROCBLAS_TUNING` をその directory に設定する。engine 起動時は親環境を土台に config の `env` を後から上書きするため、config に保存された値が同名の親環境変数より優先される。手動指定時は engine が受け取る環境値が使われる（`terminal/strata_control/setup_config.py:466-473`, `terminal/serve/server.py:4007-4028`）。

## 実行時の詳細

`Gemm::init` または `Gemm::init_external` が呼ばれるたびに `create_rocblas_state` が値を読み、その時点でファイルをロードする。環境値をプロセス全体で cache する実装ではないが、作成済み state は path/table を保持するため、その `Gemm` の生存中に環境を変えても再読込されない。Prefill の初期化では device の prompt FP16 判定も device ごとに atomic cache される（`engine/src/prefill/gemm.cu:563-624, 681-709, 776-799, 854-878`; `engine/src/prefill/prefill.cpp:2722-2729`）。

ディレクトリ指定時は device arch 名の `:` 以降を除き、rocBLAS version 末尾の `.` を削って table 名を組み立てる。table の header で runtime arch/version を照合する。community gate を通過し、table が読めると `rocBLAS tuning enabled` の行を stderr に出す（`engine/src/prefill/gemm.cu:577-603, 619-623`）。

呼び出し shape `(T,N,K,ldy)` ごとに選択結果を cache する。table row は `N/K/ldy` が完全一致するものに限り、`T` は最も近い token bucket を選ぶ。同距離なら小さい bucket が選ばれる。row がない、row が `default`、または solution 呼び出しが失敗した場合は `f16_inplace` の既定 `cublasGemmEx` 経路で計算し、出力を FP16 から widen する。solution 呼び出しが拒否された場合は当該呼び出しで fallback し、同じ shape で3回拒否されると以後その shape は既定 kernel に固定される（`engine/src/prefill/rocblas_tuning.hpp:102-116`, `engine/src/prefill/gemm.cu:626-675, 1460-1474`）。

## ログと測定値

- 未設定または空文字では state を作らず、`STRATA_ROCBLAS_TUNING` に関するログは出ない（`engine/src/prefill/gemm.cu:563-566`）。
- handle 作成・version/device query の失敗、community table の拒否、table 読み込み失敗では stderr に理由と既定 kernel へ戻る旨を出す。読み込み失敗には `cannot open rocBLAS tuning file`、header/row/solution/key の不正、arch/version mismatch などが含まれる（`engine/src/prefill/gemm.cu:567-603`, `engine/src/prefill/rocblas_tuning.hpp:36-90`）。
- table 読み込み成功時は `prefill gemm: rocBLAS tuning enabled (%zu rows, %zu with a solution, %s, rocBLAS %s)` を stderr に出す。`STRATA_ROCBLAS_VERBOSE` が設定されていれば、shape の solution/default 選択、拒否時の fallback、state 終了時の tuned launch 数と solution 呼び出し失敗数も出す。row 不在などの全 fallback 数ではない。verbose の判定は getenv が null かどうかだけなので空文字でも有効（`engine/src/prefill/gemm.cu:554-558, 621-623, 640-647, 661-673`）。
- Strata の資料 `docs/AMD_HIP.md:684-712` は table の arch/version 制約、setup の directory 指定、shape bucket、fallback を説明しており、実装と整合する。そこで挙げる速度値は資料記載の測定結果であり、この調査では再測定していない。

## 根拠

- 主な読み取りと table の適用: `engine/src/prefill/gemm.cu:542-624, 626-675, 1460-1474`
- table format と値検査: `engine/src/prefill/rocblas_tuning.hpp:31-116`
- prompt FP16 経路と cache: `engine/src/prefill/gemm.cu:681-709`, `engine/src/prefill/prefill.cpp:2722-2729`
- build 条件: `engine/cmake/hip_backend.cmake:95-100`, `engine/cmake/strata_gpu_engine.cmake:501-505`
- setup と engine 子プロセスへの環境設定: `terminal/strata_control/setup_config.py:466-473`, `terminal/serve/server.py:4007-4028`
- community table gate: `engine/include/strata/core/amd_community.hpp:32-37, 55-73`
