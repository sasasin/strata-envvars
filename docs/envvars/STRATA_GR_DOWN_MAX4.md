# `STRATA_GR_DOWN_MAX4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP と SYCL の fused hyper-connection multi-token read で、down projection のチャンクが4 token 以下のとき、各 thread の部分和配列を最大 `kFusedGrMaxT` token 分ではなく4 token 分にした kernel を選ぶ opt-in です。CUDA/HIP は `gr_down_max4()`、SYCL は `launch_multi()` 内の `max4_on` で判定し、down projection の kernel 選択だけを変えます。kernel のコードコメントは同じ tile・block size・加算順と同じ bit を意図すると説明していますが、この調査では実行比較をしていません（`engine/src/kernels/cuda/fused_gr.cu:349-403,1521-1529,1831-1867`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1943-1947,2001-2109`）。

## 値と判定

両 backend とも `std::getenv` の戻り値を `std::atoi` に渡し、結果が 0 以外なら有効です。未設定は無効です。設定された空文字も `atoi("") == 0` となり無効です。文字列全体の妥当性検査はなく、`atoi` が先頭の空白と符号付き10進数部分を読み、数字が始まらない場合は 0 になります。

| build/backend | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP | 無効 | `1`, `2`, `-1`, `01`, `1x`, `1.0`, ` 1`（`atoi` の結果が非0） | 空文字、`0`, `0anything`, `true`, `false`, `x1`（結果が0） |
| SYCL | 無効 | CUDA/HIP と同じ（`atoi` の結果が非0） | CUDA/HIP と同じ |

大文字小文字による判定はありません。値に別の意味や上限はなく、数値への変換結果が真偽に使われます。読み取り結果は関数内 `static` に保存されます。CUDA/HIP は `ct <= 4` の場合に `gr_down_max4()` が呼ばれた最初の時点、SYCL は `launch_multi()` のループ最初の反復で初期化され、その後プロセス内で環境を変更しても反映されません（`engine/src/kernels/cuda/fused_gr.cu:1524-1529,1831-1835`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1932-1947`）。

## 有効になる条件

- fused hyper-connection の multi-token read が呼ばれ、CUDA/HIP では `launch_multi()`、SYCL では対応する `launch_multi()` まで処理が進む必要があります。1回の down launch が対象にする token 数 `ct` が4以下のときだけ候補になります。より大きい `ct` では無効値と同じ kernel です（`engine/src/kernels/cuda/fused_gr.cu:1821-1835,1855-1867`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1932-1947,2001-2109`）。
- CUDA/HIP の通常の non-staged 経路では、`ct <= 4` なら plain/Q8 と tile 幅 `N` または `N/2` に応じて `MAX_T=4` の down kernel を選びます（`engine/src/kernels/cuda/fused_gr.cu:1855-1867`）。
- CUDA/HIP の staged 経路では、`STRATA_NO_MULTI_GR` が未設定・空・`0` 始まりなら `exact_t` が true になり、`ct=1..6` は既に token 数ごとの exact kernel を使います。このため `STRATA_GR_DOWN_MAX4` が有効でも staged 経路の選択は変わりません。`STRATA_NO_MULTI_GR` が空でなく `0` 以外から始まる場合は generic 経路になり、`ct <= 4` でこの変数が有効なら `gr_down_staged_kernel<4>`、そうでなければ既定の `kFusedGrMaxT` kernel を選びます（`engine/src/kernels/cuda/fused_gr.cu:1816-1820,1835-1854`）。
- SYCL の staged 経路には上記の CUDA/HIP の `STRATA_NO_MULTI_GR` exact-token 分岐がなく、`ct <= 4` とこの変数の有効判定で `<4>` staged kernel を選択します（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1943-1947,1948-2000`）。
- CUDA/HIP では Q8 inject 入力の `launch_q8()` が先に返るとこの切替を使いません。RDNA 専用 read が有効ならそちらへ分岐し、`STRATA_GR_V3` による v3 の split read が有効な場合も `launch_multi()` を通りません。HIP gfx906 で `STRATA_GR_SPLIT=1` かつ BF16 down weights の split 経路を選ぶ場合も同様です（`engine/src/kernels/cuda/fused_gr.cu:4286-4303,4304-4310,4351-4397,4399-4425`）。SYCL では `STRATA_GR_V3` の split read が選ばれると `launch_multi()` に進みません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202`）。
- 既定値や CLI / 設定ファイルとの優先順位を決める Strata 側の設定・転送処理は見つかりませんでした。コードではプロセス環境から直接読み取っています。

## 実行時の詳細

CUDA/HIP の `fused_gr_read_multi_slice()` は Q8 注入、RDNA 専用処理、v3 split、HIP gfx906 の split を順に判定し、残った既定経路で `launch_multi()` を呼びます。そこで shared-memory 容量から決めたチャンクごとに `ct` を求め、down projection の kernel を起動します。`gr_down_multi_kernel` の `acc[MAX_T]` は thread の各 token 部分和を持ち、`MAX_T` が4の kernel ではその配列とループ上限が4になります。down の計算後に up kernel を起動する流れは別処理です（`engine/src/kernels/cuda/fused_gr.cu:349-403,1810-1869,4424-4431`）。

CUDA/HIP の設定値は process-wide な関数 static、SYCL はループ内の関数 static で一度だけ評価されます。デバイスごとの cache ではなく、同じプロセスで環境を変えても再評価されません。CUDA/HIP の既定経路では kernel launch 後に `cudaGetLastError()` を確認し、失敗すると stderr に `fused_gr_read_multi: <CUDA error string>` を出して `exit(1)` します（`engine/src/kernels/cuda/fused_gr.cu:1524-1529,4424-4430`）。この環境変数専用のログや警告はありません。

## ログと測定値

Strata のコードに、この変数の値や選択 kernel を知らせる専用ログはありません。CUDA/HIP の一般的な launch failure は上記の stderr と終了経路で観測できます。ソースコメントには RTX 5070 の Q2_0 default config で行った10組の interleaved decode A/B では高速化を確認できず（ON/OFF median 0.97–0.99）、既定 OFF とした旨があります（`engine/src/kernels/cuda/fused_gr.cu:1521-1523`）。一方、Strata 0.1.39 のコミュニティ測定資料は RTX 5070 Ti / Ryzen 7 9800X3D / Windows 11 の一台で、同変数を他の engine env 2個と併用した状態で decode +2.8%（short）、+3.5%（130K後）と記録しています。別の RTX 5070 Ti / Ryzen 9 5900X / Windows 10 の資料では複数設定の組み合わせの効果がゼロと報告されています。どちらも現行 checkout の再測定ではなく、この変数単独の因果を示す数値とは扱えません（`docs/bench-results/2026-10-04-community-rtx-5070ti-windows/README.md:1-8,58-59,98-107`、`docs/bench-results/2026-10-06-community-rtx5070ti-5900x/README.md:1-6,17-21,60-70`）。

## 根拠

- CUDA/HIP の読み取りと判定: `engine/src/kernels/cuda/fused_gr.cu:1524-1529`
- CUDA/HIP の呼び出し条件・kernel 分岐: `engine/src/kernels/cuda/fused_gr.cu:1810-1869`
- multi-token down kernel の部分和: `engine/src/kernels/cuda/fused_gr.cu:349-403`
- CUDA/HIP の先行する別経路と launch failure: `engine/src/kernels/cuda/fused_gr.cu:4286-4303,4304-4310,4351-4429`
- SYCL の読み取り・分岐: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1932-2109`
- SYCL の v3 分岐: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202`
