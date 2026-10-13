# `STRATA_PF_HCDOWN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査対象リポジトリの作業ツリーは clean。外部ライブラリの内部動作は対象外。

## 役割

長い prompt chunk の hyper-connection 読み取りで、down projection と inject projection を別々に計算する代わりに、一つの BF16 WMMA GEMM にまとめる実験用スイッチです。入力 `xn16` を一度読んで、down の出力 `lo` と inject の出力 `inj` を作ります。HIP gfx11 用の実装は `src/prefill/wmma_gemm.cu` にあります。

通常経路では既定で無効で、HIP gfx11 向けの prompt 性能最適化を明示的に試す opt-in 設定です。資料の `docs/DETAILS.md` にこの変数の説明や測定値は見つかりませんでした。

## 値と判定

値は文字列全体として比較せず、環境変数が存在し、先頭文字が `1` かを確認します。

| 設定値 | 判定 |
|---|---|
| 未設定、空文字 | 無効 |
| 先頭文字が `1` | 有効。例: `1`, `10`, `1anything` |
| それ以外 | 無効。例: `0`, `true`, `false`, ` 1` |

数値変換や trim、大文字小文字変換はありません。判定結果は `pf_hcdown()` 内の function-local `static const bool` に保存されます。最初の呼び出し時に一度だけ読み込むため、その後プロセス内で環境を変えても再評価されません。CUDA/HIP と SYCL の実装に同じ形式の helper があります。根拠: `src/prefill/prefill.cpp:333-336`, `sycl/src/prefill/prefill.cpp:267-270`。

## 有効になる条件

値が有効でも、全ての prompt chunk で fused GEMM が実行されるわけではありません。

- 実際の処理は hyper-connection の各 half（`hc_attn`、`hc_ffn`）の読み取り時に判定されます。
- `hc_pad()` が true である必要があります。これは `STRATA_PF_HCDOWN` または関連する `STRATA_HCD_EXACT` が有効な場合です。
- chunk の token 数 `T` が `max(STRATA_PF_SWITCH_MIN_T, 64)` 以上である必要があります。`STRATA_PF_SWITCH_MIN_T` 未設定時は0なので、この変数単独の場合の最低長は64 tokensです。
- `STRATA_GR_UNFUSED` が有効でなく、BF16 low-part 用の `m.xn16_lo` がない場合に限り、padded token stride `D + 64` が選ばれ、HCDOWN 分岐へ進みます。
- down/inject の両重みが `Bf16InF32` 形式で、ポインタと形状が期待どおりである必要があります。カーネル側も入力、出力、`T >= 64`、`K` が64の倍数、stride 等を検査します。
- 実カーネルは HIP ビルドの gfx11 WMMA 対応 device（gfx1100/1101/1102/1150/1151）でのみ動きます。`STRATA_WMMA_GFX11` ビルドと実行 device の判定が必要です。CUDA など非 HIP ビルドではヘッダーが常に false を返す stub です。SYCL の prefill も同じヘッダーを include しており、別の SYCL カーネル実装は見つかりませんでした。

これらの条件が合わない場合、結果は条件により異なります。chunk が閾値未満、`STRATA_GR_UNFUSED` 有効、または low-part buffer がある場合は padded stride にならず、通常の projection 経路へ進みます。一方、padded stride で HCDOWN 分岐へ入った後に重み検査または WMMA 関数が失敗すると、通常の projection へ戻らず、prefill は `prefill: STRATA_PF_HCDOWN could not run the hyper-connection projections` をエラーとして false を返します。CUDA/SYCL、非対応 GPU、非対応形状で opt-in する際は特にこの差が重要です。根拠: `src/prefill/prefill.cpp:2570-2590`, `sycl/src/prefill/prefill.cpp:2813-2833`, `src/prefill/wmma_gemm.h:24-35`, `src/prefill/wmma_gemm.cu:653-663`。

## 実行時の詳細

通常は hyper-connection の down projection を `bf16_proj()` で実行し、inject projection も別の処理で計算します。HCDOWN が有効で上記条件を満たすと、`strata_pf_hcdown_bf16()` が両方の BF16 重みを一つの GEMM として読み、FP32 の `lo` と `inj` を生成します。入力行 stride は `D + 64` です。コード注釈では通常の stride `10240` に対して `10240 + 64` を使う設計とされ、重みの K 次元は64の倍数、chunk は64 tokens以上です。カーネルは FP32 accumulation を使いますが、hipBLASLt と異なる K の演算順序になると実装コメントに記載されています。出力の数値差や品質、速度は本調査では測定していません。

`STRATA_HCD_EXACT=1` も同時に設定されていても、`STRATA_PF_HCDOWN` が有効なら HCDOWN の分岐が優先されます。HCDOWN が無効で exact が有効な場合は、padded stride の down projection に `bf16_hcd_exact()` を試し、inject projection は通常経路に残します。`STRATA_PF_SWITCH_MIN_T` は chunk 長のゲートを調整する関連変数です。根拠: `src/prefill/prefill.cpp:330-345,2570-2590`, `src/prefill/wmma_gemm.cu:480-485,653-663`。

成功時に HCDOWN の有効化だけを知らせる専用ログは見つかりませんでした。実行できない場合は上記のエラー文字列が `err` に設定され、prefill の処理が失敗します。根拠: `src/prefill/prefill.cpp:2581-2587`; SYCL: `sycl/src/prefill/prefill.cpp:2824-2830`。

## 根拠

- `src/prefill/prefill.cpp:330-345` — 環境変数の先頭文字判定、static cache、関連 stride helper。
- `src/prefill/prefill.cpp:2570-2590` — chunk 長、padding、`gr_unfused`、BF16 weight 条件、fused call、失敗時の扱い。
- `src/prefill/wmma_gemm.h:24-35` — API の shape / dtype / K / token 条件、HIP 外の false stub。
- `src/prefill/wmma_gemm.cu:31-57,480-485,653-663,710-724` — build/device guard、fused GEMM、範囲判定、非対応ビルド fallback。
- `sycl/src/prefill/prefill.cpp:264-270,2813-2833` — SYCL 側の同じ env 判定と prefill 分岐。SYCL は `src/prefill/wmma_gemm.h` の stub を include (`sycl/src/prefill/prefill.cpp:11`)。
