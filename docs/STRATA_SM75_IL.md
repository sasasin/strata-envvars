# `STRATA_SM75_IL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA compute capability 7.5（Turing）の interleaved small-batch matvec table を個別に有効・無効にします。この table は native MMVQ の一部の重み型・列数に使う行数設定です。`STRATA_SM75_IL` が未設定なら、同じく Turing 向けの opt-in 集合を制御する `STRATA_SM75_PERF` に従います。`STRATA_SM75_IL` が設定されていれば、その判定結果が `STRATA_SM75_PERF` より優先されます。

## 値と判定

`sm75_switch()` はまず対象 device が compute capability 7.5 か確認し、その後 `STRATA_SM75_IL` を読みます。変数が設定されていれば `atoi(value) != 0`、未設定なら `STRATA_SM75_PERF` の `atoi(value) != 0` を使います。

| `STRATA_SM75_IL` | table の許可判定（sm_75 の場合） |
|---|---|
| 未設定 | `STRATA_SM75_PERF` が未設定または整数変換結果 0 なら無効、非 0 なら有効 |
| 空文字 | `atoi("")` は 0 なので無効 |
| `0`, `00`, `0abc`, `junk` | 整数変換結果が 0 なので無効 |
| `1`, `1abc`, `2`, `-1`, ` 1` | 整数変換結果が非 0 なので有効 |

整数変換は `atoi` なので、先頭空白と符号を許容し、数値の後ろの文字列は無視します。数値として読めない文字列や数値接頭辞のない文字列は 0 になります。大文字小文字の比較はありません。`STRATA_SM75_PERF` にフォールバックする場合も同じ `atoi(...) != 0` 判定ですが、同変数の未設定は無効です。

## 有効になる条件

- この経路は CUDA native MMVQ 実装です。HIP 側では `native_mmvq_il_supported()` は常に false です。
- 現在の device が compute capability 7.5 の場合だけ `STRATA_SM75_IL` を参照します。別 capability では table はこの変数によって有効になりません。
- native interleaved path 自体が使われるには、呼び出し元の `STRATA_MMVQ_IL` が許可し、native MMVQ の multi-column exact layout が有効で、列数・量子化型・table に対応する行数も有効である必要があります。これらを満たさない場合は通常の `native_mmvq` kernel に fallback します。
- `STRATA_MMVQ_IL_T1`、`STRATA_MMVQ_IL_Q3K`、`STRATA_MMVQ_IL_ROWS` などの別設定により、対象型や列数の table 行が無効・上書きされる場合があります。`STRATA_SM75_IL=1` はこれらの条件を無視して全ての入力に interleaved kernel を使わせる指定ではありません。

## 実行時の詳細

`src/kernels/cuda/native_mmvq.cu` の `sm75_il_on()` が共通 helper `sm75_switch()` を呼び、`il_arch_ok()` が device ごとに capability 判定を cache します。device の判定結果は `ok[16]` に保持され、同じ device について環境変数を後から変更しても再判定されません。フォールバック先の `STRATA_SM75_PERF` 判定も `sm75_series()` の function-local static に cache されます。

許可された場合でも、実際の interleaved kernel 呼び出しでは `native_mmvq_il_supported()` が列数 1〜8、exact layout、architecture table の有無、および量子化型に対応する行数を確認します。対応しない場合、`native_mmvq_il()` は `native_mmvq()` を呼びます。対応する場合は interleaved kernel を選択します。`STRATA_SM75_IL` 自体を読むことによる専用ログはありません。

## 文書・測定値との照合

`docs/DETAILS.md` は `STRATA_SM75_PERF=1` が Turing 上の bitwise kernel 群を許可し、各個別変数が `=0` で無効、`=1` で有効にできると説明しています。`STRATA_SM75_IL` についても個別の interleaved small-batch matvec table と記載されています。現行 helper は値を `atoi` で変換するため、説明にある `0` / `1` 以外も整数変換結果に従って扱います。資料には RTX 2080 Ti でのシリーズ測定が記載されていますが、`STRATA_SM75_IL` 単独の性能値はこの調査では確認できません。

## 根拠

- `include/strata/core/sm75_series.hpp:24-44`: `STRATA_SM75_PERF` の cache、Turing capability 判定、変数設定時の優先順位と `atoi` 判定。
- `src/kernels/cuda/native_mmvq.cu:3200-3225`: `STRATA_SM75_IL` 呼び出し、Turing 条件、device ごとの architecture 判定 cache。
- `src/kernels/cuda/native_mmvq.cu:3141-3174,3229-3256`: table 行の選択と対応条件、unsupported 時の fallback。
- `src/core/verify.cpp:164-165,1333-1342,1375-1384`: `STRATA_MMVQ_IL` による上位 gate と verifier からの利用箇所。
- `src/kernels/cuda/native_mmvq.cu:3259-3268`: HIP 実装は interleaved path をサポートしない。
- `docs/DETAILS.md:2526-2543`: Turing 系列の説明、個別スイッチと資料に記載された測定範囲。
