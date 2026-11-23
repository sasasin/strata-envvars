# `--images`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（モデルの setup。`setup.sh` / `START-HERE.bat` などから委譲） |
| オプション | `--images` |
| 別名 | なし |
| 値 | `qwen-image` または `no` |

## 役割

モデルの run config に画像生成設定を追加するか、設定を外すかを選びます。`qwen-image` は Qwen-Image-2.1-Turbo 用の `sd-cli` を選択 backend 向けに準備し、モデルファイルを取得・検証して、`serve/images.py` が読む `images` セクションを設定します。これはチャット入力画像の読取りを制御する `--vision` とは別機能です（parser の登録: `terminal/setup.py:11245-11254`、設定組立て: `terminal/strata_control/setup_config.py:561-575`）。

## 使い方

Strata の checkout ルートで実行します。初回は確認プロンプトがあり、`--yes` を付けると推奨回答として承認されます。

```sh
# 画像生成を構成し、モデルの起動は行わない
./setup.sh --setup --images qwen-image --no-start

# 既存の画像生成設定を外す
./setup.sh --setup --images no --no-start
```

Windows では `START-HERE.bat` を使えます。`--images` は `setup.py` に登録され、同じトップレベル scope の setup ラッパーから委譲されます（`docs/cli/README.md` の `source-setup` 節、`docs/cli/000_cli_tools.md:15`）。

## 値と既定値

- `qwen-image`: Qwen-Image-2.1-Turbo の画像生成設定を作ります。
- `no`: setup 処理で `images` セクションを削除します。
- 省略時は parser の値が `None` です。config 組立て側はこの場合 `images` を書き換えず、以前の設定があれば `carry_over` で維持します（`terminal/setup.py:11253-11254`、`terminal/strata_control/setup_config.py:574-575`、`terminal/setup.py:7473-7484`）。
- それ以外の値は `argparse` の `choices` により拒否されます。独自の alias や空値の補正はありません（`terminal/setup.py:11253-11254`）。

## 実行時の動作

`qwen-image` を指定すると、setup は backend と denoiser の量子化を選び、確認後に `sd-cli` をビルドまたは既存 build を再利用します。CUDA/HIP/Vulkan/CPU の選択処理は `terminal/setup.py:5883-5895` と `terminal/tools/image/qimage.py:65-104` にあります。GPU memory が 8 GB 以下なら `Q4_K_M`、12 GB 以下なら `Q6_K`、それより大きければ `Q8_0` を推奨し、CPU では `Q4_K_M` です。明示した `--image-quant` が推奨より大きい場合は警告して選択を維持します。`--image-backend`、`--image-quant`、`--image-gpu-policy` と、native/noise/VAE の各 image option は同じ parser にあります（`terminal/setup.py:11255-11266`）。

確認に `n` と答えると画像用の設定生成を中止し、`None` が config に渡されます。`y`（既定）または `--yes` の場合、`engine-image/` に `sd-cli` と `BUILD.json` を作成・更新し、選んだ denoiser、VAE、text encoder を data folder 内の `models/qwen-image-2.1-turbo/` に取得して SHA-256 を検証します。その後、実行ファイル、backend、model file のパスなどを含む `images` セクションを返します（`terminal/setup.py:5898-5929`、`terminal/setup.py:5816-5879`、`terminal/tools/image/qimage.py:235-253`）。このセクションは画像生成 API の処理が参照します（`terminal/serve/images.py:20`）。

`no` のとき helper は `None` を返し、保存前に `write_setup_config` が `images` キーを取り除きます。設定ファイルが変更される場合、以前のファイルは `.bak` として保持されます（`terminal/setup.py:5898-5903`、`terminal/setup.py:7631-7664`）。

## 適用条件と副作用

- `qwen-image` は setup のモデル設定経路で処理されます。確認を断れば画像設定の build/download は行われません（`terminal/strata_control/setup_config.py:574-575`、`terminal/setup.py:5904-5919`）。
- 画像生成の build が無効な CUDA/HIP/Vulkan SDK 環境では、必要な build tool の取得・利用またはコンパイルが必要です。CUDA で `nvcc` が見つからない場合は失敗し、Vulkan では必要に応じて SDK を `third_party/` に取得します（`terminal/setup.py:5731-5746`、`terminal/setup.py:5760-5785`、`terminal/setup.py:5838-5879`）。
- 画像モデル3ファイルのダウンロードでネットワークエラー、サイズ不一致、または pinned SHA-256 不一致が起きると setup は失敗します。不一致ファイルは `.bad` に保持され、再実行を案内します（`terminal/setup.py:5920-5924`、`terminal/setup.py:3471-3539`、`terminal/setup.py:3772-3825`）。
- 画像モデルは Qwen Research License の対象で、setup はライセンス案内を表示します（`terminal/setup.py:5905-5908`、`terminal/tools/image/qimage.py:58-60`）。
- `--help` にはこのオプションは表示されません。parser の help が `argparse.SUPPRESS` です（`terminal/setup.py:11252-11254`）。

## 出力とエラー

setup は画像モデルの容量を表示して確認を求め、build/download の進捗、成功表示、量子化推奨との差の警告を出します（`terminal/setup.py:5905-5929`、`terminal/setup.py:5883-5895`）。無効な値は `argparse` の usage error（終了コード 2）になります。画像モデル取得や engine 準備で setup が `fail()` した場合、エラー案内を出して終了コード 1 です（`terminal/setup.py:1049-1056`）。

## 根拠

- `terminal/setup.py:11252-11266` — `--images` と関連 image option の parser、choices、既定値、help 非表示。
- `terminal/strata_control/setup_config.py:202`、`terminal/strata_control/setup_config.py:574-575` — setup config が `setup_images` を呼び出す条件。
- `terminal/setup.py:5883-5929` — backend/quant 選択、同意確認、build・download・検証、設定生成。
- `terminal/tools/image/qimage.py:43-71`、`terminal/tools/image/qimage.py:88-104`、`terminal/tools/image/qimage.py:235-253` — model file pin、quant/backend 選択、run config の `images` 構造。
- `terminal/setup.py:7631-7664` — config の carry-over、`None` の削除、backup と書き込み。
- `terminal/setup.py:3471-3539`、`terminal/setup.py:3772-3825` — download と SHA-256 検証の失敗経路。
- `terminal/serve/images.py:20` — serve 側が読む設定セクション。
