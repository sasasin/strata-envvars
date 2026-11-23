# `setup.py --image-backend`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（root） |
| オプション | `--image-backend` |
| 別名 | なし |
| 値 | `cuda`、`hip`、`vulkan`、`cpu` のいずれか |

## 役割

`--images qwen-image` で有効にする画像生成用 `sd-cli` のビルド backend を指定します。setup が GPU から自動選択する backend を上書きします。画像生成を指定しない実行では、この値を使う処理に入りません。

## 使い方

```sh
# 画像生成エンジンを CPU backend で設定する（モデル取得の確認が表示される）
./setup.sh --images qwen-image --image-backend cpu
```

## 値と既定値

parser は `cuda`、`hip`、`vulkan`、`cpu` のみを受理します。`argparse` の `choices` による検証で、別の値を渡すと引数エラーになります（`terminal/setup.py:11257-11258`）。値の省略時は `None` となり、setup が検出した GPU と OS から自動選択します。明示値と GPU の組み合わせを事前に照合して拒否する処理は見当たりません（`terminal/setup.py:5883-5895`）。

| 値 | ビルド設定 |
| --- | --- |
| `cuda` | CUDA 用。GPU の architecture をビルド設定に渡します。 |
| `hip` | HIP 用。GPU の architecture と ROCm 環境を使います。 |
| `vulkan` | Vulkan 用。SDK またはシステムの Vulkan 開発ファイルを使います。 |
| `cpu` | GPU backend を有効にしない CPU 用。 |

## 実行時の動作

このオプションは parser では受理されますが、画像生成設定の処理は `--images` が指定された場合だけ呼び出されます。`--images qwen-image` のとき、setup は明示値を自動選択結果より優先し、選んだ backend に合わせて `sd-cli` をビルドまたは既存ビルドを再利用します。backend は run config の `images.backend` に記録され、server の画像生成処理で参照されます（`terminal/strata_control/setup_config.py:574-576`、`terminal/setup.py:5883-5895,5901-5905,5816-5830`、`terminal/tools/image/qimage.py:235-253`）。

明示値を省略した場合の自動選択は、GPU がなければ `cpu`、NVIDIA なら `cuda`、AMD なら APU または Windows で `vulkan`、それ以外の AMD で `hip`、その他の vendor で `vulkan` です（`terminal/tools/image/qimage.py:88-98`）。

画像生成の設定へ進むと、setup は確認後に選択 backend のビルドを行い、必要な画像モデルファイルを取得・検証して run config に設定します。確認への回答が「いいえ」の場合はこの設定関数から戻り、ビルドやモデル取得を行いません（`terminal/setup.py:5898-5929`）。Vulkan 開発ファイルが Linux にない場合は SDK を `third_party/` に展開し、Windows では SDK がないと停止します（`terminal/setup.py:5750-5780`）。

## 適用条件と副作用

- `--images qwen-image` がなければ `setup_images` は呼ばれず、`--image-backend` は画像設定に反映されません。`--images no` の場合も画像設定関数は `None` を返します（`terminal/strata_control/setup_config.py:574-575`、`terminal/setup.py:5901-5902`）。
- `cuda` は CUDA Toolkit の `nvcc` が見つからないと setup を終了します。`hip` は検出済み GPU architecture と ROCm を使い、`vulkan` は Vulkan SDK / 開発ファイルを必要とします。`cpu` は CPU backend の CMake 定義を選びます（`terminal/setup.py:5838-5869`、`terminal/tools/image/qimage.py:116-140`）。
- ビルドでは `build-image-<backend>/` を使い、成果物を `engine-image/` に配置します。Linux の Vulkan SDK が必要な場合はダウンロードと展開も発生します（`terminal/setup.py:5763-5780,5816-5829,5870-5879`）。
- 選択 backend と必要なモデルパスはモデルの run config に保存されます。画像モデルの取得前に空き容量の警告を出す場合があります（`terminal/setup.py:5905-5928`）。

## 出力とエラー

選択内容は `Image generation: Qwen-Image-2.1-Turbo ... on <backend>` として表示されます。CUDA Toolkit 不足、Windows での Vulkan SDK 不足、またはビルド後に `sd-cli` が見つからない場合は `fail()` 経由で setup が停止し、終了コード 1 になります（`terminal/setup.py:5840-5844,5874-5879,5905`、`terminal/setup.py:1049-1056`）。HIP の ROCm 検出やビルド失敗など、それ以外の全ての失敗条件・終了コードはこのオプション単独の経路としては確認できません。

## 根拠

- `terminal/setup.py:11252-11258` — `--images` と `--image-backend` の parser 定義、choices、および通常の help から隠す設定。
- `terminal/strata_control/setup_config.py:574-576` — `--images` が指定された時だけ画像設定を呼び出す条件。
- `terminal/setup.py:5883-5895`、`terminal/tools/image/qimage.py:88-98` — 明示値の優先と未指定時の自動選択。
- `terminal/setup.py:5816-5879,5898-5929`、`terminal/tools/image/qimage.py:116-140,235-253` — backend ごとのビルド処理、モデル設定、run config に記録する値。
