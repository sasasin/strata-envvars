# `--image-backend`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。Strata checkout は `main` が `origin/main` と一致し、調査時点の作業ツリーに未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、update wrapper から委譲） |
| オプション | `--image-backend` |
| 別名 | なし |
| 値 | `cuda`、`hip`、`vulkan`、`cpu` のいずれか |

## 役割

画像生成 preview の `--images qwen-image` で使用する画像生成エンジン `sd-cli` の backend を指定します。テキスト推論エンジンの `--backend` とは別の設定です。`--images` を指定しない場合、この値は画像生成設定に使われません（`setup.py:9101-9102`, `setup.py:10434-10435`）。

## 使い方

Strata のソース checkout 内で、たとえば次のように指定します。

```sh
./setup.sh --images qwen-image --image-backend vulkan
```

画像生成の設定を進めると、setup は画像モデルのダウンロード確認を表示します。`--yes` を併用した場合は通常の確認を自動承認する経路になります（`setup.py:5087-5095`）。

## 値と既定値

`argparse` の `choices` により、指定できる値は `cuda`、`hip`、`vulkan`、`cpu` に限られます。省略時は GPU 情報から自動選択されます。GPU がない場合は `cpu`、NVIDIA は `cuda`、AMD は Windows または共有メモリ APU なら `vulkan`、それ以外は `hip`、その他の vendor（Intel Arc を含む）は `vulkan` です（`setup.py:9096-9102`, `setup.py:5065-5077`, `tools/image/qimage.py:88-97`）。

無効な値は parser の引数検証で拒否されます。画像 backend を省略した場合に `--backend`（テキストエンジン用）の値を流用する処理は、この選択関数にはありません。`setup.py:5069-5070` は GPU vendor と `hip` 判定から画像 backend を選びます。

## 実行時の動作

`--images qwen-image` があると setup は選んだ backend を `setup_images()` に渡します。明示値があれば自動判定より優先し、その backend 用の `stable-diffusion.cpp` の `sd-cli` を `engine-image/` に用意します。既存実行ファイルと build stamp が一致すれば再利用し、一致しなければ `build-image-<backend>/` でビルドして `engine-image/` へコピーし、`BUILD.json` を書きます（`setup.py:5080-5087`, `setup.py:5004-5062`）。

backend によって必要な toolchain が異なります。CUDA は `nvcc`、HIP は ROCm、Vulkan は Vulkan SDK または利用可能なシステム開発ファイルを使います。CPU は backend 固有 SDK を要求せず CPU 用設定でビルドします（`setup.py:5021-5051`, `setup.py:4959-4991`）。Vulkan を選んだ場合、Linux で SDK/開発ファイルがなければ setup は SDK を `third_party/` にダウンロード・展開し、実行環境変数も設定します。Windows で SDK がなければ setup を停止します（`setup.py:4964-4990`）。

画像モデルのダウンロードを承認すると、選択された backend とモデル設定が run config の `images` セクションに保存されます。確認を拒否した場合は画像設定を作らず、続く設定書き込み時に `images: null` はセクションごと取り除かれます（`setup.py:5089-5104`, `setup.py:6663-6677`）。

## 適用条件と副作用

- このオプションは `--images` を指定した場合だけ処理に使われます。既存設定の `images` は `--images` を今回指定しない限り別途 carry-over 対象です（`setup.py:10434-10435`）。
- 明示した backend と実機・開発環境の互換性をこの parser は検証しません。たとえば必要な CUDA Toolkit が見つからない CUDA ビルドは setup のエラー経路に進みます。Vulkan も Windows で SDK がない場合は停止します（`setup.py:5021-5026`, `setup.py:4969-4972`）。
- 画像モデルを承認すると、モデルファイル3点のダウンロードと SHA-256 検証、画像生成エンジンのビルドまたは再利用、モデル配置先ディレクトリの作成、run config の更新が発生します。空き容量が必要量 + 5 GB 未満なら警告しますが、その場では中止しません（`setup.py:5089-5103`）。
- CUDA/HIP は GPU の architecture 値も build stamp とビルド定義に使います。HIP 経路は `HIP_PLATFORM`、`ROCM_PATH`、`HIP_PATH`、`LD_LIBRARY_PATH` を setup プロセス内で更新します（`setup.py:5010-5011`, `setup.py:5032-5037`）。
- 通常の Apple Silicon setup は parser 作成前に `metal/setup_mac.py` へ委譲します。そのため本書の `setup.py` parser にあるこの option の適用範囲には含まれません（`setup.py:9068-9069`）。

## 出力とエラー

setup は選択したモデル量子化と backend を表示し、モデルのダウンロード確認を出します。推奨量子化より大きい画像モデルを選ぶ設定（`--image-quant`）では警告が出ますが、backend オプション自体は自動で別値へ置き換えません（`setup.py:5071-5077`, `setup.py:5086-5094`）。

CUDA Toolkit がない場合や、ビルド完了後に `sd-cli` が生成されていない場合は、`fail()` がエラーを表示して終了コード 1 で setup を停止します。無効な値は `argparse` が受理せず、usage と引数エラーを出します（`setup.py:5021-5026`, `setup.py:5056-5059`, `setup.py:904-909`, `setup.py:9101-9102`）。HIP/ROCm などその他の失敗条件の詳細な文言・終了経路は、この文書では網羅していません。

## 根拠

- parser 定義・preview 注記: `setup.py:9096-9105`（`--image-backend` は `help=argparse.SUPPRESS` のため `--help` には表示されません）。
- 適用条件と設定生成: `setup.py:5080-5104`, `setup.py:10434-10435`。
- 明示値の優先と backend 自動判定: `setup.py:5065-5077`, `tools/image/qimage.py:88-97`。
- backend ごとのビルドと SDK 条件: `setup.py:4959-4991`, `setup.py:5004-5062`。
- setup options の概要: `docs/IMAGES.md:48-69`。同文書は利用者向け説明として参照し、この文書の値・動作の根拠は同一 revision の parser と処理コードに置いています。
