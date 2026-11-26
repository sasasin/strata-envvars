# `STRATA_ROUTE_PROJ_PER_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

検証ウィンドウ内の複数 token をまとめて MoE router に通すとき、router の BF16 重み投影だけを token ごとの `bf16_gemv_fp32_mmvf` 呼び出しに分ける。変数が未設定なら `bf16_gemv_fp32_mmvf_cols` で全 token の列をまとめて投影する。どちらの分岐でも、その後の `router_top10` はウィンドウ全体に対して呼ばれるため、この変数は top-k の実行単位を token ごとに変えない（CUDA/HIP 系: `engine/src/core/layer.cpp:443-466`、SYCL 系: `engine/sycl/src/core/layer.cpp:456-479`）。

## 値と判定

両実装とも `std::getenv(...)` の null 判定のみで、文字列の変換・比較はしない。未設定なら列まとめ投影、何らかの値が設定されていれば token ごとの投影となる。したがって空文字、`0`、`false`、`1`、任意の文字列はいずれも設定ありとして扱われる。空白や大文字小文字、数値としての妥当性も検証しない。分岐は `moe_route_window` 呼び出しごとに評価し、関数内の static cache はない。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP 系または SYCL 系で `moe_route_window` のまとめ投影分岐に入る場合 | 列まとめ投影 `bf16_gemv_fp32_mmvf_cols` | 空文字、`0`、`false`、`1`、その他の設定値で token ごとの投影 | 該当なし（値の内容による無効判定なし） |
| まとめ投影分岐に入らない場合（後述） | この変数を読まず、通常の `moe_route` 経路 | 効果なし | 効果なし |

根拠: `engine/src/core/layer.cpp:459-465`、`engine/sycl/src/core/layer.cpp:472-478`。

## 有効になる条件

- 呼び出し元が検証ウィンドウをまとめて処理する経路を選ぶ必要がある。CUDA/HIP 系では `dec_batch && route_window_on()` が必要（`engine/src/core/verify.cpp:2647-2654`）。`STRATA_DEC_BATCH` は unset なら有効、設定時は `atoi` の結果が 0 だと無効（例: 空文字、`0`、数字で始まらない文字列）、非ゼロなら有効（例: `1`、`-1`、`1tail`）で、値は verifier 内の static に初回評価結果が保存される（同 `1489`）。
- CUDA/HIP 系の `route_window_on()` は `STRATA_HIP_GFX906` build では `STRATA_ROUTE_WIN` unset または先頭文字が `'0'` 以外で有効、他の build では `STRATA_ROUTE_WIN` の先頭文字が `'1'` のときだけ有効。これも static に一度評価される（`engine/src/core/verify.cpp:305-319`）。
- `native_bf16_projections` が有効である必要がある。初期値は false で、CLI の `--native-bf16` または `--native` の preset 経路がこれを有効にし、`layer_set_native_bf16` へ設定を渡す（`engine/src/core/layer.cpp:100`、`engine/src/program/generate.cpp:3914`, `5160-5164`, `6114`）。SYCL 版の同名状態も初期値 false である（`engine/sycl/src/core/layer.cpp:96`）。
- ウィンドウ内 token 数 `n` が 1 より大きくなければならない。`n == 1` は通常の per-token `moe_route` に戻る（CUDA/HIP 系: `engine/src/core/layer.cpp:446-454`、SYCL 系: `engine/sycl/src/core/layer.cpp:459-467`）。
- `STRATA_ROUTE_PER_TOKEN` が設定されていない必要がある。この別変数は値ではなく設定有無でまとめ投影を止めるため、空文字や `0` でもこの文書の変数に到達しない（同上）。
- native router が有効で、expert 数が 512、`k == 10` の場合は `moe_route_window` のまとめ投影対象外。CUDA/HIP 系 verifier は native router 経路を先に選び（`engine/src/core/verify.cpp:2636-2646`）、SYCL verifier も 512 または 256 expert の native multi-router 経路を先に選ぶ（`engine/sycl/src/core/verify.cpp:1583-1593`）。SYCL verifier から `moe_route_window` を呼ぶ箇所は `STRATA_HIP_GFX906` build の条件付きである（同 `1594-1602`）。
- router 重み `ffn_gate_inp.weight` がモデルに存在する必要がある。欠落時は環境変数を判定する前に `err` を設定して false を返す（CUDA/HIP 系: `engine/src/core/layer.cpp:456-459`、SYCL 系: `engine/sycl/src/core/layer.cpp:469-472`）。

この変数を有効にしても router の重み、router の数学的定義、top-k の呼び出し単位は変えない。projection kernel の呼び出し形だけを変える分岐であり、ソースコメントは個々の token の算術が single-token 呼び出しと同じと説明している（`engine/src/core/verify.cpp:2629-2630`, `2648-2653`）。

## 実行時の詳細

`moe_route_window` は native BF16 projection が有効で、native router の除外条件に当たらず、`STRATA_ROUTE_PER_TOKEN` も設定されていない場合に、まとめ投影可能な経路として動く。その経路で `STRATA_ROUTE_PROJ_PER_TOKEN` が設定されていれば、`t = 0..n-1` について入力 `x + t * g.n_embd` から logits `logits + t * g.n_expert` へ `bf16_gemv_fp32_mmvf` を呼ぶ。未設定時は `bf16_gemv_fp32_mmvf_cols` を一度呼ぶ。いずれもその後に `router_top10(logits, n, ...)` を一度呼ぶ（CUDA/HIP 系: `engine/src/core/layer.cpp:443-466`、SYCL 系: `engine/sycl/src/core/layer.cpp:456-479`）。

環境変数を読むのはこの分岐が選ばれた後であり、通常の per-token fallback や `n == 1` では読み取られない。対象分岐は verifier が処理する各 MoE layer/window の `moe_route_window` 呼び出し時に判定される。ソース内にこの変数専用の CLI 引数、他の設定値による値の上書き、起動時 cache、ログ出力はない。プロセス内で環境を変更した場合、次の対象関数呼び出しで再評価される。

## ログと測定値

この変数を読む箇所に専用ログや警告、終了処理はない。欠落 router 重みは通常のエラー戻り値経路となるが、この環境変数固有の失敗ではない（`engine/src/core/layer.cpp:456-459`、`engine/sycl/src/core/layer.cpp:469-472`）。対象変数の効果を定量化した測定値は、確認した Strata ソース・関連資料には見当たらないため記載しない。

## 根拠

- 全参照と値判定: `engine/src/core/layer.cpp:459-465`、`engine/sycl/src/core/layer.cpp:472-478`。
- 呼び出し元・backend 条件: `engine/src/core/verify.cpp:305-319`, `2636-2654`、`engine/sycl/src/core/verify.cpp:1583-1602`。
- native BF16 の既定と CLI 設定: `engine/src/core/layer.cpp:100`, `202`、`engine/src/program/generate.cpp:3914`, `5160-5164`, `6114`、SYCL 既定: `engine/sycl/src/core/layer.cpp:96`, `179`。
