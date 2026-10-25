# `STRATA_MMVQ_IL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier が複数 token の window を処理するとき、対象となる dense projection と loaded output head で、CUDA の interleaved small-batch matvec (`native_mmvq_il`) を選べるようにします。値が無効、または実装側の対応条件を満たさない場合は `native_mmvq` に進みます。

## 値と判定

`src/core/verify.cpp` の `g_mmvq_il()` は値全体を parse せず、環境変数の有無と先頭文字だけを判定します。判定結果は関数内の `static const bool` に保存されるため、最初に呼ばれた後のプロセス内変更は反映されません。

| 設定 | `g_mmvq_il()` の結果 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（設定値の先頭は終端文字 `\0`） |
| 先頭文字が `0` | 無効（例: `0`, `0anything`） |
| それ以外 | 有効（例: `1`, `true`, `false`, `2`） |

大文字小文字、空白、数値としての妥当性、後続文字は検査しません。従って `false` も有効です。

## 有効になる条件

値判定が有効でも、実際に interleaved kernel が選ばれるのは `native_mmvq_il_supported()` が true を返す場合だけです。

- CUDA であり、compute capability が sm_80 以上、sm_70、または sm_60 であること。sm_70 は `STRATA_SM70_TABLE` が `atoi` で非 0、sm_60 は `STRATA_SM60_TABLE` が未設定または `atoi` で非 0 の場合に限ります。他の古い世代や capability を取得できない場合は無効です。
- `ncols` が 1〜4 であること。
- native MMVQ の複数列出力が exact として有効であること（この実装の初期値は true）。
- 対象型が IQ4_XS (23)、Q4_K (12)、Q5_K (13)、Q6_K (14)、Q3_K (11) のいずれかで、architecture / 型 / 列数 / 出力行数に対応する table の行数が 0 でないこと。

標準 table は主に 2〜4 列用です。1 列では別の table があり、現状は sm_86 の Q3_K の項目だけが定義されています。`STRATA_MMVQ_IL_T1=0` はこの 1 列経路を止め、`STRATA_MMVQ_IL_Q3K=0` は Q3_K の複数列経路を止めます。`STRATA_MMVQ_IL_ROWS` が該当 shape の行を上書きする場合は table 判定に使われます。

HIP には interleaved 実装がなく、対応関数は supported 判定を常に false とし、通常の `native_mmvq` を呼びます。したがって HIP ではこの変数を有効にしても kernel 選択は変わりません。

## 実行時の詳細

Verifier の dense projection helper は、環境判定と `native_mmvq_il_supported()` の両方が true の場合、必要なら q8_1 activation の interleaved copy を作り、その後 `native_mmvq_il()` を呼びます。条件を満たさない場合は同じ入力・shape で `native_mmvq()` を呼びます。Verifier の loaded output head も同じ条件で分岐します。したがってこの変数は通常の単一列 decode 全般を切り替えるものではなく、これら verifier 内の対象呼び出しに作用します。

CUDA の interleaved kernel は対象 shape について通常 kernel と bitwise 同じ出力を意図した実装です。`docs/MMVQ_IL_TABLE.md` も、table は速度選択のみで出力値は同一と説明しています。ここでは測定値を独自に再検証していません。

## 根拠

- `src/core/verify.cpp:136-139`: 環境値の判定と static cache。
- `src/core/verify.cpp:1084-1095`: verifier 内の dense projection と activation interleave / fallback。
- `src/core/verify.cpp:1769-1779`: loaded output head の分岐。
- `src/kernels/cuda/native_mmvq.cu:2642-2662,2682-2708`: shape table、architecture 条件、対応型と supported 判定。
- `src/kernels/cuda/native_mmvq.cu:2705-2747`: CUDA 呼び出しの fallback と HIP stub。
- `include/strata/kernels/native_mmvq.hpp:142-150`: interleaved copy / kernel API と fallback 契約。
- `docs/MMVQ_IL_TABLE.md:1-11`: docs における用途、出力同一性、table の説明。
