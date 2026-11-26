# `STRATA_ROUTE_PRIOR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA verify の MoE ルーティングで、GPU 上に常駐している expert の選択 logit に値 λ を加え、選ぶ top-10 を変えるための opt-in 設定です。選択後の重みは、補正前の router logit から計算した確率を選択済み top-10 上で正規化します。したがって expert の選択と生成結果は変わり得ますが、router が出した重みの元になる確率は補正しません。[`verify.cpp:2664-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`route_prior.cu:1-7, 39-47, 73-83`](../../../../Niko1221/Strata/engine/src/kernels/cuda/route_prior.cu)

未設定時の λ は GPU 種別・メモリ量・`STRATA_DEFAULTS=026` にかかわらず `0` です。実際の処理が走るのは、値が正で、expert 数 `NE == 512`、top-k `K == 10`、resident table `hits_.d_res` が存在する verify 経路です。通常の設定 UI は Qwen の CUDA、離散 NVIDIA GPU 13 GiB 以下の場合にだけ項目を表示しますが、これは UI の適用条件であり、engine の直接設定に対するカード容量の制限ではありません。[`sm120_series.hpp:117-125`](../../../../Niko1221/Strata/engine/include/strata/core/sm120_series.hpp)、[`verify.cpp:2668-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`speed_switches.py:49-51, 107-124`](../../../../Niko1221/Strata/terminal/strata_control/speed_switches.py)

## 値と判定

engine は `std::getenv` の結果を `std::atof` で float に変換します。環境変数が未設定なら既定値 `0`、設定されていても空文字なら `atof("") == 0` です。数値文字列全体の検証、許容範囲チェック、clamp、無効値エラーはありません。`atof` が先頭から数値として読める部分を変換するため、空白は数値変換規則に従い、後続文字は無視されます。数値として読めない文字列は `0` 相当になり、NaN や負値は `> 0` 判定を通りません。正の無限大は `> 0` 判定を通り、kernel 側にも λ の有限性検査はありません。[`sm120_series.hpp:122-126`](../../../../Niko1221/Strata/engine/include/strata/core/sm120_series.hpp)、[`verify.cpp:299-303, 2668-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| engine の値解決 | `0` | `1.5`, `0.5`, `2`, `1.5junk`（先頭の数値部分を変換）、`inf`（正の無限大） | 空文字、`0`, `-1`, `-inf`, `nan`, `true`, `junk`, `0anything`（変換結果が正でない） |

値に上限はなく、正の変換結果なら同じ分岐条件を通ります。値は変換後の `float` です。正の無限大も分岐を通り、kernel は resident の各 logit にその値を加算します（異常値の検査や fallback はありません）。`atof` による数値変換を行うため、文字列 `true`/`false` を真偽値として解釈することはありません。CLI 引数に同名の専用フラグはなく、`strata launch --set STRATA_ROUTE_PRIOR=1.5` または run config の `env` を使って文字列を渡します。serve は親プロセス環境をコピーした後に run config の `env` を適用するので、同じ名前があれば run config の値が親環境を上書きします。設定 UI の On は `1.5` を書き、Off はその項目を削除します。[`server.py:4007-4028`](../../../../Niko1221/Strata/terminal/serve/server.py)、[`speed_switches.py:49-51, 156-169`](../../../../Niko1221/Strata/terminal/strata_control/speed_switches.py)、[`DETAILS.md:1282`](../../../../Niko1221/Strata/docs/DETAILS.md)

## 有効になる条件

- CUDA engine の verify 実装が対象です。ルーティング kernel は `engine/src/kernels/cuda/route_prior.cu` にあり、CUDA engine の `strata_kernels` に含まれます。[`strata_gpu_engine.cmake:48-76`](../../../../Niko1221/Strata/engine/cmake/strata_gpu_engine.cmake)
- 変換後の値が `> 0` であること。未設定、空、0、負数、非数値文字列は実行分岐を通りません。[`verify.cpp:2668-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- 対象 MoE 層が `NE == 512`（512 experts）、`K == 10` であり、resident table `hits_.d_res` が存在すること。条件を満たさないモデル形状や table がない状態では値が正でも適用されません。[`verify.cpp:2668-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- router の top-10 を経る verify の MoE routing が必要です。この追加処理は `moe_route` / verify 窓の routing 後に ids と weights を差し替え、その後の resident plan / doorbell 処理へ渡されます。[`verify.cpp:2657-2670, 2686-2714`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- GPU 世代、離散/統合 GPU、容量、`STRATA_DEFAULTS=026` による既定値の切り替えはありません。明示値があればどのカードでもユーザー値が優先されると resolver のコメントと実装に記されています。[`sm120_series.hpp:105-107, 117-126`](../../../../Niko1221/Strata/engine/include/strata/core/sm120_series.hpp)
- Expert settings / Terminal の簡易スイッチは Qwen（config に `arch` がない形状）、CUDA backend、13 GiB 以下の NVIDIA GPU でのみ表示されます。そこから渡される値は `1.5` です。[`speed_switches.py:49-51, 107-124`](../../../../Niko1221/Strata/terminal/strata_control/speed_switches.py)

## 実行時の詳細

`verify.cpp` の `g_route_prior()` は初回呼び出し時に環境文字列と変換後の λ を関数内 `static` に保持します。プロセス稼働中に環境を書き換えても、この値は再評価されません。verify の各 routing 後に λ を調べ、上記形状と resident table の条件を満たし λ が正なら `route_prior_top10` を起動します。[`verify.cpp:299-303, 2662-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

kernel は各 token の 512 個の logit を走査し、resident expert（その層の `res[e] >= 0`）にだけ λ を加えたスコアから top-10 を選びます。重みは補正前 logit の softmax 確率を選ばれた10個分で正規化したものです。各行について有効な候補が10個揃わない、または選択確率の合計が有限の正値でない場合、その行の ids/weights を書き換えず、元の router top-10 を維持します。kernel 起動関数は `n_tok <= 0` なら何もしません。[`route_prior.cu:29-47, 50-83, 88-92`](../../../../Niko1221/Strata/engine/src/kernels/cuda/route_prior.cu)

同じ名前は `generate.cpp` の window warm-up 判定でも読み取られます。ここでは `route_prior_resolve` を使って `STRATA_WINDOW_WARM` の規則へ渡し、判定結果を関数内 `static` に保存します。prior が正なら、未指定の window warm-up は避けられます（明示的な `STRATA_WINDOW_WARM=1` は強制）。この warm-up は最初のリクエスト前に推測用の dummy token を処理して expert cache を温める処理であり、prior 有効時には dummy token が residency table を偏らせて初回回答に影響し得ることが理由です。warm-up 自体は `o.spec >= 2`、`n_stages == 1`、`o.batch <= 0` の場合に限られます。[`generate.cpp:16348-16360`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)、[`sm120_series.hpp:128-136`](../../../../Niko1221/Strata/engine/include/strata/core/sm120_series.hpp)

## ログと測定値

verify の dispatch 統計通知には `route_prior=0` または `route_prior=1` のフィールドがあります（後者は λ が正の場合）。これは有効値そのものではなく、正値かどうかの表示です。通常の成功時にこの設定専用の警告やエラーを出す処理は見つかりません。kernel は rankable な10候補が揃わない行を元の router 結果のままにする設計で、専用の失敗ログはありません。[`verify.cpp:2662-2670`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`route_prior.cu:65-83`](../../../../Niko1221/Strata/engine/src/kernels/cuda/route_prior.cu)

`docs/DETAILS.md` と 0.2.7 release notes は RTX 3060 12 GB / Qwen IQ3_XXS での測定として、`1.5` で story decode +15%、code decode +37% と記載します。また長い agent task では反復や弱い結果が出る懸念から 0.2.8 以降は既定 OFF に戻したと説明します。これは資料に記載された特定条件の測定・判断であり、他カードやモデルでの性能保証ではありません。[`DETAILS.md:1282, 1519`](../../../../Niko1221/Strata/docs/DETAILS.md)、[`release-notes-0.2.7.md:7`](../../../../Niko1221/Strata/docs/release-notes-0.2.7.md)

## 根拠

- `engine/src/core/verify.cpp:294-303, 2662-2670`
- `engine/src/kernels/cuda/route_prior.cu:29-92`
- `engine/include/strata/core/sm120_series.hpp:103-136`
- `engine/src/program/generate.cpp:16348-16360`
- `engine/cmake/strata_gpu_engine.cmake:48-76`
- `terminal/serve/server.py:4007-4028`
- `terminal/strata_control/speed_switches.py:49-51, 107-124, 156-186`
- `docs/DETAILS.md:1282, 1519`; `docs/release-notes-0.2.7.md:7`
