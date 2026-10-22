# `STRATA_SM120_PERF`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の compute capability 12.0（sm_120）向けに、複数の機能を既定で有効にするかをまとめて制御します。変数自体がカーネルを選ぶのではなく、各機能の専用環境変数が未設定のときに使う既定値を `sm120_default()` 経由で変えます。主な対象は speculative verify の side mixer、Daily attention、hyper-connection の up/down カーネル、routed expert の SwiGLU、および対応形式での fused prompt expert です。

## 値と判定

`include/strata/core/sm120_series.hpp:28-35` で `std::getenv()` の結果を `std::atoi()` に渡します。

| 値 | `sm120_series()` の結果 |
|---|---|
| 未設定 | `true` |
| `atoi` の結果が 0 | `false`。空文字、`0`、数値に変換できない文字列など |
| `atoi` の結果が 0 以外 | `true`。負数も含む |

`atoi` は文字列全体の厳密な数値検証ではなく、先頭の空白と符号を許し、先頭の数値部分を変換します。たとえば `2suffix` は 2、`0suffix` は 0 として扱われます。大文字小文字の比較はありません。

## 有効になる条件

- `sm120_default(major, minor)` は、compute capability が 12.0 で、かつ上記の判定が有効なときだけ `true` です。sm_120 以外では、この変数を設定しても同関数による既定値は有効になりません（`include/strata/core/sm120_series.hpp:37-41`）。
- 現行の呼び出し箇所は CUDA 実装です。HIP の分岐では side mixer / Daily attention / SwiGLU の自動既定を使わず、prompt fused expert の `DevInfo::s120` 判定も HIP ビルドにはありません（`src/core/verify.cpp:188-202`, `src/kernels/cuda/qsa_decode_attn.cu:838-859`, `src/kernels/cuda/iq_kernels.cu:4113-4127`, `src/prefill/moe_fused_iq.cu:1261-1295`）。
- 各機能の専用変数が明示されると、その機能の専用判定が優先します。例: `STRATA_SIDE_MIXER`, `STRATA_ATTN_DAILY`, `STRATA_GR_UP75`, `STRATA_GR_DOWN_TG`, `STRATA_GU_SWIGLU`, `STRATA_PF_FUSED`。したがって `STRATA_SM120_PERF=0` でも、専用変数で機能を opt-in できます。prompt fused expert は専用変数と形式・device 対応条件も満たす必要があります（下記実行時詳細、`src/prefill/moe_fused_iq.cu:1391-1427`）。
- この helper が見る GPU 属性は CUDA のデバイス属性です。`STRATA_EMULATE_CC` の現行許容範囲は 75 から 119 までで 120 を含まず、sm_120 のこの既定値をエミュレートする用途には使えません（`include/strata/core/emulate.hpp:10-19`, `include/strata/core/sm120_series.hpp:37-41`）。

## 実行時の詳細

環境変数は `sm120_series()` の最初の呼び出し時に読み、関数内の `static const bool` に保存します。プロセス実行中に環境を書き換えても再評価されません。呼び出し側も GPU ごとの既定判定をキャッシュする箇所があります（例: `src/core/verify.cpp:191-201`, `src/kernels/cuda/fused_gr.cu:1199-1209`, `src/kernels/cuda/qsa_decode_attn.cu:848-858`）。

未設定時の主な既定動作は次のとおりです。

- verify の side mixer は sm_120 で mode 2、それ以外は mode 0 です。明示された `STRATA_SIDE_MIXER` は 0〜2 に clamp され、専用設定が優先します（`src/core/verify.cpp:182-202`）。
- hyper-connection の up75 カーネルは sm_120 でも既定 ON です。down カーネルは 80 SM 以上の sm_120 で 2 token 以上なら 1 token / block row、80 SM 未満では偶数 token 数で token pair を使います。`STRATA_GR_UP75` / `STRATA_GR_DOWN_TG` が明示されると各専用判定に従います（`src/kernels/cuda/fused_gr.cu:1191-1239`）。
- Daily decode attention と routed expert SwiGLU は sm_120 で既定 ON です。それぞれ `STRATA_ATTN_DAILY` と `STRATA_GU_SWIGLU` を明示すると専用判定が使われます（`src/kernels/cuda/qsa_decode_attn.cu:832-859`, `src/kernels/cuda/iq_kernels.cu:4106-4127`）。
- fused prompt expert は sm_120 かつ 80 SM 以上で、対応する gate/up 量子化形式などの条件を満たす場合に限り、対象形式を既定で有効にします。80 SM 未満のカードや未計測形式は自動既定の対象外です。`STRATA_PF_FUSED=0` は無効化し、`=1` は対象を他カードにも opt-in します（`src/prefill/moe_fused_iq.cu:1391-1427`）。

`STRATA_SM120_PERF` 自身によるログ出力やエラー処理は確認できません。`docs/DETAILS.md:2463-2491` は RTX PRO 5000 Blackwell 72 GB（110 SM、sm_120、Linux、CUDA 13.2）での測定と既定スイッチを記載し、`STRATA_SM120_PERF=0` でそのスイッチ群を止められると説明しています。同資料は別カードや Windows などの未測定条件も明記しています。ここに示した速度・品質の主張は同資料の記述であり、この調査で再測定した結果ではありません。

## 根拠

- 判定、sm_120 判定、既定値 helper: `include/strata/core/sm120_series.hpp:28-41`
- verify side mixer の既定と GPU ごとの cache: `src/core/verify.cpp:182-202`
- hyper-connection up/down の既定: `src/kernels/cuda/fused_gr.cu:1191-1239`
- Daily attention の既定: `src/kernels/cuda/qsa_decode_attn.cu:832-859`
- routed expert SwiGLU の既定: `src/kernels/cuda/iq_kernels.cu:4106-4127`
- fused prompt expert の sm_120 判定と適用条件: `src/prefill/moe_fused_iq.cu:1291-1297,1391-1427`
- Strata の測定説明と専用変数による上書き: `docs/DETAILS.md:2463-2491`
