# `STRATA_PF_XMX_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の prompt prefill で `STRATA_PF_XMX=2` の fused grouped XMX を使うとき、fused XMX と、各 expert を FP16 に dequantize して oneMKL GEMM に渡す経路との切り替え境界（expert あたり平均行数）を指定する。値は prefill の計算経路を選ぶだけで、CLI 引数や生成 token の選択を直接変える処理はない。実装は `engine/sycl/src/prefill/prefill.cpp` の `xflush` lambda にある（5031-5066 行）。

## 値と判定

`xflush` が fused XMX 分岐に到達した最初の時点で `std::getenv` し、未設定なら `200`、設定されていれば `std::atoi` の結果を関数内 `static const int` に保存する。文字列全体の妥当性検査はなく、先頭から `atoi` が読める整数部分を使う。先頭空白と符号は `atoi` の規則で処理され、整数に変換できない文字列や空文字は `0` になる。したがって `200rows` は `200`、`0anything`・`true`・空文字は `0` として扱われる。整数として表現できない大きさの入力の結果は C ライブラリの `atoi` の範囲外であり、Strata 側で検証・規定していない。

| 条件 | unset | 有効になる値の例 | 無効値・境界の例 |
|---|---|---|---|
| fused grouped XMX 分岐に到達 | 既定 `200` | `201`、`200`、`1`、`-1`（整数としてそのまま比較） | 空文字、`0`、`0anything`、`true` は `0`。変換後 `0` 以下なら fused 側の条件を満たさない |

実際の比較は整数除算した `nr / xg_n < xg_max`。`nr` は group 内の routed row 合計、`xg_n` は group 内 expert 数であり、ここでは `xg_n > 0`。平均値が閾値より**小さい**と fused kernel を選び、等しい場合と大きい場合は dequantize + oneMKL 経路を選ぶ（`engine/sycl/src/prefill/prefill.cpp:4858-4861,5037-5066`）。

## 有効になる条件

- SYCL engine の prefill 経路であること。通常の CUDA/HIP 経路にはこの読み取り箇所がない。SYCL は独立した backend として構成される（`engine/CMakeLists.txt:23-33`）。
- `STRATA_PF_XMX` が `2` に解釈され、layer が `!use_mmq`、native expert pack、対応形式などの条件を満たして `xmx2_only` になること。形式・寸法判定は `engine/sycl/src/prefill/prefill.cpp:4754-4772` にある。
- XMX build/device 条件を通過して XMX mode が無効化されていないこと。Arc Alchemist は `STRATA_PF_XMX` 未設定時に mode 2 が既定、Battlemage は既定 0。非対応 AOT build や、sub-group 8 用 build で Battlemage を使う場合は mode を 0 にし、警告を出す（`engine/sycl/src/prefill/xmx_moe.dp.cpp:149-173`）。build 時の XMX kernel 切替は `engine/sycl/CMakeLists.txt:73-77`。
- `STRATA_PF_XMX=1` の dequantize + grouped XMX 経路、mode 0 の通常 FP16 経路、MMQ 経路、または条件を満たさず `xmx2_only` にならない layer では、この閾値を使う fused 分岐に入りません。
- 別の CLI 引数によるこの閾値の上書きは実装されていない。`STRATA_PF_XMX` は別変数で、XMX mode 自体を選ぶ。

## 実行時の詳細

`xflush` は group の行数 `nr` を集計してから fused XMX 分岐を実行する。そこで初めて `STRATA_PF_XMX_ROWS` を読むため、変数の変更はプロセスの最初の該当 group より前に反映されるが、`xg_max` の初期化後は同じプロセス内で再読込されない。unset の 200 も同じく cache される（`engine/sycl/src/prefill/prefill.cpp:4850-4861,5031-5041`）。

条件が真なら gate/up と down の両方に `iq_xmx_grouped` を呼び、間に SwiGLU を実行する。偽なら expert ごとに重みを FP16 へ dequantize し、gate/up と down を `m.gemm.f16` で処理する（`engine/sycl/src/prefill/prefill.cpp:5041-5066`）。どちらも同じ group の routed rows に対する expert 計算経路の切替である。kernel 側は group 数・寸法・量子化形式の不正を stderr に出して `exit(1)` するが、通常この呼び出しに渡す group と寸法は同じ prefill 側のデータから作られる（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:8168-8174`）。

## ログと測定値

fused XMX 分岐に到達したときは stderr に `strata: prompt experts on the fused grouped XMX (STRATA_PF_XMX=2)` を一度出す。閾値の実値や、group ごとにどちらの枝を選んだかを示すログはない（`engine/sycl/src/prefill/prefill.cpp:5031-5034`）。

隣接するソースコメントには「16 experts」の `xmx_group_parity` 測定で約 200 rows/expert 未満では fused launch が勝り、320 では dequantize + oneMKL の gate/up が fused より 0.67-0.76 倍、と記されている（`engine/sycl/src/prefill/prefill.cpp:5035-5036`）。コメントには測定機種、OS、回数が示されていないため、一般的な性能値とは扱えない。`docs/INTEL.md:278-280` には `STRATA_PF_XMX` の mode 説明があるが、この rows 閾値の詳細・測定条件は記載されていない。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:5031-5066` — fused XMX 分岐、環境変数読み取り、閾値比較と代替経路。
- `engine/sycl/src/prefill/prefill.cpp:4754-4772` — mode 2 の native pack / format eligibility。
- `engine/sycl/src/prefill/xmx_moe.dp.cpp:149-173` — `STRATA_PF_XMX` の既定値、build/device 条件と警告。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:8168-8174` — grouped kernel の引数検査と失敗時の終了。
- `engine/CMakeLists.txt:23-33`、`engine/sycl/CMakeLists.txt:73-77` — SYCL backend と XMX build 条件。
- `docs/INTEL.md:278-280` — Strata 資料の XMX mode 説明。
