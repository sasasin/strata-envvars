# `STRATA_PF_FUSED_SM75_KQ`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されなかった。

## 役割

CUDA の Turing（compute capability 7.5）で、Q4_K / Q5_K gate/up と Q5_1 down（セットアップできる場合は Q8_0 down も）の Strata native fused prefill kernels を登録するかを制御する診断用スイッチです。既定ではセットアップを試み、値の先頭が `0` なら試みません。無効にした場合、該当 K-quant ペアはこの経路でカバーされず、上位の経路選択に従って MMQ 等に残ります。CUDA 実装の `dev_info()` が判定し、`native_supported()` と `experts_native()` がセットアップ済みカーネルを選択・起動します（`engine/src/prefill/moe_fused_iq.cu:2847-2848,2913-2926,3415-3432,3495-3499,3886-3900`）。

## 値と判定

`dev_info()` 内の関数ローカル `static const bool` 初期化で `std::getenv` を一度読み、未設定でなく先頭文字が `'0'` の場合だけ無効になります。空文字は設定されていても先頭が終端 NUL なので無効化しません。文字列全体の解析、数値変換、空白除去、大文字小文字変換はありません（`engine/src/prefill/moe_fused_iq.cu:2918-2919`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA の Turing K-quant setup 判定 | セットアップを許可 | `1`, `true`, ` 0`, 空文字, `2` | `0`, `00`, `0anything` |
| HIP build または Turing 以外の CUDA device | この変数の判定箇所に到達しない | 該当なし | 該当なし |

表の「有効」はこのスイッチ単体がセットアップを禁止しない意味です。Turing 系の `dev_info()` 分岐に入るには、`STRATA_PF_FUSED_SM75` が先頭 `'1'` である必要があります。また K-quant kernels のセットアップには別途 `STRATA_PF_FUSED_KQ` の先頭が `'1'` であることが必要です（`engine/src/prefill/moe_fused_iq.cu:2899-2901,2918-2922`）。

## 有効になる条件

- CUDA backend であること。この K-quant native-kernel setup と dispatch は `!defined(__HIPCC__)` 側にあります。HIP の `dev_info()` は HIP 分岐で先に return し、この変数を読まず、SYCL はこの CUDA source を使いません（`engine/src/prefill/moe_fused_iq.cu:2854-2886,2918-2926,3222-3229,3873-3900`; `engine/cmake/backends/cuda.cmake:135-152`; `engine/cmake/backends/hip.cmake:30-38`; `engine/sycl/src/prefill/moe_fused_stub.cpp:1`）。
- device が Turing / compute capability 7.5 で、`STRATA_PF_FUSED_SM75` が先頭 `'1'` であること。未設定または先頭が `'1'` 以外なら Turing 用 fused setup に入らず、この変数も読みません（`engine/src/prefill/moe_fused_iq.cu:2899-2902`）。
- `dev_info()` の共通 Q2_0 setup が成功し `d.ok` が true であること。そうでなければ K-quant setup 条件は実行されません（`engine/src/prefill/moe_fused_iq.cu:2903-2905,2919`）。
- `STRATA_PF_FUSED_KQ` が設定され、先頭文字が `'1'` であること。条件が満たされると Q4_K / Q5_K の gate/up と Q5_1 down の WW=2 kernel setup をすべて試し、全て成功した場合に `d.kq=true` にします。Q8_0 down setup はこの KQ setup 成功の後に独立して試みます（`engine/src/prefill/moe_fused_iq.cu:2920-2925`）。
- 実際のレイヤー選択では `STRATA_PF_FUSED_NATIVE=0`、`STRATA_PF_FUSED=0`、または小カード向け override が fused native path を止めないこと。加えて gate/up が Q4_K / Q5_K、down が Q5_1（または `d.kq8` が立った場合の Q8_0）で、通常 fused path が選ばれる必要があります（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3495-3499`）。
- `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-56` と `engine/src/prefill/prefill.cpp:223-255` により、MMQ を含まない CUDA build では `STRATA_PF_FUSED_KQ` が未設定なら起動前に `1` を設定します（利用者が設定済みならその値を保持）。この一覧に `STRATA_PF_FUSED_SM75_KQ` 自体はないため、この変数の既定は引き続きコード上の「先頭が `0` でなければ許可」です。

## 実行時の詳細

読み取りは通常の CUDA `dev_info()` 初期化で Turing branch に入った時だけ行われます。環境値は関数ローカル static に保存されるため、そのプロセスで最初にこの判定に到達した後の環境変更は反映されません。device 情報も `g_dev[dev & 31]` に device ごとに cache されます。`moe_fused_iq_q36.cu` は同じ `.cu` を別 namespace で再コンパイルするため、通常形状用と Qwen3.6 形状用にはそれぞれ独立した static 判定と device 情報があります（`engine/src/prefill/moe_fused_iq.cu:2690-2691,2847-2853,2918`; `engine/src/prefill/moe_fused_iq_q36.cu:1-6,33-38`）。

変数が無効なら `d.kq` を立てる K-quant setup ブロックを丸ごと飛ばします。値が許可しても setup API が失敗した場合は `d.kq` が false のままで、`native_supported()` は対象ペアを native 対応とせず、K-quant dispatch には進みません。setup の失敗に対するこの分岐固有のログはありません。選択された K-quant native kernel の launch 後に CUDA エラーがあれば `ck(..., "experts_native")` が `prefill fused experts (native): experts_native: <CUDA error>` を stderr に出して `exit(1)` します（`engine/src/prefill/moe_fused_iq.cu:2920-2925,3495-3499,3886-3900,68-72`）。

レイヤーがこの fused 経路に選ばれなければ、この変数だけを理由とする警告や終了はありません。MMQ の有無などに応じて別の既存経路が使われます。この環境変数に対応する CLI 引数・設定ファイル値は、調査対象ソースで確認できません。

## ログと測定値

この変数の判定・無効化・setup 成功を直接知らせるログはありません。setup 不成立時は状態フラグが立たず、後段の経路選択から外れます。`docs/DETAILS.md` の Turing 節は sm_75 kernels を opt-in と説明しますが、この K-quant switch 固有の測定値は載せていません。ソースコメントには RTX 2080 Ti の一層での過去の測定条件・比率が記されていますが、再測定した結果や一般的な性能保証としては扱いません（`engine/src/prefill/moe_fused_iq.cu:2913-2918`; `docs/DETAILS.md:1314-1324`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:2847-2853,2887-2926` — device/backend 分岐、Turing opt-in、対象変数の読み取り、KQ setup。
- `engine/src/prefill/moe_fused_iq.cu:3415-3432,3495-3499,3886-3900` — native path の共通条件、K-quant pair 選択と launch。
- `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-56`、`engine/src/prefill/prefill.cpp:223-255` — MMQ なし build における関連 switch の起動時既定値設定。
- `engine/src/prefill/moe_fused_iq_q36.cu:1-6,33-38` — Qwen3.6 用の別 namespace / 別コンパイル単位。
- `engine/cmake/backends/cuda.cmake:135-152`、`engine/cmake/backends/hip.cmake:30-38`、`engine/sycl/src/prefill/moe_fused_stub.cpp:1` — backend とソースの構成。
