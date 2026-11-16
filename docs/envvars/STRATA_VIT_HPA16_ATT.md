# `STRATA_VIT_HPA16_ATT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP ビルドの自前 GPU vision tower で、attention の P×V 積を float32 出力の代わりに F16 出力で計算し、計算後に float32 へ widen する経路を選びます。P と V はどちらも F16、積の accumulation は float32 です。score 積 S の経路や重み積の切替はこの変数の対象ではありません（`tools/vision/own/vit_gpu.cu:624-630,648-659`）。

## 値と判定

`VitGpu::load()` 内で `std::getenv` が null でないときだけ `std::atoi(e) != 0` を代入します。文字列全体の検証や範囲検査はなく、`atoi` が先頭から変換した整数がゼロ以外なら ON、ゼロなら OFF です。従って空文字・非数値文字列・`0`・`0anything` は OFF、`1`・`-1`・`1anything` は ON です。先頭空白や符号は `atoi` の整数変換規則に従い、大文字小文字の比較はしません。整数として変換できない文字列は 0 になります。範囲外の数値に対する `atoi` の結果はコードで検査されません（`tools/vision/own/vit_gpu.cu:940-941`）。

| ビルド・GPU | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP (`STRATA_VIT_HIP`)、gfx1151 | ON（`VitGpu::load()` が true に初期化） | `atoi` 結果が非ゼロ | `atoi` 結果が 0 |
| HIP、gfx1151 以外 | OFF（初期値 false） | `atoi` 結果が非ゼロ | `atoi` 結果が 0 |
| CUDA / SYCL / CPU のみ | この変数を読む処理なし | 該当なし | 該当なし |

gfx1151 での既定 ON と環境値による上書きは `tools/vision/own/vit_gpu.cu:911-925,939-944`、HIP 条件付きコンパイルと CUDA/HIP のビルド設定は `tools/vision/own/vit_gpu.cu:648-660`、`tools/vision/own/CMakeLists.txt:120-135` にあります。

## 有効になる条件

- `strata-vision` の自前 tower (`--tower own`、または `--tower auto` が own を選ぶ場合) を GPU (`--gpu`) で実行し、そのビルドが HIP である必要があります。CPU tower では GPU 実装を作らず、CUDA・SYCL にはこの変数を読む箇所がありません（`tools/vision/strata_vision.cpp:137-170`、`tools/vision/own/own_reader.cpp:114-125`、`tools/vision/own/CMakeLists.txt:120-135`）。
- `--tower auto` は mmproj と backend で own tower が利用可能な場合に own を選びます。GPU で未対応 geometry または head dimension が 96 を超えると own GPU 読み取りは不可となり mtmd 側が選ばれ得ます。その場合この変数は評価されません。明示した `--tower own` は選択を維持し、起動失敗はエラー経路になります（`tools/vision/own/own_reader.cpp:49-72,84-87`、`tools/vision/strata_vision.cpp:137-175`）。
- 値が ON でも、P×V の呼び出しが float32 出力・F16 入力・バッチ配置条件を満たし、作業領域の範囲内である必要があります。条件を満たさない呼び出しは通常の float32 出力経路を使います（`tools/vision/own/vit_gpu.cu:648-665`）。
- hipBLASLt がビルドに含まれ、`STRATA_VIT_LT_ATT` が非ゼロなら、対象積で hipBLASLt が成功した場合はその結果を先に採用し、HPA16_ATT 分岐を通りません。hipBLASLt がない場合、同変数が無効の場合、またはその積を処理できず `lt_mm` が false を返した場合は、この HPA16_ATT 分岐が選択され得ます（`tools/vision/own/vit_gpu.cu:483-487,645-659`、`tools/vision/own/CMakeLists.txt:132-136`）。
- `STRATA_VIT_HPA16` は重み積用の別スイッチです。P×V 用の `hpa16_att` とは別に設定され、重み積の値をこの変数が上書きすることはありません（`tools/vision/own/vit_gpu.cu:630,940-944,752-765`）。

## 実行時の詳細

変数は `VitGpu::load()` の HIP 部分で、GPU の gfx1151 判定による既定値設定後に一度読みます。未設定なら既定値を保ち、設定ありなら `atoi` の結果で上書きします。値は `VitGpuImpl::hpa16_att` に保持され、その後の各画像リクエストで環境を読み直しません（`tools/vision/own/vit_gpu.cu:895-925,939-944`）。

バッファ確保では ON のとき `N * D` 要素の F16 P×V 出力領域 `d_pv16` を追加します。該当する batched product は `d_pv16` に F16 出力・float32 accumulation で計算し、`k_widen16` で float32 の出力先へ戻します。したがってこのスイッチが変えるのは中間積の丸め形式と追加 GPU 作業領域であり、同一の vision 出力や後続の生成 token が保たれることはこのコードだけでは保証されません（`tools/vision/own/vit_gpu.cu:648-659,809-814`）。

追加バッファの `cudaMalloc` が失敗すると `alloc()` が `GPU memory: <CUDA/HIP runtime error>` をエラー文字列にして失敗します。own tower の GPU `load()` 失敗は `own_reader_run()` から起動失敗になります。`--tower auto` が own を選び、かつ `--model` が指定されている場合は READY 前の失敗理由を stderr に出して llama.cpp/mtmd の reader へ fallback します。明示 `--tower own` など fallback 用 `start_error` がない場合は reader が `ERR ...` を stdout に出します（`tools/vision/own/vit_gpu.cu:676-684,809-814,895-1009`、`tools/vision/own/own_reader.cpp:89-110,118-125`、`tools/vision/strata_vision.cpp:137-175`）。

## ログと測定値

HPA16 系のいずれか（重み積または attention P×V 積）が有効な場合、stderr に `vit-hpa16: 16-bit results with float32 accumulation for ...` を出します。この変数だけが ON なら末尾は `the attention's P*V product` です。どちらも OFF ならこのログは出ません（`tools/vision/own/vit_gpu.cu:942-944`）。

`docs/DETAILS.md` とこの checkout 内の測定レポートから、この環境変数単独の有効・無効比較と条件を確認できる測定値は見つかりませんでした。ソースコメントには gfx1151 の HPA16 全般について Strix Halo 上の比較値がありますが、HPA16_ATT 単独の結果とは区別できないため、ここでは本変数の測定値として記載しません（`tools/vision/own/vit_gpu.cu:912-918`）。

## 根拠

- 値の読み取り、既定値、診断ログ: `tools/vision/own/vit_gpu.cu:911-925,939-944`
- P×V の型・形状ガード、積、float32 への widen: `tools/vision/own/vit_gpu.cu:642-665`
- 追加 GPU バッファと割当失敗: `tools/vision/own/vit_gpu.cu:676-684,809-814`
- own tower の選択、GPU load、fallback / ERR 経路: `tools/vision/own/own_reader.cpp:49-72,84-125`、`tools/vision/strata_vision.cpp:137-175`
- HIP のみで `vit_gpu.cu` をビルドする条件: `tools/vision/own/CMakeLists.txt:120-136`
