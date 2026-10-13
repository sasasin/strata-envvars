# `STRATA_GR_FAST`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

複数 token をまとめて処理する hyper-connection read (`fused_gr_read_multi`) で、正規化 (`norm`) と up projection にレイテンシ隠蔽版の GPU kernel を使うか選びます。無効時は従来 kernel を使います。単一 token の `fused_gr_read` は別の `gr_down_kernel` / `gr_up_kernel` を直接起動するため、この環境変数では切り替わりません。

## 値と判定

`src/kernels/cuda/fused_gr.cu:1815-1823` の `gr_fast()` が、初回呼び出し時に `std::getenv("STRATA_GR_FAST")` を一度読み、値を static cache します。未設定なら `-1`（カード別の既定値）、設定済みなら `std::atoi` の結果が 0 かどうかで決めます。

| 値 | 判定 |
|---|---|
| 未設定 | backend / GPU による既定値を使う |
| 設定ありで `atoi(value) == 0` | fast kernel を使わない。空文字、数字で始まらない文字列、`0`, `0abc` などが該当 |
| 設定ありで `atoi(value) != 0` | fast kernel を使う。例: `1`, `-1`, `2`, `1abc` |

`atoi` は文字列全体の妥当性を検査しません。先頭の空白や符号の後の数値を変換し、数値の後ろにある文字は判定に影響しません。数値として読み取れない文字列は 0 扱いです。環境変数をプロセス起動後に変更しても、最初の判定後は再読込されません。

## 有効になる条件

- `.cu` 実装では `STRATA_GR_FAST_BUILD` が有効な場合に fast norm/up kernel がコンパイルされます。有効条件は `STRATA_HIP_GFX906` が定義されているか、HIP コンパイラ (`__HIPCC__`) 以外でコンパイルされることです。したがって通常の CUDA build ではコードが含まれ、HIP build では gfx906 向け build に限って含まれます (`src/kernels/cuda/fused_gr.cu:28-33`)。
- fast kernel がビルドされていない HIP build では `gr_fast()` 自体が使われず、`launch_multi` は従来 kernel を起動します。
- fast kernel がビルドされる HIP では、環境変数 unset 時の既定は ON です (`1819-1821`)。
- CUDA では、環境変数 unset 時は `STRATA_SM70_TABLE` が設定され、かつ `cur_dev_volta()` が真（Volta GPU）で、その値の `atoi` が非 0 の場合だけ ON です。それ以外は OFF です (`1822`)。`STRATA_GR_FAST` が明示設定されている場合は、この既定値より優先されます。
- ベンチ用 API `fused_gr_set_fast(int)` が 0 以上を設定すると、それが環境変数より優先されます。通常コード内での setter 呼び出しは見つからず、ベンチ実装が使用します (`1814-1828`, `src/kernels/fused_gr_bench.cpp:89,105,136`)。

値が有効でも、fast kernel がコンパイルされていることと `fused_gr_read_multi` の通常 read 経路を通ることが必要です。HIP gfx906 の `STRATA_GR_SPLIT=1` 経路でも `gr_fast()` の結果により norm/up kernel が切り替わります (`1930-1946`)。Q8 read (`q8_down` と `q8_up` が指定された経路) は `launch_q8` から先に return するため、この変数による分岐を通りません (`1856-1864`)。`STRATA_GR_V3` が利用可能な条件を満たし、V3 kernel 経路に入った場合も `gr_fast()` による分岐を通りません (`1865-1929`)。

## 実行時の詳細

通常の複数 token read では `launch_multi` が fast 判定を行い、有効なら `gr_norm_fast_kernel` を起動します。`STRATA_HC_SPLIT` で split/staged variant が選ばれている場合、norm は別の split norm kernel（gfx12 の HIP では `STRATA_GR_NORM_FAST` による追加選択）を使います。down projection の後、同じ fast 判定に従って `gr_up_fast_kernel` または従来 up kernel を起動します (`1030-1046`, `1091-1096`)。

fast norm/up 実装は、データ読み込みと演算を重ねるための kernel です。ソースコメントでは、norm の入力を先に読み込んで中間値 `xn` をレジスタに保持し、up projection では warp 内の複数行の重みと epilogue 入力を先に読み込む構成と説明しています (`1134-1139`)。CUDA で `STRATA_GR_FAST` 未設定の Volta を有効にする別条件 `STRATA_SM70_TABLE` は `gr_fast()` 内で確認されます。

実装コメントは置換前後の同じ算術順序および bitwise 一致を記しています (`1032-1035`)。ただし、この調査では実行や測定をしていません。エラー出力や警告はこの変数の値だけを理由には出しません。

## 文書との照合

`docs/NVIDIA_V100.md` は sm_70 上の hyper-connection up projection に gfx906 の latency-hidden kernel を挙げ、`STRATA_GR_FAST=0` で従来 kernel を選べると説明しています。同文書では `STRATA_SM70_TABLE=1` の V100-SXM2 における verify window GPU work の測定値として 22.8 ms から 21.2 ms を記載していますが、これは複数設定を含む測定であり、`STRATA_GR_FAST` 単独の効果とは扱えません (`docs/NVIDIA_V100.md:38-45,85-91`)。`docs/AMD_HIP.md` は hyper-connection read の fast kernel に対し `STRATA_GR_FAST=0` を従来構成として記載し、別の `STRATA_GR_SPLIT=1` については約 3% の per-window 測定と既定 OFF の理由を説明しています (`docs/AMD_HIP.md:500-501`)。`docs/DETAILS.md` に `STRATA_GR_FAST` の個別説明は見つかりませんでした。

## 根拠

- Build guard と kernel 宣言: `src/kernels/cuda/fused_gr.cu:28-33,988-994`
- fast/従来 norm/up の選択: `src/kernels/cuda/fused_gr.cu:1030-1046,1091-1096`
- 環境値の parse、優先順位、既定値: `src/kernels/cuda/fused_gr.cu:1813-1828`
- Q8/V3/split 経路の条件: `src/kernels/cuda/fused_gr.cu:1856-1866,1900-1929,1930-1953`
- 単一 token read: `src/kernels/cuda/fused_gr.cu:1969-1983`
- ベンチ用 setter: `include/strata/kernels/fused_gr.hpp:62-63`, `src/kernels/fused_gr_bench.cpp:89,105,136`
