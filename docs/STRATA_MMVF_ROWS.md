# `STRATA_MMVF_ROWS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

BF16 重みと FP32 活性を使う複数行 MMVF GEMV のカーネル選択を切り替えます。有効時は出力を4行ずつ処理する rows カーネルを選び、同じ出力行数なら通常の複数行カーネルより少ない block 数で計算します。主な呼び出し元は verify window 内の BF16 投影で、router、PLE、indexer などが `bf16_gemv_fp32_mmvf_multi()` を呼びます。`STRATA_LFUSE` の共有 expert gate を router と同じ launch に載せる経路も、rows カーネルを使える条件なら `bf16_gemv_fp32_mmvf_multi_aux()` を使います。

## 値と判定

CUDA 実装と SYCL port は、変数を `getenv()` で読み、値の先頭文字が `'1'` かどうかで判定します。文字列全体の比較や数値 parse はしません。

| 値 | 判定 |
|---|---|
| unset | OFF（ただし起動時の gfx1151 既定値設定で `1` が入る場合を除く） |
| 空文字 | OFF |
| 先頭文字が `1`（例: `1`, `10`, `1foo`） | ON |
| その他（例: `0`, `true`, ` 1`） | OFF |

通常の multi selector と fused auxiliary selector は、それぞれ関数内の `static const bool` に最初の判定結果を保持します。該当関数で一度判定した後にプロセス環境を変更しても、その selector は再評価されません。

## 有効になる条件

- 起動時の自動設定は HIP build に限られます。GPU 0 が gfx1151 なら、Strata は engine code が変数を初回参照する前に `STRATA_MMVF_ROWS=1` を設定します。利用者が変数を何らかの値（空文字を含む）で既に設定していれば、その値を保持します。`STRATA_GFX1151_DEFAULTS` の値が先頭文字 `'0'` なら gfx1151 の既定値テーブル全体を適用しません。
- 自動設定の対象外でも、CUDA/SYCL 実装で先頭文字が `'1'` ならカーネル選択に使われます。unset が自動的に ON になるのは、gfx1151 向け既定値テーブルが適用された場合です。
- 通常の rows 経路は `bf16_gemv_fp32_mmvf_multi()` において、単一行の早期 return 後、入力が通常の形状・ポインタ検査を通過し、`n_out >= 64` のときだけ選択されます。API が受け付ける `n_tok` は 1〜8 ですが、`n_tok == 1` かつ `ldy >= n_out` なら単一行関数へ先に進みます。従って rows 経路を使うのは複数行 2〜8 の呼び出しです。
- auxiliary 経路はさらに `n_tok` が 2〜8 であること、`n_in` が正の偶数、`ldx` が偶数、必要なポインタが non-null、`x` が8-byte aligned であることを要します。条件を満たさないと `false` を返して何も launch せず、呼び出し側は通常の multi GEMV に fallback します。
- CUDA と SYCL の両方に rows 実装があります。Strata の gfx1151 既定値説明は、CUDA や他の AMD GPU にはこの自動設定が適用されないとしています。

## 実行時の詳細

rows kernel は `RPB=4` とし、block ごとに最大4つの出力を計算します。通常の multi kernel は出力ごとに block を割り当てます。rows kernel では各 block が一度読み込んだ各活性行を最大4出力に使い、最後の不完全なグループは `o0 + r < n_out` の検査で範囲外の書き込みを避けます。block size は `n_in` から 32〜256 の候補を選びます。

値が OFF、`n_out < 64`、または auxiliary selector の条件不足なら通常の複数行 kernel が実行されます。単一行呼び出しではこの変数を参照する multi selector に入らず、単一行 kernel が使われます。rows kernel のコメントとヘッダーは、同じ出力について既存 multi kernel と同じ演算順・bitwise 結果になる設計と記しています。

## 文書との照合

`docs/STRIX_HALO.md` は gfx1151 でこの変数を「4-row BF16 GEMV」として既定有効のスイッチ群に記載しています。ソースでは GPU 0 のアーキテクチャを起動時に確認し、ユーザー設定を優先して既定値を設定するため、この説明と実装は一致します。

`docs/A770_SPEED_SPEC.md` の A770 / Level Zero 測定記録では、rows path は比較した複数の形状で default path より1.4〜6倍遅く、A770 の既定値には採用しないとしています。これは同文書記載の A770 ベンチマーク条件での結果であり、gfx1151 や他 GPU の性能を示すものではありません。`docs/DETAILS.md` にはこの変数固有の説明・測定値は見当たりませんでした。

## 根拠

- 起動時の gfx1151 既定値、既設定値の優先、起動ログ: `src/core/arch_defaults.cpp:12-35,61-80`。起動時の呼び出しとタイミング: `src/program/generate.cpp:2152-2158`, `sycl/src/program/generate.cpp:1970-1976`。
- 値判定、通常 multi 経路の単一行分岐・形状条件・fallback: `src/kernels/cuda/native_bf16.cu:295-338`; SYCL port: `sycl/src/kernels/cuda/native_bf16.dp.cpp:581-620`.
- auxiliary 経路の条件と fallback 判定: `src/kernels/cuda/native_bf16.cu:269-293`, `sycl/src/kernels/cuda/native_bf16.dp.cpp:536-579`; 呼び出し側: `src/core/verify.cpp:1433-1448`, `sycl/src/core/verify.cpp:1305-1319`.
- 4出力/block の計算と読み込み: `src/kernels/cuda/native_bf16.cu:136-184,231-252`; bitwise 同値に関する実装コメントと API 契約: `include/strata/kernels/bf16_gemv.hpp:51-60`.
- gfx1151 の説明: `docs/STRIX_HALO.md:83-97`; A770 の測定記録と条件: `docs/A770_SPEED_SPEC.md:503-519`.
