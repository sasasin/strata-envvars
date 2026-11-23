# `setup.py --image-noise`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから起動） |
| オプション | `--image-noise` |
| 別名 | なし |
| 値 | `on` または `off` |

## 役割

`--images qwen-image` で画像生成をセットアップするとき、画像生成エンジン `sd-cli` に Strata のノイズ生成器を組み込むかを選びます。単独では画像生成の設定を更新しません。

## 使い方

```sh
# 既存モデルの設定を更新し、画像生成と Strata のノイズ生成器を設定する
./setup.sh --setup --images qwen-image --image-noise on --no-start
```

## 値と既定値

- `on` はノイズ生成器を有効にし、`off` は有効にしません。値は `argparse` の `choices` で制限されます。不正値や値の省略は通常の argparse エラーになります（`terminal/setup.py:11261-11262`）。
- 既定値は `None` で、画像セットアップ内では `on` との完全一致だけを有効扱いにします。したがって未指定と `off` はどちらも無効です（`terminal/setup.py:5913`）。
- オプションは `help=argparse.SUPPRESS` で登録されるため、`--help` の表示には現れません（`terminal/setup.py:11261-11262`）。

## 実行時の動作

`--image-noise on` の指定だけでは何も組み込まれません。設定組み立て時に `setup_images` が呼ばれるのは `--images` が指定された場合だけです（`terminal/strata_control/setup_config.py:574-575`）。さらに `--images no` の場合、または画像モデルのダウンロード確認に応じない場合は、画像セットアップがそこで終了し、ノイズ設定も適用されません（`terminal/setup.py:5898-5909`）。

`--images qwen-image` のセットアップが進むと、`on` の場合にノイズ生成器のソースを含むビルド stamp を使って `sd-cli` をビルドまたは再利用し、生成された画像設定に `"noise": "strata"` を記録します。`off` または未指定ではその設定キーを追加せず、stable-diffusion.cpp 側の既定ノイズを使います（`terminal/setup.py:5913-5927`、`terminal/setup.py:5816-5837`、`terminal/tools/image/qimage.py:220-232,235-248`）。

実行時には、画像生成要求を作る `terminal/serve/images.py` が設定値 `"noise": "strata"` を `sd-cli --model-args strata_noise=1` に変換します（`terminal/serve/images.py:165-174`）。Strata のパッチは既定の CUDA RNG に対して独自 Philox RNG を選び、それ以外の RNG では警告を出して stable-diffusion.cpp のノイズ生成を維持します（`terminal/tools/image/sdcpp_noise/apply.py:33-46`）。

この指定は画像生成エンジンのビルド対象ソースにも作用します。ビルド時に `apply.py` が `sd-cli` のソースへノイズ関連ファイルを書き込みます。対象箇所が想定した stable-diffusion.cpp の内容と異なる場合は `SystemExit` で中断します（`terminal/setup.py:5794-5802`、`terminal/tools/image/sdcpp_noise/apply.py:57-80`）。ノイズ有効時の stamp にはノイズソースの fingerprint が含まれるため、ソース変更時には再ビルド対象になります（`terminal/tools/image/qimage.py:187-196,220-232`）。

`--image-noise` を指定せず `--images` も省略した場合、既存の画像設定は設定引き継ぎの対象です。このため、保存済みの画像設定にあるノイズ指定を変更するには、画像セットアップを改めて指定する必要があります（`terminal/strata_control/setup_config.py:574-575`、`terminal/setup.py:7631-7653`）。

## 適用条件と副作用

- `--images qwen-image` が指定され、画像モデルのダウンロード確認を通過したときに適用されます。特定の画像 backend に限る条件は parser から使用箇所までの経路にはありません。ビルド関数は backend を引数に取ります（`terminal/setup.py:5816-5825,5898-5927`）。
- 画像モデルのファイルをダウンロードし、必要なら `sd-cli` をコンパイルします。ノイズ有効時はセットアップが取得・用意した stable-diffusion.cpp のソースツリーをパッチし、画像設定をモデルごとの実行設定に書き込みます（`terminal/setup.py:5907-5927`、`terminal/tools/image/sdcpp_noise/apply.py:57-80`）。既存設定が変更される場合、セットアップは `.bak` を作成してから設定を書き込みます（`terminal/setup.py:7653-7663`）。
- ノイズパッチは全 backend 用として組み込まれますが、実行時に Strata の RNG へ切り替える条件は `sd-cli` の RNG が CUDA の場合です。異なる RNG が選択されている場合の最終的な乱数列や画像結果は、この CLI ソースだけからは確定できません（`terminal/setup.py:5794-5796`、`terminal/tools/image/sdcpp_noise/apply.py:33-46`）。

## 出力とエラー

- 画像セットアップでは、選択 backend・量子化の案内、ライセンス表示、モデルのダウンロード確認を出します。容量不足の可能性は警告されます（`terminal/setup.py:5898-5912`）。
- パッチ対象に想定コードが一意に見つからない場合、`apply.py` は対象ファイル名と「別の stable-diffusion.cpp commit の可能性」を示す `SystemExit` で停止します（`terminal/tools/image/sdcpp_noise/apply.py:66-72`）。
- CUDA backend で必要な `nvcc` が見つからない場合など、画像エンジンのビルド要件を満たさないとセットアップはエラーになります。これは `--image-noise` 固有の検証ではなく、画像セットアップの失敗経路です（`terminal/setup.py:5838-5845`）。

## 根拠

- `terminal/setup.py:11261-11262` — root parser の定義、受理値、help 非表示。
- `terminal/strata_control/setup_config.py:574-575` — 画像オプションが指定されたときのセットアップ呼び出し。
- `terminal/setup.py:5898-5929` — `on` の判定、画像モデル準備、ビルドと設定への反映。
- `terminal/setup.py:5816-5837`、`terminal/tools/image/qimage.py:220-248` — ビルド fingerprint と画像設定の組み立て。
- `terminal/tools/image/sdcpp_noise/apply.py:57-80`、`terminal/serve/images.py:165-174` — ソースへのパッチと実行時引数への変換。
- `terminal/setup.py:7631-7663` — 既存設定の引き継ぎ、バックアップ、書き込み。
