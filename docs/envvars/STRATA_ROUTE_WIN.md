# `STRATA_ROUTE_WIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

speculative decoding の verify window で、通常は token ごとに実行する非 native MoE router を window 全体でまとめて処理するかを選ぶ。`engine/src/core/verify.cpp` の `route_window_on()` がこの変数を判定し、`Verify::step` の router 分岐で使用する。対象は router の計算方法であり、後段の expert 選択結果や生成 token を変える設定としては実装されていない。window 経路のコメントは token ごとの処理と bitwise 同一と説明している（`engine/src/core/verify.cpp:305-319,2647-2654`）。

この変数を読むのは `engine/src/core/verify.cpp` のみ。SYCL 側の `engine/sycl/src/core/verify.cpp` は `STRATA_ROUTE_WIN` を読まず、gfx906 macro の場合に `dec_batch` だけで window router を呼ぶ別実装である（`engine/sycl/src/core/verify.cpp:1583-1608`）。

## 値と判定

`std::getenv` の戻り値を、ビルド時の `STRATA_HIP_GFX906` macro に応じて先頭 1 文字だけで判定する。文字列全体の parse、空白除去、大文字小文字変換、数値変換はしない。`route_window_on()` 内の `static const bool` に初回評価結果を保存する（`engine/src/core/verify.cpp:309-319`）。

| 条件（build macro） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_HIP_GFX906` 定義あり | ON | 空文字、`1`、`true`、`abc`（先頭が `0` 以外） | `0`、`0anything`（先頭が `0`） |
| `STRATA_HIP_GFX906` 定義なし | OFF | `1`、`10`、`1anything`（先頭が `1`） | 空文字、`0`、`true`、` 1`、`01` |

したがって gfx906 分岐では明示的な空文字も ON、先頭が `0` の任意の値は OFF。それ以外の分岐では先頭が `1` の場合だけ ON で、空文字や `true` は OFF。たとえば gfx906 で `true` は ON、その他の build で `true` は OFF となる（`engine/src/core/verify.cpp:311-316`）。

## 有効になる条件

- `STRATA_HIP_GFX906` macro の有無で既定値と判定規則が分かれる。CMake は `STRATA_HIP_GFX906` を gfx906 compatibility build の選択肢として定義し、HIP backend の設定で同名 compile definition を付ける（`engine/CMakeLists.txt:97-100`, `engine/cmake/backends/hip.cmake:16-22`）。
- Verify の router 処理に到達し、`STRATA_DEC_BATCH` が有効であること。`dec_batch` は `std::atoi` の結果が 0 以外かを関数内 `static` に一度だけ保存し、未設定なら ON。`STRATA_DEC_BATCH=0`、空文字、数値に変換できない文字列などは OFF となり、token ごとの router ループを使う（`engine/src/core/verify.cpp:1489`, `2636-2661`）。
- `dec_batch` が ON でも、`dec_batch && n > 1 && w_router != nullptr && native_router_enabled() && NE == 512 && K == 10` の native router 分岐が先に選ばれる場合、この設定の分岐には入らない（`engine/src/core/verify.cpp:2631-2648`）。
- `route_window_on()` が ON でも、`moe_route_window()` は native BF16 projection が無効、または `STRATA_ROUTE_PER_TOKEN` が設定済みなら token ごとの `moe_route()` に戻る。また `n == 1` も token ごとに処理する。`STRATA_ROUTE_PER_TOKEN` は値ではなく設定有無の判定なので、空文字や `0` でも fallback する（`engine/src/core/layer.cpp:443-454`）。
- `STRATA_ROUTE_PROJ_PER_TOKEN` が設定されている場合は projection のみ token ごとに実行するが、top-k は window 分をまとめて処理する。これも設定有無で判定され、空文字や `0` も設定ありとなる（`engine/src/core/layer.cpp:456-465`）。
- 該当箇所は verify の GPU router 実装であり、CLI 引数や設定ファイルからこの値を読む処理は確認できなかった。SYCL verify 実装はこの変数による切替を行わない（`engine/sycl/src/core/verify.cpp:1583-1608`）。

## 実行時の詳細

`route_window_on()` は最初に呼ばれた時に環境変数を読み、その結果を `static` に保持する。以後の verify window や実行中の環境変更では再読込しない（`engine/src/core/verify.cpp:309-319`）。同関数は `dec_batch` が ON の router 分岐で呼ばれる（`engine/src/core/verify.cpp:2636-2654`）。

この切替が有効で native router 分岐に該当しないとき、window 全体の BF16 router projection と top-k を `moe_route_window()` に依頼する。そこで `STRATA_ROUTE_PER_TOKEN` などの fallback 条件を満たす場合には token ごとの `moe_route()` を呼ぶ。batch path は `ffn_gate_inp.weight` が無ければ `"<tensor-name> is missing"` を `err` に設定して失敗を返し、呼び出し元も false を返す。成功時には verify の後続 router/expert 処理へ進む（`engine/src/core/layer.cpp:443-466`, `engine/src/core/verify.cpp:2647-2661`）。

## ログと測定値

`STRATA_ROUTE_WIN` の値や window routing の採用を直接表示する専用ログは、この分岐にはない。verify router の後には `router layer: batched native router=..., shared-expert gate in the router launch=..., route_prior=...` というログがあるが、`STRATA_ROUTE_WIN` や `moe_route_window()` の採用状態は表示しない（`engine/src/core/verify.cpp:2662-2663`）。batch path で router weight が欠落した場合は `err` に tensor 名付きの missing エラーを設定して false を返す（`engine/src/core/layer.cpp:456-459`）。

ソースコメントには過去の測定として、gfx906 の 2x MI50 で約 55 ms の verify window 中 router 約 3 ms、gfx1201 の R9700・Coder IQ1_M・`--spec 4` で window routing が 3.34 ms から 1.39 ms、decode +9% とある。前者にはモデル等の条件が記されていない。後者もコメントに記された条件下の値であり、この調査で再測定していない。実装コメントは token ごとの routing と bitwise 同一とも記載している（`engine/src/core/verify.cpp:305-308,2650-2652`）。`docs/DETAILS.md` に `STRATA_ROUTE_WIN` または route-window の説明は見つからなかった。

## 根拠

- `engine/src/core/verify.cpp:305-319` — 設定の意図、build macro ごとの値判定、static cache。
- `engine/src/core/verify.cpp:1489,2631-2663` — `STRATA_DEC_BATCH`、router 分岐の優先順位、window route 呼び出し。
- `engine/src/core/layer.cpp:443-466` — native BF16 条件、per-token fallback、projection と top-k の実行。
- `engine/sycl/src/core/verify.cpp:1583-1608`, `engine/sycl/src/core/layer.cpp:456-466` — SYCL の別経路。
- `engine/CMakeLists.txt:97-100`, `engine/cmake/backends/hip.cmake:16-22` — gfx906 build macro の設定。
