# `STRATA_ROUTE_PER_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_ROUTE_PER_TOKEN` が設定されていると、対応する MoE verify-window の router 計算を、複数 token をまとめる経路から token ごとの `moe_route` 呼び出しへ切り替える。router projection と top-k の計算方法・出力を変える専用値のパーサーではなく、環境変数の存在だけを見る切替である。設定値が空文字でも切替は有効になる。CUDA/HIP 共通実装と SYCL 実装の `moe_route_window` に読み取りがある（`engine/src/core/layer.cpp:443-452`、`engine/sycl/src/core/layer.cpp:456-465`）。

この変数によるログ出力や警告はない。切替先の `moe_route` が失敗した場合は、通常の router エラー経路が使われる。

## 値と判定

`std::getenv` の戻り値を `!` で判定し、文字列の変換・比較はしない。したがって unset の場合だけバッチ経路を許し、設定値が存在すれば値を問わず per-token 経路へ進む。空文字、`0`、`false`、大文字の値、空白付きの値もすべて「設定あり」である。無効値という区分や数値境界はない（`engine/src/core/layer.cpp:446-448`、`engine/sycl/src/core/layer.cpp:459-465`）。

| 条件 | unset | 設定時に有効になる値 | 判定されない値の違い |
|---|---|---|---|
| `engine/src/core/layer.cpp` / `engine/sycl/src/core/layer.cpp` | 他の条件が満たされれば window バッチを許可 | 値を問わず全て。例: 空文字、`0`、`1`、`false` | なし。値を parse せず、存在だけを見る |

`docs/SETTINGS.md:300` は値を `on / off` と整理し、`docs/AMD_HIP.md:605` は `=1` を例示するが、実装は `1` との文字列比較をせず設定有無だけを見る。従って `=1` は有効値の一例であり、唯一の有効値ではない。

## 有効になる条件

- 呼び出し元が `moe_route_window` に入る必要がある。CUDA/HIP 共通の verify では `STRATA_DEC_BATCH` が有効で `route_window_on()` が true の分岐で呼ばれる。`STRATA_DEC_BATCH` は unset なら有効、設定時は `atoi(value) != 0` で判定され、空文字や数値に変換できない文字列は無効になる（`engine/src/core/verify.cpp:305-319,1489,2647-2655`）。`route_window_on()` は `STRATA_ROUTE_WIN` を初回評価時にキャッシュし、`STRATA_HIP_GFX906` ビルドでは unset または先頭文字が `0` 以外なら有効、それ以外のビルドでは先頭文字が `1` のときだけ有効（`engine/src/core/verify.cpp:309-318`）。
- SYCL verify の呼び出しは `STRATA_HIP_GFX906` のビルド分岐にあり、`STRATA_DEC_BATCH` が有効で、先行する native-router 分岐に入らないとき `moe_route_window` を呼ぶ。先行分岐は `native_router_enabled()`、expert 数 512 または 256、`K == 10` を条件とする（`engine/sycl/src/core/verify.cpp:1048,1583-1602`）。この呼び出し分岐には `STRATA_ROUTE_WIN` の判定はない。
- `moe_route_window` 内でバッチ経路になるには `native_bf16_projections` が有効である必要がある。これは generate 側が `o.native_bf16` を `layer_set_native_bf16` に渡して設定する状態（`engine/src/program/generate.cpp:6114`、`engine/sycl/src/program/generate.cpp:3229`）。無効なら、この環境変数が unset でも per-token 経路になる。
- `native_router_enabled()` かつ 512 experts、`k == 10` の組み合わせもバッチ経路から除外され、`moe_route` を使う。CUDA/HIP 側の verify はその組み合わせを先行する native-router 分岐で処理する（`engine/src/core/layer.cpp:446-452`、`engine/src/core/verify.cpp:2636-2647`）。SYCL の `moe_route` は native router を 256 experts、`k == 10` にも使うが、`moe_route_window` の除外条件は 512 experts のみである（`engine/sycl/src/core/layer.cpp:414-417,459-465`）。ただし通常の SYCL verify 呼び出しでは 256-expert の native-router 分岐も先行するため、`moe_route_window` には入らない（`engine/sycl/src/core/verify.cpp:1583-1599`）。
- `n == 1` の window は、環境変数と他条件にかかわらず per-token の `moe_route` を使う（`engine/src/core/layer.cpp:448-454`、`engine/sycl/src/core/layer.cpp:461-467`）。

## 実行時の詳細

CUDA/HIP 共通側と SYCL 側の `moe_route_window` は、各呼び出しで `STRATA_ROUTE_PER_TOKEN` を読み直す。関数内に static cache はなく、プロセス起動時に一度だけ読むコードでもない。存在すれば `n` 個の token を順に処理し、それぞれの logits / ids / weights の領域を `MoEBuffers` に割り当てて `moe_route` を呼ぶ。unset かつ他の条件が揃う場合は、router の BF16 projection と top-k を window 単位で処理する（`engine/src/core/layer.cpp:443-466`、`engine/sycl/src/core/layer.cpp:456-479`）。

per-token 経路では `moe_route` が個別 token の router projection と top-k を実行する。CUDA/HIP 共通側の top-k は、native router が有効かつ 512 experts / k=10 のとき native router、それ以外は `router_top10` を使う（`engine/src/core/layer.cpp:418-423`）。SYCL 側は native router が有効かつ 512 または 256 experts / k=10 のとき `native_router_top10_multi_ne`、それ以外は `router_top10` を使う（`engine/sycl/src/core/layer.cpp:412-417`）。

バッチ経路でのみ参照される別変数 `STRATA_ROUTE_PROJ_PER_TOKEN` が設定されていれば、router projection だけを token ごとの `bf16_gemv_fp32_mmvf` で行い、top-k は引き続きまとめて行う。未設定なら複数列の `bf16_gemv_fp32_mmvf_cols` を使う。この別変数は `STRATA_ROUTE_PER_TOKEN` が設定されて per-token 分岐に入った場合には参照されない（`engine/src/core/layer.cpp:456-465`、`engine/sycl/src/core/layer.cpp:469-479`）。

## ログと測定値

`STRATA_ROUTE_PER_TOKEN` 固有のログ、警告、終了処理はない。`moe_route` 内で router weight がない場合は `ffn_gate_inp.weight is missing` 相当のレイヤー名付きエラーを返す。native router が例外を投げた場合は `router: ` に例外文字列を付けたエラーを返す（`engine/src/core/layer.cpp:405-423`、`engine/sycl/src/core/layer.cpp:401-417`）。verify の呼び出し元は失敗時に `false` を返す（`engine/src/core/verify.cpp:2653-2655`、`engine/sycl/src/core/verify.cpp:1599-1601`）。

## 根拠

- 読み取り・分岐・バッチ処理: `engine/src/core/layer.cpp:443-466`、`engine/sycl/src/core/layer.cpp:456-479`
- verify 側の呼び出し条件: `engine/src/core/verify.cpp:305-319,1489,2636-2660`、`engine/sycl/src/core/verify.cpp:1048,1583-1607`
- per-token router の top-k 分岐: `engine/src/core/layer.cpp:418-423`、`engine/sycl/src/core/layer.cpp:412-417`
- `native_bf16_projections` の設定箇所: `engine/src/program/generate.cpp:6114`、`engine/sycl/src/program/generate.cpp:3229`
