# `STRATA_VIT_NO_MPP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Metal 版 own vision tower が Metal 4 の tensor-op 製品を使わず、plain kernel を使うための診断用スイッチ。`VitGpu::load` がこの変数を設定有無で判定し、設定されていれば tensor-op 用 Metal library のコンパイルと製品ごとの自己検査を行わず、BF16/F16 重み積・attention の S・P*V の全てで plain 経路を選ぶ。通常の画像エンコード自体を無効化する変数ではない。`tools/vision/own/vit_metal.mm:404-431, 238-243, 549-566`。

## 値と判定

| 条件（build など） | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `tools/vision/own/vit_metal.mm` を含む Metal own-tower build | tensor-op library のコンパイルを試みる（Metal 4 対応・コンパイル成功時に製品別自己検査へ進む） | 値を問わず、環境変数が存在すること。`1`、`0`、`true`、空文字、`0anything` はいずれも plain kernel を指定する | 該当なし。文字列の解析・数値変換・大小文字比較はしない |
| CPU tower、CUDA/HIP/SYCL の own tower、Metal を含まない build | この実装での効果なし | 該当なし | 該当なし |

実装は `std::getenv(...) != nullptr` 相当の有無判定であるため、未設定だけが false。空文字も設定ありとして扱い、空白を含む値や無効な数値文字列も拒否しない。CLI 引数による値の上書きや fallback はない。`tools/vision/own/vit_metal.mm:406-416`。

## 有効になる条件

- Metal own-tower 実装がビルドに含まれていること。CMake では Apple 上で `STRATA_VIT_OWN_METAL` または `STRATA_VISION_METAL` が有効な場合に `vit_metal.mm` を追加し、`STRATA_VIT_GPU` / `STRATA_VIT_METAL` を定義する。`tools/vision/own/CMakeLists.txt:56-68, 157-163`。
- GPU 経路を使うこと。`strata-vision` では `--gpu` が必要で、own tower が選択される必要がある。`--tower own` は明示選択、`--tower auto` は `own_reader_supported` が適合と判断した場合に選択し、それ以外は mtmd を選ぶ。`--tower` が省略されたときの初期値には `STRATA_VISION_TOWER` が関係する。`tools/vision/strata_vision.cpp:90-112, 137-164`; 適合判定は `tools/vision/own/own_reader.cpp:49-72, 84-87`。
- 単独の `strata-vision-own` でも `--gpu` を指定すると同じ own GPU reader を通る。`tools/vision/own/own_main.cpp:1-31`; build target は `tools/vision/own/CMakeLists.txt:157-169`。
- GPU own tower の `VitGpu::load` まで到達すること。Metal device がない場合やモデル読込などで先に失敗すれば、カーネル選択は行われない。`tools/vision/own/own_reader.cpp:114-125`。
- Metal 4 対応、製品別 self-test の成功、または個別の `STRATA_VIT_NO_MPP_W` / `_S` / `_PV` の指定が tensor-op の可否に関係する。ただし本変数が設定されると Metal 4 の判定結果に関わらず MPP 用ライブラリをコンパイルせず、全製品を plain にする。個別の suffix 変数は各製品を無効化するだけで、本変数を再有効化しない。`tools/vision/own/vit_metal.mm:406-428`。
- `--tower auto` で own tower の起動前に失敗すると mtmd に fallback する場合がある。明示 `--tower own` では `own_reader_run` のエラーが `ERR ...` と終了コードとして返る。`tools/vision/strata_vision.cpp:137-175`; `tools/vision/own/own_reader.cpp:92-110, 116-125`。

## 実行時の詳細

変数を読むのは `VitGpu::load` のカーネル初期化時で、Metal の通常 kernel library をコンパイルした後、MPP library のコンパイル前である。関数呼び出しごとに読み、static cache はない。own reader は GPU reader の起動時に `load` し、`READY` を返す前に warm-up するため、同じ reader の読み取り後に環境を変えても既に決定した製品フラグには反映されない。reader を再起動して `load` を再実行すれば、その時点の環境が評価される。`tools/vision/own/vit_metal.mm:368-416`; `tools/vision/own/own_reader.cpp:116-125, 151-169`。

設定時は `mpp_why` に `STRATA_VIT_NO_MPP` を記録し、MPP library のコンパイルと `mpp_check` 呼び出しを迂回する。ログ後、`wgemm` は `vk_gemm_f16` / `vk_gemm_bf16` を選び、S と P*V はそれぞれ `vk_gemm_s` / `vk_gemm_pv` を使う。画像の GPU エンコードは続行される。`tools/vision/own/vit_metal.mm:404-431, 238-243, 549-566`。

## ログと測定値

`VitGpu::load` は stderr に次の形式で1回ログを出し、各製品は `plain (STRATA_VIT_NO_MPP)` と表示される（各製品専用の suffix 変数も設定されている場合、その製品の理由表示は suffix 名になる）。フラグによる専用の警告やエラー、終了はない。

```text
strata-vision: Metal tower on <device>; products: BF16 weights plain (STRATA_VIT_NO_MPP), F16 weights plain (STRATA_VIT_NO_MPP), attention S plain (STRATA_VIT_NO_MPP), P*V plain (STRATA_VIT_NO_MPP); patch matrix float32, one output a thread
```

ログの生成は `tools/vision/own/vit_metal.mm:425-431`。調査対象 checkout に `docs/DETAILS.md` はなく、この変数の効果に関する測定値もソースには見つからなかった。

## 根拠

- `tools/vision/own/vit_metal.mm:404-431` — 設定有無の判定、Metal 4 / MPP library 分岐、個別製品の自己検査と診断変数、stderr ログ。
- `tools/vision/own/vit_metal.mm:230-243, 549-566` — MPP フラグに応じた plain / tensor-op kernel 選択。
- `tools/vision/own/CMakeLists.txt:56-68, 157-163` — Metal 実装を含める build 条件。
- `tools/vision/strata_vision.cpp:90-112, 137-175`; `tools/vision/own/own_reader.cpp:49-72, 114-125, 151-169` — tower 選択、GPU load と起動経路。
