# `STRATA_IL_PAD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

CUDA の interleaved small-batch MMVQ で、IQ4_XS の入力列数が 5 のとき、6 列用 kernel を使って最初の 5 列だけを出力するかを切り替えます。既定ではこの padding が有効です。値は性能経路の選択に使われ、kernel は余分な 1 列も計算しますが保存しません。kernel の各列は独立した和を計算するため、コード上は 5 列用 kernel と保存される値が bitwise 同じとされています（`src/kernels/cuda/native_mmvq.cu:2157-2159,2200-2208,2271-2277`）。

## 値と判定

値全体の真偽値比較ではなく、`std::atoi` で整数に変換し、その結果の bit 0 が立っているかを調べます。

| 入力 | `atoi` の結果 | padding |
|---|---:|---|
| 未設定 | 既定値 `1` | 有効 |
| 空文字 | `0` | 無効 |
| 数字で始まらない文字列（例: `true`, `false`） | `0` | 無効 |
| `1`, `3`, `-1` など、変換後の整数の bit 0 が 1 | 変換された整数 | 有効 |
| `0`, `2`, `-2` など、変換後の整数の bit 0 が 0 | 変換された整数 | 無効 |

`atoi` のため、先頭の空白と符号は整数変換で扱われ、数字の後ろにある文字列は判定に使われません（例: `1xyz` は 1、`0xyz` は 0）。小数点や指数表記としては解釈されず、数値変換できない先頭なら 0 です。文字列の大文字小文字は比較しません。値は `il_pad()` 内の関数ローカル `static const int` に保存され、最初にこの分岐を通った後で環境を変更しても再評価されません（`src/kernels/cuda/native_mmvq.cu:2246-2249`）。

## 有効になる条件

- CUDA コンパイルの interleaved MMVQ 経路に限られます。同ファイルの interleaved 実装は `!__HIPCC__` 側にあり、HIP 側は `native_mmvq_il_supported()` が常に `false`、`native_mmvq_il()` は通常の `native_mmvq()` に委譲します（`src/kernels/cuda/native_mmvq.cu:1607-1608,3987-4003`）。
- `native_mmvq_il()` の呼び出し時に、列数が 1〜8、exact layout が有効、GPU 世代が interleaved 対応、型と行数に対する table の行数が非ゼロである必要があります。どれかを満たさない場合は通常の `native_mmvq()` を実行します（`src/kernels/cuda/native_mmvq.cu:3956-3966`）。
- 環境変数が実際に分岐するのは、対応経路で列数が 5、型が IQ4_XS、行数/warp が 1 または 2 のときだけです。ほかの量子化型、列数、行数ではこの変数の値を読みません（`src/kernels/cuda/native_mmvq.cu:2263-2277`）。5〜8 列の table がないカードでは interleaved 経路自体が選ばれず、通常 kernel になります。文書化された現行 table 概要では 5〜8 列 table は sm_120 のみです（`docs/MMVQ_IL_TABLE.md:3-10,14-22`）。
- verifier は `STRATA_MMVQ_IL` が unset または先頭文字が `0` 以外の場合に interleaved 経路を検討します。これが `0` で始まると呼び出し元が通常 kernel を選び、この変数は効果を持ちません（`src/core/verify.cpp:181-184,1639-1648,2611-2617`）。

## 実行時の詳細

verifier の dense projection と出力 head は、対応条件が揃えば interleaved MMVQ を呼びます。speculative decode の head も同じ CUDA kernel 経路を使います（`src/core/verify.cpp:1639-1648,2611-2617`; `src/core/dflash2.cpp:520-528`）。その中で IQ4_XS の 5 列呼び出しだけ、bit 0 が立っていれば 6 列・5 出力の template instantiation を起動します。bit 0 が 0 なら 5 列の kernel を起動します。6 列側は各列の和を計算し、`c < NOUT` の列だけを書き出します（`src/kernels/cuda/native_mmvq.cu:2199-2208,2271-2277`）。

この値に対する専用ログや警告はありません。interleaved MMVQ が非対応なら通常 MMVQ に fallback します。kernel launch が失敗した場合は `cudaGetLastError()` を確認し、`native MMVQ launch: <CUDA error>` の `std::runtime_error` を送出します（`src/kernels/cuda/native_mmvq.cu:2353-2357,3962-3966,3984`）。`docs/DETAILS.md` と `docs/MMVQ_IL_TABLE.md` に本変数固有の性能測定値は見当たらないため、速度差は記載しません。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:2157-2159,2199-2208` — 余分な列の計算と出力列数制限、および列ごとの和。
- `src/kernels/cuda/native_mmvq.cu:2246-2249,2271-2277` — 既定値、`atoi`、bit 0 判定、IQ4_XS の 5 列分岐。
- `src/kernels/cuda/native_mmvq.cu:3956-3966,3987-4003` — interleaved 実装の適用条件、通常 kernel への fallback、HIP 実装。
- `src/core/verify.cpp:181-184,1639-1648,2611-2617`; `src/core/dflash2.cpp:520-528` — 呼び出し側の interleaved 経路。
- `docs/MMVQ_IL_TABLE.md:3-10,14-22` — interleaved MMVQ の列数範囲と GPU table の説明。
