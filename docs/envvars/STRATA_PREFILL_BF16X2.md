# `STRATA_PREFILL_BF16X2`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

プロンプト prefill の BF16 重み GEMM で、BF16 に丸めた活性値だけでなく、その丸めで落ちた残差も別の BF16 GEMM として加算するかを選びます。実装コメントでは BF16 の有効精度をおよそ16 bitにするモードとして説明されています。対象は hyper-connection、SSM alpha/beta、indexer、router、shared gate、PLE のバッチ key/value 経路などの BF16 重み投影です。値を変えるため opt-in で、decode の経路を切り替える変数ではありません（`src/prefill/prefill.cpp:316-322,1989-1994`）。

## 値と判定

値は `std::atoi` で整数に変換され、環境変数が未設定なら `0` です。文字列全体の厳密な数値検査はせず、`atoi` が変換した整数を使います。したがって空文字や数字で始まらない文字列は通常 `0`、`1tail` は `1`、`2tail` は `2`、`-1` は `-1` と判定されます。空白と符号を含む数字も `atoi` の規則で変換され、数値の後ろに続く文字列は判定されません。

| `atoi` の結果 | 通常の BF16 活性入力 | hyper-connection の BF16 活性入力 |
|---|---|---|
| `0`（未設定、空文字、無効な先頭文字を含む） | 無効 | 無効 |
| `1` | 有効 | 有効 |
| `2` | 有効 | 無効 |
| その他の非0整数 | 有効 | 無効 |

判定関数は最初の呼び出しで環境変数を読み、`static const int` に保存します。以後、プロセス内で環境変数を書き換えても設定は再読込されません。また各判定に `f16_io` が渡され、これが真なら `atoi` の結果にかかわらずモードを `0` として扱います（`src/prefill/prefill.cpp:323-342`、SYCL実装 `sycl/src/prefill/prefill.cpp:244-263`）。

## 有効になる条件

- prefill の BF16 活性入力経路で有効です。HIP の `STRATA_HIP_PROMPT_F16` などにより、その stage が FP16 入出力（`f16_io`）を選んだ場合は無効です。FP16 活性値にはこの BF16 残差を適用しません（`src/prefill/prefill.cpp:1220-1225,323-342`）。
- モード `1` では hyper-connection の down/up/inject などにも残差バッファを使います。モード `2` 以上や負の非0値では、一般の BF16 投影向け残差は有効ですが、hyper-connection 用の残差バッファは確保されず、hyper-connection 投影は対象外です（`src/prefill/prefill.cpp:1257-1258,2617-2668`）。
- 有効値でも、対象経路で BF16 重み・活性値を使う投影にのみ作用します。native 重みの projection や他の GEMM 全般を一律に置き換える設定ではありません（`src/prefill/prefill.cpp:1983-1994,2692-2695,2718-2722,2944-2947`）。
- 同じ判定とバッファ条件は SYCL 側にもあります（`sycl/src/prefill/prefill.cpp:244-263,1170-1171,2831-2881`）。

## 実行時の詳細

設定モードに応じて、prefill chunk 用の追加 device buffer を確保します。mode `1` は hyper-connection の `xn16_lo` / `lo16_lo` と一般投影用の `mixed_bf_lo`、mode `2` 等の非0値は `mixed_bf_lo` を確保します。必要な分の chunk サイズはメモリ必要量の見積もりにも加算されます（`src/prefill/prefill.cpp:1257-1258,1905-1907`）。

float 活性値を BF16 へ変換するカーネルは高位 BF16 値に加え、要求された場合に低位残差を別バッファへ書きます（`src/prefill/kernels.cu:1727-1733,1840-1843`）。各対象 projection はまず高位 BF16 活性値と BF16 重みの GEMM を行い、低位バッファがあれば同じ重みに対して `beta=1` の GEMM を追加し、同じ出力へ加算します（`src/prefill/prefill.cpp:1989-1994`）。このため prefill の中間値、router の logits や選択結果を含む後続計算が変わり得ます。実装コメントも、残差込みなら router の選択が同じ入力の decode に近づく意図を記していますが、token や routing の同一性を保証するコード上の仕組みは確認できません。

具体的な対象呼び出しには、hyper-connection の down/up/inject（`src/prefill/prefill.cpp:2638-2668`）、GDN の alpha/beta（同 `2692-2695`）、QSA indexer（同 `2721-2722`）、MoE router（同 `2944-2947`）、共有 expert gate（同 `3014-3016`）があります。PLE key/value の batched 経路も低位残差を使います（同 `2553-2577`）。設定値専用のログ出力や無効値の警告は、確認した実装にはありません。

## 根拠

- `src/prefill/prefill.cpp:316-342` — 役割、既定値、mode 1/2、static cache、FP16 抑止。
- `src/prefill/prefill.cpp:1257-1258,1905-1907` — 追加バッファの割当てとサイズ見積り。
- `src/prefill/prefill.cpp:1989-1994` — 高位 GEMM と残差の加算 GEMM。
- `src/prefill/kernels.cu:1727-1733` — BF16 活性値と低位残差の生成。
- `src/prefill/prefill.cpp:2553-2577,2617-2675,2692-2695,2721-2722,2944-2947,3014-3016` — PLE、hyper-connection、GDN、indexer、router、shared gate での適用。
- `sycl/src/prefill/prefill.cpp:238-263,1170-1171,2755-2779,2811-2881` — SYCL実装の同等箇所。

`docs/DETAILS.md` と `README.md` には、この変数の利用者向け説明や性能測定値を確認できません。性能・精度の定量的な効果はここでは記載していません。
