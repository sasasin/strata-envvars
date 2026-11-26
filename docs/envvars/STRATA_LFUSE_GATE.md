# `STRATA_LFUSE_GATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`STRATA_LFUSE=1` で有効になる resident decode の shared-expert 融合処理のうち、shared expert の gate projection を router の batched GEMV に同乗させる経路を許可するか決める。既定は許可で、`STRATA_LFUSE_GATE` の先頭文字が `0` のときだけこの gate 融合を止める。CUDA/HIP 側の verifier と SYCL verifier に読み取り実装がある（`engine/src/core/verify.cpp:188,1522-1525,2634-2645`、`engine/sycl/src/core/verify.cpp:131,1060-1063,1581-1592`）。候補名の他のソース参照 `terminal/data/settings-register.json:21090-21100` は読み取り箇所を記録する設定レジストリで、実行時の読み取りは上記2箇所。

このフラグは shared expert 自体を無効にしない。gate の同乗を止めると router は通常の router 重みだけを計算し、shared expert 処理側で gate を計算する。gate を同乗できた場合は shared expert 側でその計算を省き、後段 combine が gate を適用する（`engine/src/kernels/cuda/shared_expert.cu:258-281`、`engine/src/core/verify.cpp:2747-2754,2944-2959`）。実装コメントはこの融合経路の算術を bitwise 同一と説明している（`engine/src/core/verify.cpp:2632-2634`）。

## 値と判定

両 verifier の `g_lfuse_gate()` は `std::getenv` の戻り値を関数内 `static const bool` に一度だけ保存する。未設定なら `true`、設定されていれば `v[0] != '0'` を返す。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（`engine/src/core/verify.cpp:188`、`engine/sycl/src/core/verify.cpp:131`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP verifier、SYCL verifier | 有効 | 空文字、`1`、`true`、`false`、` 0` など、先頭文字が `0` 以外 | `0`、`0anything`、`00` など、先頭文字が `0` |

`0` 以外なら後続文字を問わず有効なので、`false` も有効になる。大文字小文字や文字列の数値としての妥当性は判定しない。無効値のときは融合用の gate 重みを取得せず、通常経路へ進む。

## 有効になる条件

この値が有効でも、次の条件がすべて揃わなければ gate 同乗は行われない。

- `STRATA_LFUSE` の先頭文字が `1` である。未設定や `true` では `g_lfuse()` が false になる（`engine/src/core/verify.cpp:125,1522-1525`、`engine/sycl/src/core/verify.cpp:130,1060-1063`）。
- verifier が resident mode (`ar_on()`) で、native MoE combine と decode batching が有効である。
- 対象 group の token 数 `n` が 2〜8 であり、shared expert の native BF16 経路が有効である。
- router projection の追加 gate row を扱う router 経路に入る: `n > 1`, `w_router != nullptr`, `native_router_enabled()`, `K == 10`。CUDA/HIP verifier は `NE == 512`、SYCL verifier は `NE == 512` または `NE == 256` を要求する（`engine/src/core/verify.cpp:2631-2645`、`engine/sycl/src/core/verify.cpp:1578-1592`）。
- モデルに `ffn_gate_inp_shexp.weight` があり、追加 GEMV が成功する。重みが無いか追加 GEMV が `false` を返した場合は `sg_ready` が false のまま通常 router GEMV に進む。

`STRATA_LFUSE_GATE` は CLI 引数や設定ファイルで上書きされない。隣接する `STRATA_LFUSE_PAIR` は gate/up projection の pair 経路を別に制御するが、この gate 同乗の可否は `STRATA_LFUSE_GATE` と上記条件で決まる（`engine/src/core/verify.cpp:189,2750`、`engine/sycl/src/core/verify.cpp:132,1671`）。

## 実行時の詳細

`g_lfuse_gate()` は `lfuse_on(n)` が真になり、`lfuse_on(n) && g_lfuse_gate()` の右辺が初めて評価された時点で環境を読む。結果は function-local static に cache されるため、同一プロセス内での環境変更は反映されない（`engine/src/core/verify.cpp:188,2634`、`engine/sycl/src/core/verify.cpp:131,1581`）。

許可され、router 条件とモデル重みが揃えば `bf16_gemv_fp32_mmvf_multi_aux` が router logits と shared gate 値 `sh_g_` を計算し、成功時だけ `sg_ready=true` になる。失敗時は通常の `bf16_gemv_fp32_mmvf_multi` に fallback する（`engine/src/core/verify.cpp:2634-2645`、`engine/sycl/src/core/verify.cpp:1581-1592`）。後続の `shared_expert_multi` には `sg_ready` が bit 0 として渡され、true なら shared-expert 関数は gate 計算・出力 scale を省略し、combine が `native_moe_combine_multi_hits_gated` で gate を適用する。false なら shared expert 側が gate を計算し通常 combine を使う（`engine/src/core/verify.cpp:2747-2754,2944-2959`、`engine/src/kernels/cuda/shared_expert.cu:258-281`、`engine/sycl/src/core/verify.cpp:1668-1675,1810-1823`、`engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:355-405`）。

追加 GEMV が例外を投げると verifier は `verify router: ...` をエラーとして返す。shared-expert 呼び出しの例外は `verify shared expert: ...`、combine の例外は `verify combine: ...` として返る（`engine/src/core/verify.cpp:2646,2752-2754,2945-2948`、SYCL 側 `engine/sycl/src/core/verify.cpp:1593,1673-1675,1810-1813`）。この環境変数専用の警告や終了経路はない。

## ログと測定値

CUDA/HIP verifier は dispatch 統計が有効な場合、`router layer: batched native router=%ld, shared-expert gate in the router launch=%ld, route_prior=%ld` と `combine layer: kind %ld (0 per-token, 1 multi, 2 multi+hits, 3 multi+hits gated)` を統計に記録する。gate 同乗の結果は router 行の第2値（`sg_ready`）と combine kind `3` に表れる（`engine/src/core/verify.cpp:2663,2944`）。統計は既定で有効だが、`STRATA_DISPATCH_STATS` の先頭文字が `0` なら無効。記録は stderr へ直接出ず、`STRATA_DISPATCH_REPORT` が空でないパスに設定されている場合に終了時 JSON へ書かれる（`engine/include/strata/core/dispatch_stats.hpp:107-119,145-152`）。SYCL verifier にはこれら2つの `notef` 記録がない。

測定値は該当する Strata 資料に見つからなかった。`docs/DETAILS.md` の SM70 設定表は `STRATA_LFUSE=1` を挙げるが、`STRATA_LFUSE_GATE` の値や測定値は記載していない（`docs/DETAILS.md:1487`）。

## 根拠

- `engine/src/core/verify.cpp:125,188,1522-1525,2631-2646,2747-2754,2944-2959`
- `engine/sycl/src/core/verify.cpp:130-132,1060-1064,1578-1593,1668-1675,1810-1823`
- `engine/src/kernels/cuda/shared_expert.cu:216-220,258-283`
- `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:315-320,355-405`
- `engine/include/strata/core/dispatch_stats.hpp:107-119,145-152`
- `docs/DETAILS.md:1487`
