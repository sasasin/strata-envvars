# `STRATA_ROUTE_PER_TOKEN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

HIP gfx906 の decode verify window で複数 token の MoE router をまとめて計算する経路を無効にし、token ごとの従来の `moe_route()` に切り替えます。ソース中の説明では、主な対象は256 expert の router です。この変数が変えるのは router の計算経路で、コード上は routing の値を意図的に変える設定ではありません。

## 値と判定

値の文字列は parse せず、`std::getenv()` が null かどうかだけで判定します。

| 環境変数の状態 | `batched` 判定への効果 |
|---|---|
| 未設定 | 他の条件を満たす場合、複数 token の batched routing を許可 |
| 設定あり（空文字を含む） | batched routing を無効化 |
| `0`、`1`、`false` など | いずれも設定ありとして batched routing を無効化 |

従って、文書の例 `STRATA_ROUTE_PER_TOKEN=1` だけでなく、空文字を含む任意の設定値で per-token 経路になります。数値変換、大小文字比較、無効値時の fallback はありません。

## 有効になる条件

この変数が経路を選択するのは、verify 側から `moe_route_window()` が呼ばれた場合です。呼び出しは `dec_batch` が有効な分岐のうち、HIP gfx906 用の `#if defined(STRATA_HIP_GFX906)` 節にあります。CUDA の 512 expert / top-10 native router 分岐が先に選ばれる場合は、この節へ進みません。SYCL 側にも同じ `moe_route_window()` 判定がありますが、verify 側の呼び出しも gfx906 compile guard 内です。

`moe_route_window()` 内で batched 経路を使うには、さらに `native_bf16_projections` が有効であることと、native 512-expert/top-10 router の除外条件に当たらないことが必要です。`STRATA_ROUTE_PER_TOKEN` が設定されていれば、これらの条件にかかわらず `batched` は false です。なお、呼び出し時の token 数 `n` が1なら、変数未設定でも per-token 経路になります。

関連する `STRATA_DEC_BATCH` は未設定なら有効、設定値を `atoi()` で変換して0以外なら有効です。これは verify の batched 分岐自体に入るかを決める別設定です。

## 実行時の詳細

`moe_route_window()` の呼び出しごとに `getenv()` を評価し、結果を static cache しません。したがって、関数呼び出し前にプロセス環境が変更されれば次の呼び出しで再評価されます（通常の実行でプロセス環境を変更する処理があるとは、ここでは確認していません）。設定あり、または他の条件により `batched` が false のときは、`t = 0..n-1` の各 token に対して `moe_route()` を呼びます。

未設定で batched が有効な場合は、router 重みが欠けていれば `... is missing` のエラーを返します。`STRATA_ROUTE_PROJ_PER_TOKEN` も設定されている場合は射影だけ token ごとの `bf16_gemv_fp32_mmvf()` を使い、未設定なら複数列の `bf16_gemv_fp32_mmvf_cols()` を使います。どちらの場合も、その後の top-10 は `router_top10()` でまとめて処理します。これらは `STRATA_ROUTE_PER_TOKEN` とは別の分岐です。

この環境変数専用のログ出力は実装にありません。`docs/AMD_HIP.md` は gfx906 の verify-window routing の切替例として `STRATA_ROUTE_PER_TOKEN=1` を挙げ、複数 token をまとめた射影と top-k を説明しています。verify ソースのコメントは、その batched 経路を per-token 呼び出しと bitwise 同等としています。これはソースと資料上の記述であり、この調査では性能や実行結果を測定していません。

## 根拠

- `src/core/layer.cpp:395-418` — `getenv()` による有無判定、batched 条件、per-token loop と batched projection/top-k。
- `sycl/src/core/layer.cpp:456-479` — SYCL 側の対応する判定と処理。
- `src/core/verify.cpp:845` — `STRATA_DEC_BATCH` の既定と変換。`src/core/verify.cpp:1438-1457` — native 512 router 分岐と gfx906 用 `moe_route_window()` 呼び出し。
- `sycl/src/core/verify.cpp:825,1309-1328` — SYCL 側の decode-batch 判定と呼び出し分岐。
- `docs/AMD_HIP.md:500-514` — gfx906 切替の説明と資料記載の検証方法。
