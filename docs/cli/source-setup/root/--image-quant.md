# `--image-quant`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` などから委譲） |
| オプション | `--image-quant` |
| 別名 | なし |
| 値 | `Q4_K_M`、`Q6_K`、`Q8_0` のいずれか（必須） |

## 役割

画像生成機能 Qwen-Image-2.1-Turbo の denoiser（DiT）に使う GGUF 量子化を選びます。このオプションは parser では受理されますが、プレビュー機能のため通常の `--help` には表示されません。画像生成の有効化自体は `--images qwen-image` が担い、量子化指定だけでは画像生成を構成しません。(`setup.py:9096-9101`, `setup.py:5080-5087`)

## 使い方

Linux の source checkout で、セットアップ時に画像生成と量子化を指定する例です。

```sh
./setup.sh --setup --images qwen-image --image-quant Q6_K
```

`setup.sh` は引数を `setup.py` に渡します。Windows では `START-HERE.bat --setup --images qwen-image --image-quant Q6_K` を使えます。(`setup.sh:76`, `START-HERE.bat:48`, `docs/IMAGES.md:16-21`)

## 値と既定値

- 有効値は `Q4_K_M`、`Q6_K`、`Q8_0` です。値を省くと argparse の既定値 `None` となり、量子化選択時に GPU メモリ容量から推奨値を選びます。(`setup.py:9099-9100`, `tools/image/qimage.py:56,65-71`)
- 自動推奨は GPU メモリが 8 GB 以下なら `Q4_K_M`、8 GB 超〜12 GB 以下なら `Q6_K`、12 GB 超なら `Q8_0` です。選択 backend が CPU の場合は GPU 容量によらず `Q4_K_M` を推奨します。(`tools/image/qimage.py:65-71`, `setup.py:5069-5073`)
- 選択肢以外の値は argparse が拒否し、通常の usage/error 表示と終了コード 2 になります。重複して指定した場合の argparse の通常動作では最後の値が残ります。専用の追加 validation はありません。(`setup.py:9099-9100`, `setup.py:9212`)

## 実行時の動作

`setup.py` は `--image-quant` の値を `a.image_quant` に格納します。画像生成の設定処理が呼ばれると、`image_backend_choice()` が明示値を推奨値より優先し、`setup_images()` がその量子化名のファイルを選びます。さらに VAE とテキスト encoder を含む合計 3 ファイルをモデルディレクトリへダウンロードして SHA-256 を検証し、実行設定の `images` セクションに `quant` と denoiser のパスを書きます。(`setup.py:5065-5077`, `setup.py:5080-5104`, `tools/image/qimage.py:44-56,190-203`)

指定量子化が GPU 容量からの推奨より大きい場合も値は補正されず、そのまま使用されます。セットアップは推奨値と GPU 容量を示す警告を出し、コメント上は大きいモデルの一部が stable-diffusion.cpp により RAM に置かれ遅くなる可能性を説明しています。推奨以下の明示値について、この警告は出ません。(`setup.py:5072-5077`)

画像生成セクションは `--images` が指定された場合にのみ今回の設定で更新されます。`--images no` では設定値が `None` となり、設定書き込み時に `images` セクションを取り除きます。`--image-quant` だけを指定しても `a.images` が偽なら `setup_images()` は呼ばれず、この値は使われません。(`setup.py:5083-5084,10434-10436`, `setup.py:6666-6668`)

## 適用条件と副作用

- 通常の `setup.py` parser ではこのオプションを受理しますが、画像生成の選択肢はプレビュー扱いで `--help` に隠されています。画像生成を構成する際には `sd-cli` のビルド、モデルファイルのダウンロード、run config の更新が行われます。ディスク空き容量が必要量 + 5 GB 未満でも処理は拒否されず、ダウンロードが容量不足になる可能性を警告します。(`setup.py:9096-9101`, `setup.py:5087-5104`)
- `--image-backend cpu` などで backend を明示した場合、量子化の推奨容量計算は選択 backend に従い、CPU では `Q4_K_M` が基準です。backend の自動選択は GPU がない場合 CPU、NVIDIA CUDA、AMD の専用メモリ GPU HIP（Windows または APU は Vulkan）、Intel 等 Vulkan です。(`setup.py:5069-5073`, `tools/image/qimage.py:88-98`)
- Apple Silicon で `STRATA_CONTROL_INSTALL=1` を指定せずに `setup.py` を実行すると `metal/setup_mac.py` に委譲されます。Metal 用 parser は未知の引数を `not used on a Mac: ...` と警告して続行するため、この文書の `--image-quant` はその経路では使われません。Intel SYCL wrapper は argv を保ったまま `setup.py` を再実行します。(`setup.py:9068-9069`, `metal/setup_mac.py:356-358`, `sycl/setup_intel.py:547-560`)
- `--images qwen-image` を指定すると、セットアップは画像生成機能とライセンスに関する案内を表示し、確認を求めます。拒否すると画像生成設定を返さず、モデルのダウンロード・画像 engine ビルドへ進みません。`--yes` はこの確認を自動承認します。(`setup.py:5087-5095`)

## 出力とエラー

- 明示値が推奨より大きい場合、stderr 側の警告関数を通じて推奨量子化と容量を知らせます。量子化値だけを理由に処理を中断する分岐はありません。(`setup.py:5074-5076`)
- 画像モデルのダウンロード後にサイズと SHA-256 が検証されます。また CUDA backend の画像 engine ビルドで `nvcc` がない場合は `fail()` によるエラー経路になります。ビルド完了後に `sd-cli` が見つからない場合も失敗します。(`setup.py:5022-5026,5056-5059,5095-5100`)
- 画像生成設定はモデルごとの run config に書かれます。既存の同じ設定ファイルが変更される場合、setup は `.bak` を作成しようとし、バックアップ作成に失敗すると警告して本体の設定書き込みを続けます。(`setup.py:6653-6677`)

## 根拠

- parser 宣言、choices、help 非表示: `setup.py:9096-9101`。
- 推奨量子化・明示値優先・警告: `setup.py:5065-5077`、`tools/image/qimage.py:56,65-71`。
- 選択値を使う設定処理、確認、download/hash 検証、設定生成: `setup.py:5080-5104`、`tools/image/qimage.py:44-56,190-203`。
- `--images` がない場合と `--images no` の動作、設定からの削除: `setup.py:5083-5084,10434-10436,6666-6668`。
- wrapper、Mac 委譲、SYCL argv 再実行: `setup.sh:76`、`START-HERE.bat:48`、`setup.py:9068-9069`、`metal/setup_mac.py:356-358`、`sycl/setup_intel.py:547-560`。
- 利用者向けのプレビュー手順とオプション表: `docs/IMAGES.md:16-21,48-55`。これは補助資料として参照し、上記の動作説明は parser と実装を根拠にしています。
