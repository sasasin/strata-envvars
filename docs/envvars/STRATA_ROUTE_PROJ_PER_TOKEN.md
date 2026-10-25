# `STRATA_ROUTE_PROJ_PER_TOKEN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

verify window 内で複数 token の router projection をまとめて計算する経路について、BF16 router weight × FP32 activation の投影部分だけを token ごとの GEMV 呼び出しに分けます。router top-k は引き続き window 全体をまとめて1回呼びます。

この環境変数は通常の1 token の routing や他の projection には使われません。`moe_route_window()` のバッチ経路でのみ参照されます。CUDA/HIP 実装と SYCL 側に同じ判定があります。

## 値と判定

文字列や数値への変換はありません。`std::getenv()` の結果が null かどうかだけを調べるため、未設定なら OFF、設定されていれば値を問わず ON です。`1` 以外の文字列や空文字も ON になります。

| 状態 | 投影処理 |
|---|---|
| unset | `bf16_gemv_fp32_mmvf_cols()` で複数 token をまとめて処理 |
| 設定あり（`1`、`0`、空文字など） | token ごとに `bf16_gemv_fp32_mmvf()` を呼ぶ |

判定は `moe_route_window()` が呼ばれるたびに行われ、関数内 static cache はありません。したがってプロセス内で環境値を変更できる場合は、次の呼び出しに反映されます。

根拠: `src/core/layer.cpp:395-418`, `sycl/src/core/layer.cpp:456-479`。

## 有効になる条件

環境変数が設定されていても、次の経路に入らなければ効果はありません。

- verify が decode batch として複数 token（`n > 1`）を処理し、`moe_route_window()` を呼ぶこと。
- native BF16 projection が有効であること。無効ならバッチ経路を選ばず、各 token を `moe_route()` で処理する。
- `STRATA_ROUTE_PER_TOKEN` が未設定であること。この変数が設定されていると `moe_route_window()` は最初から per-token の `moe_route()` に分岐し、本変数の判定位置に到達しない。
- 呼び出し元のビルド条件・router 経路が `moe_route_window()` に到達すること。現在の verify 呼び出しは `STRATA_HIP_GFX906` 条件内にあり、通常の 512 expert / top-10 native-router 経路はその前の分岐で処理される。SYCL の verify は native router が 256 expert / top-10 を処理する場合も先行分岐する。

`n == 1` も token ごとの `moe_route()` に分岐するため、本変数による差はありません。`STRATA_ROUTE_PER_TOKEN` は projection の選び方だけでなく `moe_route()` 全体を token ごとに呼び、top-k も token ごとに実行します。本変数はバッチ top-k を維持します。

根拠: `src/core/verify.cpp:1438-1458`, `sycl/src/core/verify.cpp:1309-1329`, `src/core/layer.cpp:398-417`, `sycl/src/core/layer.cpp:459-478`。

## 実行時の詳細

バッチ経路で本変数が設定されていれば、`x + t * n_embd` と対応する logits 領域を使い、各 token について `bf16_gemv_fp32_mmvf()` を順に enqueue します。未設定時は `bf16_gemv_fp32_mmvf_cols()` を使い、最大8 tokenずつ multi-row GEMV を実行します。いずれもその後に `router_top10()` を window の `n` token 分まとめて呼びます。

カーネル API の説明では、複数列版の各出力は単独 GEMV の出力と bitwise equal とされています。従ってこのスイッチが変えるのは projection の起動のまとめ方であり、top-k の対象 token 数や router 計算の後段ではありません。

この変数専用のログ出力やエラー分岐は見つかりませんでした。`docs/AMD_HIP.md` は gfx906 の verify-window routing と別変数 `STRATA_ROUTE_PER_TOKEN=1` の per-token 経路に触れていますが、本変数単独の挙動や測定値は記載していません。その資料の約3 ms / 約55 ms という値を本変数の効果としては扱えません。

根拠: `src/core/layer.cpp:411-418`, `sycl/src/core/layer.cpp:472-479`, `include/strata/kernels/bf16_gemv.hpp:45-54`, `src/kernels/cuda/native_bf16.cu:371-380`, `sycl/src/kernels/cuda/native_bf16.dp.cpp:932-941`, `docs/AMD_HIP.md:500-513`。
