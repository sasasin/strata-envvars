# `STRATA_GR_UP75`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

CUDA の fused hyper-connection read が複数 token をまとめて処理するとき、up projection に Turing 向けの `gr_up75_kernel` を使うか選ぶ。通常の `gr_up_multi_kernel` に対するカーネル選択であり、環境変数自体を読むのは CUDA 実装の `src/kernels/cuda/fused_gr.cu` だけ。

この経路は MTP の attention / MLP hyper-connection read や verifier の複数 token read から呼ばれる。通常の単一 token 用 `fused_gr_read` は別の `gr_up_kernel` を起動するため、この変数による切り替えの対象ではない（`src/core/mtp.cpp:918-930,1044-1053`、`src/core/verify.cpp:1247-1249,2123-2141`、`src/kernels/cuda/fused_gr.cu:2367-2381`）。

## 値と判定

| 値 | 判定 |
| --- | --- |
| 未設定 | デバイスの compute capability と `STRATA_SM75_PERF` による既定判定へ進む。 |
| 設定値を `atoi` で変換して 0 | 専用 kernel を無効にする。空文字、数字で始まらない文字列も 0 になる。 |
| `atoi` の結果が 0 以外 | 専用 kernel を有効にする。たとえば `1`, `-1`, `2` は有効であり、`atoi` が読む数値接頭辞の後ろは判定に使われない。 |

設定有無だけでは有効にならず、変換後の整数が 0 かどうかで決まる。空文字は「未設定」扱いではなく、明示的な 0 として既定判定を上書きする（`src/kernels/cuda/fused_gr.cu:1190-1205`）。

未設定時は、現在の CUDA デバイスが compute capability 7.5 で、かつ `STRATA_SM75_PERF` が `atoi` で非 0 と判定された場合に有効になる。`STRATA_GR_UP75` を明示するとこの既定判定に優先し、コード上は capability による追加制限なしに真偽を返す（`include/strata/core/sm75_series.hpp:24-37`、`src/kernels/cuda/fused_gr.cu:1194-1205`）。

## 有効になる条件

- CUDA 版であること。HIP コンパイル時の `up75_on()` は常に `false` を返すため、HIP ではこの変数は有効にならない（`src/kernels/cuda/fused_gr.cu:1190-1205`）。
- fused multi-token read が標準の `launch_multi` 経路に到達し、`n_tok >= 3` であること。1〜2 token では専用 kernel を選ばない（`src/kernels/cuda/fused_gr.cu:2317-2318,1338-1348`）。
- `q8w` が false であること。Q8 hyper-connection weights の場合は `gr_up_multi_kernel` の分岐へ進み、この環境変数による選択を通らない（`src/kernels/cuda/fused_gr.cu:1232-1234,1328-1338`）。
- `STRATA_GR_V3` の分割経路が選択されていないこと。分割が成立すると `fused_gr_read_multi` は `launch_multi` より前に別 kernel を起動して返る（`src/kernels/cuda/fused_gr.cu:2227-2290,2317-2318`）。
- CUDA ビルドで `STRATA_GR_FAST` が有効な場合、`fast && !q8w` の分岐が先に `gr_up_fast_kernel` を起動するため、この変数の選択には到達しない。`STRATA_GR_FAST` 未設定時の CUDA 既定は Volta かつ `STRATA_SM70_TABLE` 非 0 の場合だけ有効（`src/kernels/cuda/fused_gr.cu:1310-1314,2175-2185`）。

## 実行時の詳細

`up75_on()` 内の `static const int env` は、条件付き選択が初めて評価された時に環境変数を一度だけ読み、プロセス内に保持する。したがって、その後プロセス内で環境値を変更しても反映されない。変数が未設定なら、デバイスごとの `static per_dev[64]` に compute capability 判定を記録する。デバイス取得に失敗するか device index が 0〜63 の範囲外なら、その呼び出しでは無効を返す（`src/kernels/cuda/fused_gr.cu:1190-1205`）。

選択が有効であれば、`gr_up75_kernel` の token 数別 template を起動する。`STRATA_NO_MULTI_GR` が有効な場合は実際の token 数別分岐ではなく最大 token 数用の template を起動するが、`n_tok >= 3` という選択条件は変わらない（`src/kernels/cuda/fused_gr.cu:1256-1260,1338-1347`）。実装コメントは、この kernel が Turing の複数 token up projection 向けで、対応する multi kernel と同じ演算結果になる設計としている（`src/kernels/cuda/fused_gr.cu:432-443`）。

この変数の有効・無効を示す専用ログはない。multi read の CUDA kernel 起動後にエラーがあれば、`fused_gr_read_multi: <CUDA error>` を stderr に出して `exit(1)` する（`src/kernels/cuda/fused_gr.cu:2317-2323`）。

## 根拠

- 直接の読み取り、`atoi` 判定、既定値、デバイス条件: `src/kernels/cuda/fused_gr.cu:1188-1207`。
- Turing 向け kernel の処理と、multi read からの選択条件: `src/kernels/cuda/fused_gr.cu:432-443,1232-1234,1310-1357`。
- HIP で無効となる分岐: `src/kernels/cuda/fused_gr.cu:1190-1205`。
- 既定の Turing 判定と `STRATA_SM75_PERF` の読み取り: `include/strata/core/sm75_series.hpp:24-37`。
- 既存資料 `docs/DETAILS.md:2244-2255` は Turing kernel 群と `STRATA_SM75_PERF` を説明し、この変数をその一つとして列挙している。カーネルのコメントには RTX 2080 Ti の `fused_gr_bench` cold 測定（up と stamp を含む）の T=3/4/6 の値があるが、これはソースコメントに記された測定であり、本調査で再測定・検証していない（`src/kernels/cuda/fused_gr.cu:1188-1189`）。
