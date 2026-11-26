# `STRATA_NO_MULTI_GR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_NO_MULTI_GR` は、複数 token をまとめて行う hyper-connection（GR）の一部の読出し・残差書込み最適化を避けるための実行時フラグです。Strata はこの値を真と判定すると、CUDA/HIP の `gr_read_multi` / `gr_write_multi` が使う native multi-token 経路を選ばず token ごとの呼出しへフォールバックします。また、Verifier と MTP の窓処理で GR 書込みを token ごとに呼び、CUDA fused GR の一部で token 数ごとに特殊化したカーネルを選ばないようにします（`engine/src/kernels/cuda/gr.cu:466-509,531-549`、`engine/src/kernels/cuda/fused_gr.cu:1816-1820,1836-1854`、`engine/src/core/verify.cpp:348,1753-1775`、`engine/src/core/mtp.cpp:1458-1477`）。

これは全演算を逐 token 化する指定ではありません。GR の外側にある MoE router、expert grouping / combine 等の batch 経路は、このフラグによる分岐の対象ではありません（例: `engine/src/core/mtp.cpp:1422-1450,1462-1477`）。また、fused GR の `exact_t` を無効にする分岐では複数 token を扱う fused kernel 自体は残ります（`engine/src/kernels/cuda/fused_gr.cu:1820-1829,1847-1854`）。

## 値と判定

各読み取り箇所は `getenv` の値について「未設定ではない」「先頭 byte が NUL でない」「先頭 byte が文字 `'0'` でない」を調べます。文字列全体の parse や数値変換はしません。従って `1` だけでなく `true`、`TRUE`、`-1`、` 0` は有効、空文字・`0`・`0anything` は無効です。空白の trim、大文字小文字変換、数値としての妥当性検査はありません。CUDA/HIP の共通 kernel と MTP、SYCL の同等箇所はこの規則です。Verifier の `env_on` helper も同じ先頭 byte 判定を使います（`engine/src/core/verify.cpp:336-339,348`、`engine/src/core/mtp.cpp:1458-1461,2592-2595`、`engine/src/kernels/cuda/gr.cu:466-472`、`engine/src/kernels/cuda/fused_gr.cu:1816-1820`、`engine/sycl/src/core/verify.cpp:151-154,242`、`engine/sycl/src/core/mtp.cpp:1173-1176`、`engine/sycl/src/kernels/cuda/gr.dp.cpp:689-695`）。

| 条件 | unset | 無効値の例 | 有効値の例 |
|---|---|---|---|
| CUDA/HIP/SYCL の掲載箇所 | false（multi-token 経路の条件を維持） | `""`, `"0"`, `"0anything"` | `"1"`, `"true"`, `"-1"`, `" 0"` |

`STRATA_NO_MULTI_GR` を上書きする CLI 引数や別の設定値は、対象の分岐では参照されません。判定は boolean であり、境界数値や fallback 値はありません。

## 有効になる条件

- CUDA/HIP の GR kernel では、`gr_read_multi` / `gr_write_multi` が呼ばれ、token 数が 1 より大きい場合に native multi-token 経路を外します。`native_mmvf` が無効なら元からその経路を通らず、フラグによる追加の切替はありません。`gr_read_multi` は通常の `gr_read` を token ごとに呼び、`gr_write_multi` も `gr_write` を token ごとに呼びます（`engine/src/kernels/cuda/gr.cu:474-509,531-549`）。
- SYCL の移植 kernel にも同じ条件があります。`native_mmvf` が有効で複数 token の場合に限り、multi-token GR 読み書きの最適化を避けます（`engine/sycl/src/kernels/cuda/gr.dp.cpp:697-710,787-803`）。
- Verifier の batch decode では、`dec_batch` と group の `n > 1` 等を満たす GR 書込みを個別 token にします。最終 layer の `dec_batch` 書込みも `g_no_multi_gr` が真なら個別呼出しです（CUDA: `engine/src/core/verify.cpp:1753-1775,2984-2988`、SYCL: `engine/sycl/src/core/verify.cpp:1183-1188,1839-1843`）。
- MTP では `T` 件の draft token の GR 書込みについて、head GR を fuse していない場合に token ごとの `gr_write` を選びます。fused head GR が有効な場合、この明示的な書込み分岐は実行されず、後段の fused GR 読み出し側の処理が使われます（CUDA: `engine/src/core/mtp.cpp:1458-1477,1481-1512,2592-2612`、SYCL: `engine/sycl/src/core/mtp.cpp:1173-1192`）。
- CUDA fused GR read では `exact_t = false` となり、staged down read の `exact_t` による token 数別 template 分岐（`ct == 1..6`）を通しません。その後は `max4` 条件を満たせば `<4>` kernel、それ以外は generic kernel を選びます。また、複数の up kernel 選択で `no_multi_gr` が真なら `kFusedGrMaxT` を template token 数として渡します。ここは fused GR 経路内のカーネル選択であり、外側の fused multi-token 呼出しを止めるものではありません（`engine/src/kernels/cuda/fused_gr.cu:1816-1820,1836-1854,1872-1925`）。
- 1 token の呼出し、batch / MTP の対象外経路、または GR の multi-token API を呼ばない経路には、これらの分岐による効果はありません。生成 token や routing 選択を変更する条件分岐は、ここで確認した読み取り箇所にはありません。

## 実行時の詳細

CUDA/HIP と SYCL Verifier の `g_no_multi_gr` は namespace-scope `const bool` 初期化時に読みます。プロセス開始後の環境変更はこの値に反映されません（`engine/src/core/verify.cpp:336-349`、`engine/sycl/src/core/verify.cpp:151-154,242-243`）。CUDA/HIP `gr.cu`、CUDA fused GR、CUDA/SYCL MTP および SYCL `gr.dp.cpp` は関数内 `static const bool` の初回評価で値を保存します。それぞれ最初に該当 kernel / MTP 経路へ到達した後の変更は反映されません（`engine/src/kernels/cuda/gr.cu:466-472`、`engine/src/kernels/cuda/fused_gr.cu:1816-1820`、`engine/src/core/mtp.cpp:1458-1461,2592-2595`、`engine/sycl/src/core/mtp.cpp:1173-1176`、`engine/sycl/src/kernels/cuda/gr.dp.cpp:689-695`）。

値の不一致による警告や設定値のログは、これらの読み取り・分岐にはありません。後続 kernel の実行失敗時には各経路の既存エラー処理が働きますが、`STRATA_NO_MULTI_GR` 固有の終了・失敗経路は見当たりません。たとえば CUDA `gr_read_multi` / `gr_write_multi` は同期失敗を stderr に出して終了するコードを持ちますが、これはフラグ値を理由とするものではありません（`engine/src/kernels/cuda/gr.cu:491-501,534-549`）。

## 根拠

- 全直接参照と候補確認: `engine/src/core/verify.cpp:348`、`engine/src/core/mtp.cpp:1458-1461,2592-2595`、`engine/src/kernels/cuda/gr.cu:466-472`、`engine/src/kernels/cuda/fused_gr.cu:1816-1820`、`engine/sycl/src/core/verify.cpp:242`、`engine/sycl/src/core/mtp.cpp:1173-1176`、`engine/sycl/src/kernels/cuda/gr.dp.cpp:689-695`。その他の一致はコメント、生成設定データ、または調査対象外の test のみでした。
- `docs/DETAILS.md` にはこの変数名の記載がなく、動作根拠には使用していません。
