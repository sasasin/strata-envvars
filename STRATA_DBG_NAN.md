# `STRATA_DBG_NAN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

非有限値（NaN または無限大）を調べるための診断フックです。値を設定すると、decode verifier の logits、prefill の MoE 中間バッファと prompt 終了時状態を検査し、HIP の FP16 出力 GEMM 経路では FP16 の非有限出力数も数えます。結果は stderr に出ます。通常の数値計算を修正したり、非有限値を置き換えたりする処理ではありません。

## 値と判定

すべての実装箇所で `std::getenv("STRATA_DBG_NAN") != nullptr` または同等の設定有無を使い、文字列の内容は parse しません。

| 環境の状態 | 診断 |
|---|---|
| unset | 無効 |
| `1`、`0`、`false`、任意の文字列 | 有効 |
| 空文字（例: `STRATA_DBG_NAN=`） | 有効 |

値の大小文字、数値としての妥当性、先頭文字は関係ありません。CLI 引数や設定ファイルによる上書きは実装されていません。

## 有効になる条件

- verifier の logits 検査は CUDA と SYCL の verifier 実装で行われます。検査対象の window に非有限 logits がなければ専用ログは出ません。
- prefill の MoE バッファ検査と prompt 終了時状態の検査は CUDA と SYCL の prefill 実装にあります。MoE 検査は MoE combine 後、prompt 状態の検査は prompt prefill の終端で実行されます。
- `src/prefill/gemm.cu` と `sycl/src/prefill/gemm.dp.cpp` の FP16 GEMM 出力カウントは、関数内が `#if defined(__HIPCC__)` に囲まれています。したがって、HIP コンパイラでこの経路をビルドし、`Gemm::f16_inplace()` が使われる場合の診断です。通常の CUDA ビルドではこの GEMM カウント処理は実行されません。
- CPU だけの経路、または該当する verifier/prefill/GEMM 経路を通らない実行で、この変数が全テンソルを検査するわけではありません。

## 実行時の詳細

verifier の CUDA/SYCL 実装は、サンプリング後の出力をコピーした後に logits をホストへ転送し、window の各 row と全 vocabulary logits を走査します。最初に非有限値を見つけると `strata dbg: verify window at position ...` を stderr に一度出します。フラグと「既に報告した」状態は関数内 static です。

prefill の MoE 検査は combine 後に GPU queue/stream を同期し、中間配列をホストへコピーして非有限値を数えます。CUDA は `GU`、`H`、`Dm`、`bo` の各カウントを出し、CPU が担当した行は `GU` / `H` の検査から除きます。SYCL もこれらを調べ、さらに experts の FP16 GEMM 入力である activations と dequantized gate/up の非有限値数・最大有限絶対値を出します。1 chunk につき最初に異常を見つけた layer が報告されるよう `reported` を保持します。診断が有効でも異常がない chunk は MoE 異常ログを出しません。

prompt 終了時には最後の residual row、利用可能なら PLE history、および GDN state 0 を走査し、それぞれの非有限値数と最大有限絶対値を `strata dbg: prompt end: ...` として出します。この経路の設定有無は呼び出し時に直接確認されます。

HIP の `Gemm::f16_inplace()` では、FP16 出力を FP32 に widen する kernel 内で非有限値を数え、stream を同期します。カウントが 0 より大きい場合に限り `strata prefill: STRATA_DBG_NAN: ... non-finite FP16 GEMM outputs ...` を出し、カウンターを 0 に戻します。GEMM 出力が有限ならこの行は出ません。

診断フラグは各 static 初期化箇所が初めて実行された時点で読み取られ、その箇所では以後キャッシュされます。したがって、プロセス実行中の環境変更は、すでに初期化済みの診断箇所には反映されません。prefill 終了時の直接判定はその呼び出しごとに環境を確認します。device/queue 同期、テンソル全体のホスト転送と走査を加えるため、診断有効時には実行時間・メモリ使用量が増える可能性があります。定量的な負荷は資料にありません。

## 根拠

- `src/core/verify.cpp:2342-2358` — CUDA verifier の設定有無判定、logits 全行検査、一度だけ出す stderr ログ。
- `sycl/src/core/verify.cpp:2427-2444` — SYCL verifier の同等処理。
- `src/prefill/prefill.cpp:3899-3923` — CUDA prefill の MoE combine 後の同期、バッファ検査と異常ログ。
- `sycl/src/prefill/prefill.cpp:4238-4292` — SYCL prefill の MoE 検査と FP16 入力診断。
- `src/prefill/prefill.cpp:4075-4091`、`sycl/src/prefill/prefill.cpp:4533-4558` — prompt 終了時状態の検査。
- `src/prefill/gemm.cu:53-70,796-813`、`sycl/src/prefill/gemm.dp.cpp:58-75,938-955` — HIP 条件下での FP16 GEMM 出力カウント、同期、非ゼロ時ログ。
- `docs/INTEL.md:589-600` は SYCL 側で experts の FP16 GEMM 入力も報告する説明、`docs/AMD_HIP.md:430-438` は HIP の FP16 GEMM 出力カウントの説明を含みます。数値負荷についての測定値は記載されていません。
