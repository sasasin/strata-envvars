# `MMVQ_IL_TMAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`MMVQ_IL_TMAX` は `mmvq_il_parity` 診断実行ファイルが、合成入力で interleaved matvec の parity 確認・benchmark を行う列数 `T` の上限を指定する。エンジンの通常推論やモデル設定を変える環境変数ではない。対象ファイルでの読み取りは `run_case` 内だけで、各ケースの `T` ループの上限に使われる（`engine/src/kernels/mmvq_il_parity.cpp:155-156, 181-186`）。

## 値と判定

`std::getenv` が null かどうかだけで未設定を判定し、設定されていれば `std::atoi` に渡す。文字列全体の検証や範囲チェック、無効値の警告、fallback はない。`atoi` は先頭の空白と符号の後の数値部分を変換し、数値として読めない文字列では 0 になる。したがって、後続の文字は無視される。

| 条件 | unset | 有効になる値（例） | 無効・ループを空にする値（例） |
| --- | --- | --- | --- |
| `mmvq_il_parity` の `run_case` | `t_max=8` | `5` → 上限 5、`  +5tail` → 上限 5 | 空文字、`false`、`0anything` → 上限 0。`-2` → 上限 -2。既定の `MMVQ_IL_TMIN=1` より小さい上限なら `T` ループは実行されない |

上限は `T <= t_max` の包含比較で使われる。既定の `MMVQ_IL_TMIN` は 1 で、両方を設定した場合は `MMVQ_IL_TMIN` が下限、`MMVQ_IL_TMAX` が上限となる。上下限が逆転しても補正されず、ループが 0 回になる。`atoi` で `int` に表せない値を入れた場合の安全な範囲制限もコードにはない（`engine/src/kernels/mmvq_il_parity.cpp:184-186`）。

## 有効になる条件

- `mmvq_il_parity` が実行されるときだけ参照される。CMake では `STRATA_ENABLE_CUDA` の構成でこの実行ファイルを追加する。`STRATA_HIP_GFX906` は `STRATA_ENABLE_CUDA` を ON にする互換構成だが、一般の HIP/SYCL/Metal や CPU 専用構成にはこのターゲットがない（`engine/cmake/strata_gpu_engine.cmake:801-818`; `engine/CMakeLists.txt:91-103`）。
- この実行ファイルは GPU 上で合成データの `native_mmvq` と `native_mmvq_il` を比較する診断用であり、モデルのロードや通常の生成経路ではない（`engine/cmake/strata_gpu_engine.cmake:813-818`; `engine/src/kernels/mmvq_il_parity.cpp:155-163, 199-203, 225-243`）。
- `MMVQ_IL_TMIN` が上限より大きい場合は比較・計時の `T` ループが動かない。`MMVQ_IL_ONLY` が設定されていると、別途ケース名で対象ケースを絞る（`engine/src/kernels/mmvq_il_parity.cpp:521-523`）。
- `--bench` は計時を有効にする CLI 引数だが、`T` の範囲は parity-only 実行でも benchmark 実行でも同じ環境変数で決まる。CLI 引数による `MMVQ_IL_TMAX` の上書きはない（`engine/src/kernels/mmvq_il_parity.cpp:471-490, 218-219`）。

## 実行時の詳細

`run_case` が呼ばれるたびに `MMVQ_IL_TMAX` を読み直す。関数内 static cache はなく、読み取った値はそのケースの `for (T = t_min; T <= t_max; ++T)` に適用される。コードにはこの値を子プロセスへ渡す処理や、実行中に設定を更新する処理はない（`engine/src/kernels/mmvq_il_parity.cpp:155-186, 522-523`）。

各 `T` について合成入力を生成し、通常経路の結果と interleaved 経路の出力を比較する。差分または非有限の参照値があれば `FAIL ... T=...` を標準出力へ出し、失敗数を加算する。`--bench` の場合は同じ `T` ごとに parity check の後で計時も行う（`engine/src/kernels/mmvq_il_parity.cpp:187-203, 225-243, 247-278`）。上限を下げると調査対象となる `T` が減り、上限が下限未満ならケースの parity check と計時は省かれる。`check_tables()` は `T` ループより前に実行されるため、この場合もテーブル検査自体は行われる（`engine/src/kernels/mmvq_il_parity.cpp:402-467, 509-523`）。

## ログと測定値

`MMVQ_IL_TMAX` 自体について、設定値や採用した上限を表示するログ、無効値の警告、専用の終了エラーはない。ループが動けば parity 不一致は `FAIL ...` 行に現れ、最後に `mmvq_il_parity: FAIL` と終了コード 1、または `mmvq_il_parity: OK (every case, T 1-8, rows 1/2/4 and the table, bitwise)` と終了コード 0 を返す（`engine/src/kernels/mmvq_il_parity.cpp:240-243, 521-526`）。最終行の `T 1-8` は固定文字列で、指定した範囲を反映しない。例えば既定の `TMIN=1` と `TMAX=0` ではケースループが空でも、テーブル検査が通ればこの `OK` 行が出るため、出力だけでは全ケースの parity が確認されたとは分からない。

`docs/MMVQ_IL_TABLE.md` は `mmvq_il_parity --bench --emit-table` を GPU 上で実行してテーブルを測る手順を案内しているが、`MMVQ_IL_TMAX` に関する測定値や性能主張は記載していない（`docs/MMVQ_IL_TABLE.md:24-38`）。本調査では build・GPU 実行・性能測定を行っていない。

## 根拠

- `engine/src/kernels/mmvq_il_parity.cpp:155-186` — ケース処理、`MMVQ_IL_TMAX` / `MMVQ_IL_TMIN` の読み取りと `T` 範囲。
- `engine/src/kernels/mmvq_il_parity.cpp:187-243, 247-278` — 合成入力、parity 比較、benchmark の流れ。
- `engine/src/kernels/mmvq_il_parity.cpp:471-490, 509-526` — CLI、ケース選択、最終ログと終了コード。
- `engine/cmake/strata_gpu_engine.cmake:813-818` — CUDA 構成での `mmvq_il_parity` ターゲット追加。
- `engine/CMakeLists.txt:91-103` — CUDA 構成と gfx906 互換構成。
- `docs/MMVQ_IL_TABLE.md:24-38` — parity/benchmark ツールの資料上の用途。
