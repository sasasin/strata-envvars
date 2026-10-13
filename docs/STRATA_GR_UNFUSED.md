# `STRATA_GR_UNFUSED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

GPU の prompt prefill にある hyper-connection（HC）読み取りで、正規化後の FP32 行 `xn` を明示的に作って保持し、`gr_mix` で使う経路を選びます。ソースコメントでは F-1 の「A/B arm」とされています。通常経路は `gr_norm_rs` で行スケールと BF16 表現を作り、`gr_mix_r` が残差 `R`・行スケール・norm 重みから FP32 値を再計算して混合します。

## 値と判定

CUDA/HIP 実装と SYCL 実装のどちらも、`getenv()` の戻り値が null でなく、先頭文字が `'1'` のときだけ有効です。文字列全体の parse や数値変換はしません。

| 環境変数値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1`、`10`、`1anything` | 有効 |
| `0`、`true`、` 1`、その他先頭文字が `1` でない値 | 無効 |

大文字小文字、後続文字、数値としての妥当性は判定に影響しません。各実装で判定結果を関数内の `static const bool` に保存するため、最初に `gr_unfused()` が呼ばれた後の環境変更は反映されません。呼び出し元にはバッファサイズ計算と prefill バッファ確保が含まれるので、必ずしも最初の prompt 計算時に初めて評価されるとは限りません。

根拠: `src/prefill/prefill.cpp:361-365,1207-1216,1830-1849`、`sycl/src/prefill/prefill.cpp:296-300,1151-1159,1862-1881`。

## 有効になる条件

- CUDA/HIP ビルドでは `src/prefill/prefill.cpp`、SYCL ビルドでは `sycl/src/prefill/prefill.cpp` に実装があります。どちらも `Prefill` の GPU prompt prefill 内で判定します。通常の decode やサーバー全般の設定ではありません。
- 実際の計算への効果があるのは、この `Prefill` 経路で HC 読み取りを実行する場合です。prefill が別経路に進む場合、この分岐は通りません。
- この変数専用の警告・有効化ログや CLI 優先順位はありません。関連する最適化も抑制します。HC の入力 stride padding (`hc_pad()` が成立する場合) はこの設定下では選ばれず、`hc_upmix()` 経路も条件から除外されます。また、control vector の fused write と、通常の HC write と次 half の norm をまとめる融合も無効になります。

根拠: `src/prefill/prefill.cpp:2544-2547,2567-2568,3930-3938,3975-3988`、`sycl/src/prefill/prefill.cpp:2813-2816,2836-2837,4298-4310`。

## 実行時の詳細

有効時は `Prefill::carve()` が chunk ごとに `T * D` 個の FP32 `xn` バッファを確保します。HC 読み取りごとに `gr_norm()` が残差 `R` と `hc_attn_norm.weight` または `hc_ffn_norm.weight` から正規化結果を FP32 `xn` と BF16 `xn16` に書き込みます。down projection は BF16 側を使い、up projection と injection の後、`gr_mix()` が保持した FP32 `xn` と gate の sigmoid を掛けて HC 数で平均し、`mixed` を作ります。

無効時は FP32 `xn` を確保せず、`gr_norm_rs()` が BF16 `xn16` と行スケール `grs` を作ります。通常の混合では `gr_mix_r()` が `R * rs * norm_weight` を再計算して gate と混ぜます。カーネルコメントは、この再計算値が `gr_norm` の値と同じ順序・同じビットになると説明しています。設定を有効にすると少なくとも `4 * T * D` bytes の FP32 `xn` バッファが追加されます。

有効時に fused write/norm が止まるため、通常は HC write の後で次の norm を別途行います。コードにこの環境変数の専用ログはありません。`docs/DETAILS.md` および docs 内にこの変数の説明や測定値は見つからず、性能・出力同一性を資料から確認できる根拠はありません。

根拠: `src/prefill/prefill.cpp:361-365,1207-1216,2542-2548,2593-2601,3926-3988`、`src/prefill/kernels.cu:78-115,116-137,247-267,1835-1850,1890-1893`。対応する SYCL 経路: `sycl/src/prefill/prefill.cpp:296-300,1151-1159,2811-2817,2876-2884,4295-4310`、`sycl/src/prefill/kernels.dp.cpp:2278-2338,2434-2450`。

## 根拠

- 環境変数の全読み取り箇所は `src/prefill/prefill.cpp:363` と `sycl/src/prefill/prefill.cpp:298` です。リポジトリ内の他の本番ソースに直接参照はありません。
- CUDA/HIP 側の割り当て、条件分岐、値の混合は `src/prefill/prefill.cpp:1207-1216,2542-2601`、カーネル実装は `src/prefill/kernels.cu:78-137,247-267` です。
- SYCL 側にも同じ判定と prefill 分岐があり、対応する kernel wrapper は `sycl/src/prefill/kernels.dp.cpp:2278-2338,2434-2450` です。
