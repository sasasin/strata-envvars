# `STRATA_WS_FAST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の weight-stationary prefill 経路で、IQ4_NL down の 32-token tier を別の CUDA kernel に切り替えます。この変数だけでは weight-stationary 経路は有効になりません。ビルドと実行時の前提を満たした上で、その経路に入る層のうち IQ4_NL down、かつ routed expert あたりの行数 `u >= 20` の場合に限り切り替わります。通常 kernel と同じ Dm（down の出力）を作る設計です。

## 値と判定

実装は `std::atoi()` の戻り値がちょうど `1` かを判定します。文字列全体の検証はしません。

| 環境変数の値 | `fast()` の結果 |
|---|---:|
| 未設定 | 0 |
| 空文字、数値に変換できない文字列（例 `true`） | 0 |
| 先頭の整数変換結果が `1`（例 `1`, `01`, `+1`, ` 1`, `1tail`, `1.0`） | 1 |
| 変換結果が `1` 以外（例 `0`, `2`, `-1`, ` 0`） | 0 |

`atoi` は先頭の空白と符号を許し、数字列より後ろの文字列を検査しません。そのため `1tail` は有効ですが、`true` は無効です。境界値としての範囲検査や fallback はありません。ベンチ・テスト用 API `set_fast(v)` が 0 以上の値を設定すると環境変数より優先され、0 以外は 1 に正規化されます。`v < 0` は override を解除して環境値に戻します。通常の CLI 引数による上書きはありません。

根拠: `src/prefill/moe_ws.cu:75-89`。

## 有効になる条件

以下の条件が揃わないと、`STRATA_WS_FAST=1` でも対象 kernel は実行されません。

- `STRATA_EXPERIMENTAL_SM60` 有効の CUDA build で、weight-stationary kernel 群がコンパイルされている。HIP はこの経路の対象外です。通常 build では `prefill.cpp` の stub が `mode() == 0` を返します（`CMakeLists.txt:2135-2159`, `src/prefill/prefill.cpp:131-140`）。
- `STRATA_MMQ_WS` が設定され、`atoi` 結果が `1` であり、可視 CUDA device が 1 台以上あって、そのすべての compute capability が 6.0 である。device 列挙に失敗した場合や該当しない device がある場合は mode が無効になります。`STRATA_MMQ_WS` の判定も初回に cache されます（`src/prefill/moe_ws.cu:51-73`）。
- prefill の対象層が weight-stationary の条件を満たすこと。コード上は native layer、対応 gate/up と down の形式、両製品がその行数で per-group MMQ より速いという判定、全 routed expert が VRAM resident、単一 GPU 上で peer/CPU/streaming 分がないこと、さらに debug NaN、直接 MMQ、fused layout、Hadamard、FP4、tail などの除外条件を要求します（`src/prefill/prefill.cpp:4722-4750`）。
- down 形式が IQ4_NL であること。Q2_0 down は `STRATA_WS_FAST` を参照せず、IQ4_NL でも `u < 20` は通常 kernel のままです（`src/prefill/moe_ws.cu:140-157`, `src/prefill/moe_ws_down.cu:623-642`）。

## 実行時の詳細

環境値は起動時には読まず、`ws::down()` が IQ4_NL down を処理するときに `fast()` が初めて必要になった時点で読みます。読み取り結果は関数内の `static const int` に保存されるため、その後プロセス内で環境値を変更しても再評価されません。override API が使われている間はそちらが優先されます（`src/prefill/moe_ws.cu:75-89`, `src/prefill/moe_ws.cu:140-157`）。

対象層の down は `ws::down()` から呼ばれ、`IQ4_NL` の `u >= 20` で値が 1 なら `dn_kernel_fast<256, 32, 2, 2>`、そうでなければ `dn_kernel<256, 32, 2, 2>` を起動します。`u < 5` は 128 行×8 token、`5 <= u < 20` は 256 行×16 token の通常 kernel です（`src/prefill/moe_ws_down.cu:623-642`）。高速 kernel は通常 kernel と同じ token ごとの演算順で同じ Dm bits を保つ実装意図が記されています（`src/prefill/moe_ws_down.cu:438-445`）。

`fast()` が 1 で IQ4_NL down に到達すると、プロセス内で一度 stderr に `strata prefill: STRATA_WS_FAST=1: the weight-stationary IQ4_NL down's 32-token tier with switched token pairs and transposed dy (the same Dm bits)` を出します。このログは `u < 20` でも出るため、ログだけでは fast kernel が選ばれたことを意味しません。down kernel の起動エラーは `prefill ws: down IQ4_NL: <CUDA error>` を stderr に出して `exit(1)` します（`src/prefill/moe_ws.cu:146-157`, `src/prefill/moe_ws_down.cu:23-28,635-642`）。

## 根拠

- 候補一覧に名前があります: `docs/envvars/000_envvers.md:1659`。実際の環境読み取りは `src/prefill/moe_ws.cu:82-85` です。
- CUDA 実験 build だけが kernel 群を含みます: `CMakeLists.txt:2135-2159`。
- weight-stationary 経路を選ぶ条件と resident 判定: `src/prefill/prefill.cpp:4722-4750`。その層の gate/up、SwiGLU、down の呼び出し順: `src/prefill/prefill.cpp:5404-5417`。
- `STRATA_MMQ_WS` による GPU 条件: `src/prefill/moe_ws.cu:51-73`。
- kernel の tier 選択: `src/prefill/moe_ws_down.cu:623-642`。
- Strata の設計資料は `docs/OLDER_GPUS.md:186-196` に、実験 build・resident 条件と同じ bits である旨、および組み合わせ経路の測定を記載しています。これは `STRATA_MMQ_WS` と weight-stationary 経路全体の記載であり、`STRATA_WS_FAST` 単独の性能測定値としては扱っていません。
