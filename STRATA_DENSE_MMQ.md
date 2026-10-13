# `STRATA_DENSE_MMQ`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有ソース。外部ライブラリ内部の動作は対象外。

## 役割

HIP ビルドで prompt の dense GGUF projection を処理する際、通常の「GGUF block を FP16 に dequantize して GEMM」する経路の代わりに、GGML の int8 MMQ を使う opt-in スイッチです。`Gemm::native()` の beta が `0.0f` の積に適用されます。CUDA の実行経路ではこの環境変数を読みません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` などを受け付ける |
| その他 | 無効。`0`, `true`, 空白、負数など、先頭文字が `1` でない値 |

数値変換や文字列全体の比較はせず、`e[0] == '1'` だけを見ます。判定は関数内の `static const bool` に保存されるため、最初の `native_mmq()` 呼び出し後にプロセスの環境を書き換えても再評価されません。

根拠: `src/prefill/gemm.cu:730-739`。

## 有効になる条件

環境変数を有効にしても、次の条件をすべて満たす積だけが MMQ 経路を使います。

- HIP backend で、ビルド時に `STRATA_PREFILL_MMQ=ON` を指定して MMQ prefill を組み込んでいること。この CMake option は既定 OFF で、HIP 以外で有効にすると configure error になります。
- `Gemm::native()` の `beta == 0.0f` かつ `ldx == 0 || ldx == K`。加算積（beta が 0 以外）や padded activation は対象外です。
- 対象 quant type と出力行数について、MMQ が全認識 GPU の shared memory に収まる tile を持つこと。行数が 128 の倍数でないと fallback 用 configuration を選びます。
- `K <= 8192` かつ `K % 256 == 0`。
- scratch から計算される一度に処理可能な row 数 `R = scratch_elems_ / (2 * K)` が 1 以上であること。
- 一時 device buffer の確保に失敗しておらず、当該 `Gemm` instance で `mmq_failed_` が立っていないこと。

ソースの型対応は Q2_0、IQ2_XXS/XS/S、IQ3_XXS/S、IQ4_NL/XS、Q8_0。`STRATA_MMQ_KQUANTS` を含むビルドでは Q4_K、Q5_K、Q5_1 も追加され、HIP では Q6_K も追加されます。別の build option `STRATA_ORCA_Q4KS_MMQ` は Q5_0 を追加します。未対応型の場合、このスイッチだけでは MMQ は使われません。

条件を外れた場合、`native()` は通常の dequantize + `f16()` 経路へ進みます。GPU に適合する MMQ tile がない場合は、その型について一度 `strata: prompt kernels: llama.cpp's MMQ has no tile ... that product takes the non-MMQ path (#420)` と stderr に出します。MMQ workspace の `cudaMalloc` 失敗時は CUDA error をクリアして MMQ を無効化し、この積を通常経路へ fallback します。

根拠: `CMakeLists.txt:71-86,1416-1460`, `src/prefill/gemm.cu:819-870`, `src/prefill/moe_mmq.cu:119-168`。

## 実行時の詳細

呼び出し元の `native_proj()` は native GGUF block が存在する重みを `Gemm::native(..., beta=0.0f, ...)` に渡します。`Gemm::native()` は、padded X の処理を先に試し、その後、条件が合えば `native_mmq()` を呼びます。MMQ 経路では activation を FP32 に変換し、MMQ 用に量子化したうえで、行を最大 1024 行ずつ処理します。`K` が 256 の倍数でない積は weight 行を越えて読む危険があるため、この経路を使いません。

MMQ buffer を初めて確保したときに stderr へ `prefill gemm: dense MMQ on (STRATA_DENSE_MMQ=1)` と出ます。これは buffer 初期化時のログであり、各 projection の利用ログではありません。MMQ が使われない積について個別ログが常に出るわけではありません。

根拠: `src/prefill/prefill.cpp:1936-1940`, `src/prefill/gemm.cu:730-793,819-870`。

## 文書との照合

`docs/AMD_HIP.md:206-211` はこのスイッチを既定 OFF の HIP opt-in とし、RX 6900 XT で 4K prompt が 436 から 757 tok/s になった記録と、q8_1 activation rounding により greedy text が数十 token 後から既定経路と異なるという注意を記しています。測定条件は同節に記された内容に限られ、他の GPU やモデルでの性能・出力を保証するものではありません。`docs/DETAILS.md:278` も AMD HIP の設定として `AMD_HIP.md` に案内しています。

## 根拠

- `src/prefill/gemm.cu:730-739`: HIP MMQ 関数と環境変数の判定。
- `src/prefill/gemm.cu:740-793`: shape 条件、buffer 確保、MMQ 実行と有効ログ。
- `src/prefill/gemm.cu:819-870`: `native()` からの呼び出し条件と通常 GEMM への fallback。
- `src/prefill/moe_mmq.cu:121-168`: 対応 quant type、device tile/shared-memory 適合判定と警告。
- `CMakeLists.txt:71-86,1416-1460`: HIP 限定の build 条件と MMQ compile option。
- `src/prefill/prefill.cpp:1936-1940`: native projection からの呼び出し。
- `docs/AMD_HIP.md:206-211`, `docs/DETAILS.md:278`: 設定説明と記載された測定結果。
