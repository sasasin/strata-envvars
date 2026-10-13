# `STRATA_GDN_NOY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

AMD 向け GDN（gated-delta-net）prompt recurrence の特定経路で、正規化後の FP32 出力 `y` を書き込まず、後段が使う FP16 出力 `y16` だけを書きます。対象は `STRATA_GDN_HEAD` が選ぶ quad recurrence variant 1 です。CUDA の通常経路や、別 variant の正規化 kernel を切り替える変数ではありません。

## 値と判定

判定は `std::atoi(v) != 0` です。文字列全体の厳密な数値 parse ではなく、`atoi` が先頭から変換した整数が 0 かどうかで決まります。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効（FP32 の `y` も書く） |
| 空文字、数値に変換できない文字列、`0`, `00`, `0tail` | 無効 |
| `1`, `-1`, `2`, `1tail`, ` 1` | 有効 |

値の大文字小文字は関係しません。変数を読む値は variant 1 かつ `T > 0` の処理で初めて参照され、関数内の `static const bool` に保存されます。そのプロセスでは以後の環境変更は反映されません。根拠: `src/prefill/kernels.cu:1951-1966`、`sycl/src/prefill/kernels.dp.cpp:2627-2642`。

## 有効になる条件

通常の呼び出しで variant 1 を選ぶには、HIP ビルドで `STRATA_GDN_HEAD` が未設定でなく、`atoi` の結果が非 0 であること、かつ `STRATA_GDN_REC_HEADS` が未設定であることが必要です。`STRATA_GDN_REC_HEADS` は値の内容ではなく設定有無で serial 経路を選び、head variant を抑止します。`STRATA_GDN_HEAD` が未設定または 0 相当なら通常 variant 0 となり、この変数は参照されません。根拠: `src/prefill/kernels.cu:1996-2003`、`sycl/src/prefill/kernels.dp.cpp:2736-2743`。

Strata は AMD の gfx1151 と gfx12（gfx1200 / gfx1201）に対し、起動時の GPU 判定後、エンジンが各 switch を初めて読む前に、未設定なら `STRATA_GDN_HEAD=1` と `STRATA_GDN_NOY=1` を設定します。gfx1151 は `STRATA_GFX1151_DEFAULTS=0`、gfx12 は `STRATA_GFX12_DEFAULTS=0`（いずれも先頭文字が `0`）でそのアーキテクチャの既定値表全体を止められます。利用者が `STRATA_GDN_NOY` を何らかの値で設定済みなら、0 相当の値も含めて保持されます。これらの既定値は HIP ビルドの Strata 起動経路で適用され、他の AMD 世代や CUDA ビルドには適用されません。根拠: `src/core/arch_defaults.cpp:12-58,61-80`、`src/program/generate.cpp:2152-2158`、`sycl/src/program/generate.cpp:1970-1976`。

## 実行時の詳細

quad recurrence variant 1 は、再帰計算後に grid-stride の出力正規化 kernel を実行します。通常（無効時）は `v = bp * sg` を計算し、FP32 の `y[at]` と FP16 の `y16[o16]` を書きます。有効時は `y[at]` の store を省き、`v_fma_mixlo_f16` 命令で積を FP16 に丸めて `y16[o16]` のみを書きます。`bp`、sigmoid `sg`、出力添字、FP16 出力先は同じです。ソースコメントは FP32 `y` の値は後段が読まず、16K chunk あたり 403 MB の不要な書き込みになると説明しています。根拠: `src/prefill/kernels.cu:1436-1470`、`sycl/src/prefill/kernels.dp.cpp:1608-1640`。

通常の公開関数 `gdn_recurrence()` は `STRATA_GDN_HEAD` と `STRATA_GDN_REC_HEADS` から variant を選び、variant 1 に限ってこの設定を分岐に使います。`T <= 0` の場合は variant 1 内の正規化処理と本変数の読み取りを行いません。旧式/診断用 variant 3～5 の出力正規化は `gdn_out_norm_loop_kernel<true>` を直接起動するため、本変数の分岐を通りません。根拠: `src/prefill/kernels.cu:1932-1949,1951-1969,1996-2003`、`sycl/src/prefill/kernels.dp.cpp:2603-2625,2627-2646,2736-2743`。

## ログ・資料との照合

この変数自身によるログ出力はありません。gfx1151 / gfx12 のアーキテクチャ既定値が何かを設定した起動では、共通の起動ログ `strata: ... exact speed switches on by default ...` が設定した switch 名を列挙します。利用者がこの変数を事前設定した場合、既定値適用処理はその名前を設定済みリストに追加しません。根拠: `src/core/arch_defaults.cpp:61-80`。

`docs/STRIX_HALO.md` は gfx1151 でこの変数を含む prompt GDN 最適化群が既定 ON と記し、保守側の環境では同一出力だったと説明しています。同文書は CUDA と他の AMD 世代には適用されないとも述べます。ソース上はこの変数が FP32 store を省略し、FP16 `y16` を出力することを確認できますが、資料にある出力一致の範囲を他の環境へ一般化はできません。根拠: `docs/STRIX_HALO.md:83-97`。

## 根拠

- `src/prefill/kernels.cu:1436-1470,1951-1969,1996-2003` — CUDA/HIP 共通ソース内の AMD quad norm 分岐、値の判定、variant 選択。
- `sycl/src/prefill/kernels.dp.cpp:1608-1640,2627-2646,2736-2743` — SYCL 側の同等実装。
- `src/core/arch_defaults.cpp:12-58,61-80` — gfx1151 / gfx12 の既定値表と、利用者設定の保持・起動ログ。
- `src/program/generate.cpp:2152-2158`、`sycl/src/program/generate.cpp:1970-1976` — HIP 起動時の既定値適用。
- `docs/STRIX_HALO.md:83-97` — gfx1151 既定値と出力一致についての資料。
