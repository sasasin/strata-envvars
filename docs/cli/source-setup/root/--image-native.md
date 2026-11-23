# `source-setup --image-native`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（セットアップ実行） |
| オプション | `--image-native` |
| 別名 | なし |
| 値 | `on` または `off` |

## 役割

画像生成をセットアップするとき、Strata 独自の Qwen-Image DiT runner を実行時に使うかを選びます。`on` は CUDA/HIP 用の画像生成設定に有効化を記録し、以後の画像生成で `sd-cli` にモデル引数を渡します。通常の画像読み取り (`--vision`) を切り替えるオプションではありません。

## 使い方

```sh
# Linux: Qwen-Image の生成を設定し、Strata の native runner を有効にする
./setup.sh --setup --images qwen-image --image-native on

# Windows: 同じ設定を行う
START-HERE.bat --setup --images qwen-image --image-native on

# runner を無効にして画像生成を設定する
./setup.sh --setup --images qwen-image --image-native off
```

## 値と既定値

- parser は `on` と `off` のみを受理します。値を省略したり、別の値を指定したりすると `argparse` の引数エラーになります（`terminal/setup.py:11259-11260, 11385`）。
- 宣言時に `default` を指定していないため、未指定時は `None` です。画像設定を作る箇所では値が厳密に `on` の場合だけ真となり、未指定と `off` はどちらも無効です（`terminal/setup.py:5925-5927`）。

## 実行時の動作

`--image-native` は `--images qwen-image` と組み合わせて使います。セットアップ設定組み立て処理は `a.images` が指定されたときだけ画像生成の設定関数を呼びます。画像モデルのダウンロードとセットアップへの同意後、`image_config` は CUDA/HIP backend の場合に `native` キーを真偽値で記録します。画像生成時にその値が真なら、Strata は `sd-cli` の `--model-args` に `qwen_image_2_1_native=1` を加えます（`terminal/strata_control/setup_config.py:574-575`; `terminal/setup.py:5901-5909, 5920-5927`; `terminal/tools/image/qimage.py:235-248`; `terminal/serve/images.py:149-174`）。

CUDA/HIP では `sd-cli` のビルド時に native runner のソースを組み込みますが、これは `--image-native on` の有無とは別です。実行時に runner を使うかどうかは上記の設定値で切り替わります（`terminal/setup.py:5828-5837`; `terminal/tools/image/qimage.py:169-170, 243-244`）。

## 適用条件と副作用

- `--images qwen-image` を指定しないと、画像設定関数は呼び出されず、このオプションの値は利用されません。画像生成を設定しない場合、関連する画像設定・ダウンロード・画像生成 engine のビルドもこの経路では行われません（`terminal/strata_control/setup_config.py:574-575`; `terminal/setup.py:5898-5902`）。
- 設定キー `native` が作られるのは CUDA/HIP backend のみです。Vulkan/CPU backend ではこの値から `native` キーは記録されず、`sd-cli` に native runner のモデル引数も渡りません（`terminal/tools/image/qimage.py:169-170, 243-244`; `terminal/serve/images.py:165-174`）。
- 画像生成セットアップを続ける場合、画像 engine のコンパイルと画像モデルファイルのダウンロードが行われます。画像設定を含む run config が既存内容から変われば、書き込み前に旧設定を `.bak` としてコピーします（`terminal/setup.py:5907-5927, 7653-7663`）。
- 画像生成機能は preview 扱いで、これらの image オプションは通常の `--help` に表示されません（`terminal/setup.py:11252-11260`）。

## 出力とエラー

`--image-native` 固有の成功メッセージや追加の失敗分岐は確認できませんでした。無効な値の拒否は `argparse` の parser 段階で発生します。画像モデルの取得・検証や engine build の失敗は、画像生成セットアップの後続処理で発生し得ますが、このオプション固有のエラーではありません（`terminal/setup.py:11259-11260, 5907-5927, 11385`）。

## 根拠

- `terminal/setup.py:11252-11260` — preview image オプション群と `--image-native` の choices。
- `terminal/setup.py:5898-5929` — 画像セットアップの条件、確認、ビルド・ダウンロード、および値の `native` への変換。
- `terminal/strata_control/setup_config.py:574-575` — `--images` 指定時だけ画像設定を組み立てる分岐。
- `terminal/tools/image/qimage.py:169-170, 235-248` — native runner 対応 backend と run config の `native` キー。
- `terminal/serve/images.py:149-174` — `native: true` を `sd-cli --model-args qwen_image_2_1_native=1` に反映する処理。
- `terminal/setup.py:7653-7663` — 空の画像設定の除去と変更時のバックアップ。
