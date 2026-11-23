# `setup.sh --image-vae`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.sh`（Linux）/ `START-HERE.bat` / `UPDATE.bat` → `terminal/setup.py` |
| オプション | `--image-vae` |
| 別名 | なし |
| 値 | `on` または `off`。値を取る。 |

## 役割

`--images qwen-image` で画像生成をセットアップするとき、stable-diffusion.cpp の `sd-cli` に Strata 独自の VAE decoder を組み込むか指定します。`on` は CUDA / ROCm (HIP) バックエンドで decoder を組み込み、画像生成時に使用する設定を保存します。Vulkan / CPU では組み込み対象外で、警告を出して stable-diffusion.cpp 標準 decoder を使います。

## 使い方

```sh
# Linux の setup.sh から、画像生成と Strata の VAE decoder を設定
./setup.sh --images qwen-image --image-vae on
```

このオプションは setup の `--help` には表示されない preview 機能の引数です。`terminal/setup.py` の parser には登録されています（`terminal/setup.py:11252-11264`）。

## 値と既定値

- parser は `on` と `off` のみを受理します。それ以外の値は choices 制約に反します（`terminal/setup.py:11263-11264`）。
- 省略時の値は `None` で、`setup_images` は `on` と等しい場合だけ有効として扱います。したがって省略時と `off` は、どちらも Strata decoder を要求しません（`terminal/setup.py:5913-5918`）。
- `--images qwen-image` を指定しない場合、設定組み立て側は `setup_images` を呼ばず、この値は使用されません。画像設定が既存構成から引き継がれる場合もあります（`terminal/strata_control/setup_config.py:574-575`）。

## 実行時の動作

`--image-vae on` かつ画像生成のセットアップが進むと、選択された backend が VAE 対応 backend かを確認します。対応集合は `NATIVE_BACKENDS` と同じで、ソースコメント上 CUDA / HIP 向けです（`terminal/tools/image/qimage.py:199-200`）。非対応なら警告し、要求値を無効化して標準 decoder のまま続けます（`terminal/setup.py:5913-5919`）。

CUDA / HIP で有効な場合、`build_image_engine` は VAE ソースの fingerprint をビルド stamp に含めます。既存 `sd-cli` と stamp が一致すれば再利用し、一致しなければ stable-diffusion.cpp のソースを取得または再利用して VAE decoder を適用し、`sd-cli` をビルドします（`terminal/setup.py:5816-5837`; `terminal/tools/image/qimage.py:220-232`）。適用処理は Strata の decoder ソースとヘッダーを第三者ソースツリーへコピーし、CUDA / HIP 用ライブラリを組み込むものです（`terminal/tools/image/sdcpp_vae/apply.py:1-16,27-36`）。

ビルド後の画像設定には `vae_decoder: "strata"` が入り、そうでなければこのキーは省略されます（`terminal/tools/image/qimage.py:235-248`）。画像生成リクエストを実行するとき、serve 側はその値に応じて `--model-args strata_vae=1` を `sd-cli` に渡します（`terminal/serve/images.py:165-173`）。decoder の実行条件は Qwen-Image 2.1 の画像経路です。VAE ファイルを開けない、または decoder が失敗する場合、標準 decoder に fallback します（`terminal/tools/image/sdcpp_vae/apply.py:13-16,47-59`）。

画像生成をセットアップする場合、モデルファイル（選択 quant、VAE、LLM）はこのフラグの on/off にかかわらず取得・SHA-256 検証されます（`terminal/setup.py:5907-5924`）。画像生成への同意プロンプトで拒否すると `setup_images` は設定を返さず、decoder のビルドには進みません（`terminal/setup.py:5908-5909`）。

## 適用条件と副作用

- 有効な Strata decoder は CUDA / HIP ビルドに限られます。Vulkan / CPU では警告後、標準 decoder に切り替わります（`terminal/setup.py:5915-5919`; `terminal/tools/image/qimage.py:199-200`）。
- 必要な場合は画像生成用 `sd-cli` のコンパイルが発生します。CUDA Toolkit が見つからない場合、setup は案内を表示して終了コード 1 で停止します（`terminal/setup.py:5838-5844`; `terminal/setup.py:1049-1056`）。
- 第三者ソースがまだなければ stable-diffusion.cpp と ggml の pinned zip をダウンロードして展開します。画像モデルも別途ダウンロードされます（`terminal/setup.py:5727-5746,5920-5924`）。

## 出力とエラー

- 非対応 backend で `on` を指定したときは `[!]` 形式の警告を標準出力に出し、標準 decoder で続行します（`terminal/setup.py:5915-5918,1044-1046`）。
- CUDA Toolkit 不足など `fail()` 経由のエラーは標準出力に `[X]` と案内を出し、終了コード 1 で停止します（`terminal/setup.py:5840-5844,1049-1056`）。
- Strata decoder 自体の初期化・decode 失敗時は `sd-cli` が警告をログに記録し、標準 decoder へ切り替えます（`terminal/tools/image/sdcpp_vae/apply.py:53-59,61-75`）。

## 根拠

- `terminal/setup.py:11252-11264` — preview 用の hidden parser 登録と `--image-vae` の choices。
- `terminal/strata_control/setup_config.py:574-575` — `--images` 指定時のみ画像セットアップ関数へ渡す。
- `terminal/setup.py:5898-5929` — 値の判定、非対応 backend の fallback、ビルド・モデル取得・設定生成。
- `terminal/setup.py:5816-5837,5838-5879` — stamp 判定、decoder 適用、コンパイルと失敗経路。
- `terminal/tools/image/qimage.py:199-200,220-248` — backend 対応集合、stamp と実行設定への反映。
- `terminal/serve/images.py:165-173` — `vae_decoder` 設定を `sd-cli` の `strata_vae=1` 引数へ変換。
- `terminal/tools/image/sdcpp_vae/apply.py:1-16,27-59` — 適用対象と decoder の fallback 条件。
