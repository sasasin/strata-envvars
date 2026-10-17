# `STRATA_RDNA2_SGEMM`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。外部ライブラリの内部動作は対象外。

## 役割

HIP の prefill dense GEMM で、FP16 または BF16 の入力を FP32 に拡張してから FP32 SGEMM を使う経路を選びます。主な呼び出し元は BF16 GEMM と FP16 GEMM です。この変数は経路選択だけを変え、Strata は `hipblasSgemm` を呼び出します。変数が未設定または無効なら、呼び出し元の通常 GEMM に進みます。

## 値と判定

判定は `rdna2_sgemm_on()` の最初の呼び出しで一度行われ、関数内の `static const int mode` に保存されます。空文字と未設定は同じく無効です。

| 値 | 判定 |
|---|---|
| unset、空文字 | 無効（`mode=0`） |
| 文字列全体が小文字の `all` | 全 AMD GPU 向け（`mode=2`） |
| それ以外で `atoi(value) > 0` | gfx103x 向け（`mode=1`） |
| `atoi(value) <= 0` | 無効（`mode=0`） |

`all` の比較は大文字小文字を区別し、文字列全体の一致が必要です。数値判定は `atoi` なので、文字列全体の数値検証ではありません。たとえば `1abc`、`+1`、先頭空白の後の `1` は正数として判定され、`0abc`、`-1`、数値で始まらない文字列は無効です。`2` も `all` ではなく gfx103x モードになります。

## 有効になる条件

- HIP コンパイル時にだけ、この読み取りと経路がコンパイルされます（`__HIPCC__`）。CUDA 専用ビルドではこの変数を読むコードはありません。
- SGEMM 経路は `K > 0` かつ `N >= 64` の場合に限られます。`N < 64` の router/gate 等は設定値にかかわらず通常経路を使います。
- `mode=1` は実行中の HIP device の `gcnArchName` が `gfx103` で始まる場合だけ有効です。各 device の architecture 判定結果は最大64 device分 static 配列に cache されます。device query が失敗するか device index が範囲外なら無効になります。
- `mode=2`（値が厳密に `all`）は architecture 判定を飛ばして、`N >= 64` の AMD device で有効になります。
- BF16 呼び出しでは、先行する hipBLASLt 経路が処理した場合はそこで戻るため、この SGEMM 判定に到達しません。また `ldx != 0`（padded X）の場合も SGEMM 呼び出しをスキップし、通常経路を使います。
- BF16 呼び出しで `f16_io_` が有効な場合は、その専用 FP16 画像経路が先に処理して戻るため、この環境変数の経路には入りません。
- scratch 用 FP32 buffer の確保に失敗した場合は `rdna2_sgemm()` が false を返し、呼び出し元が通常 GEMM を実行します。

## 実行時の詳細

有効な場合、Strata は重みを FP32 buffer に拡張し、入力 activation は最大128 MiB相当ずつの slice に分けて同じ stream 上で FP32 に拡張します。その後、各 slice の出力範囲に `hipblasSgemm` を発行します。FP16/BF16からFP32への拡張後の値は表現上正確ですが、native GEMM と加算順序が異なるため、結果は bit-identical とは限りません。ソースコメントでは差が和の順序によるものとされています。

BF16 GEMM は hipBLASLt の試行後、`ldx == 0` のときにこの経路を試します。FP16 GEMM は HIP 用呼び出し箇所からこの経路を試します。成功すれば通常 GEMM を呼ばず、失敗または条件不一致なら通常経路へ進みます。読み取りはリクエストごとではなく最初の `rdna2_sgemm_on()` 呼び出し時であり、実行中に環境を変更しても mode は再評価されません。ソースにこの変数の専用ログ出力はありません。

## 根拠

- `src/prefill/gemm.cu:849-869` — 環境変数の読み取り、`all` / `atoi` 判定、mode cache、device architecture 判定。
- `src/prefill/gemm.cu:885-906` — shape gate、buffer 確保、FP32 拡張、SGEMM 発行。
- `src/prefill/gemm.cu:921-960` — BF16 経路の順序、hipBLASLt・`ldx` 条件・呼び出し元 fallback。
- `src/prefill/gemm.cu:1104-1106` — FP16 経路の呼び出し。
- `docs/AMD_HIP.md:550-576` — 経路の説明と、RX 6800での測定条件・結果。記載値は同資料の測定結果であり、ここで再測定したものではありません。
