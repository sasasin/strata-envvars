# `--image-native`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査対象リポジトリの状態は `main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` 等から委譲） |
| オプション | `--image-native` |
| 別名 | なし |
| 値 | `on` または `off` |

## 役割

Qwen-Image-2.1-Turbo の画像生成で、Strata が追加するネイティブ DiT runner を使うかを指定します。これはチャットで画像を読む `--vision` とは別の画像生成機能です。

## 使い方

ソース checkout のルートから、画像生成の setup とともに指定します。

```sh
./setup.sh --setup --images qwen-image --image-native on
```

`--image-native` は `setup.py` の parser に登録されていますが、preview option として `argparse.SUPPRESS` が指定されているため `--help` には表示されません。短縮 alias はありません。`setup.sh` などの wrapper は `setup.py` に委譲します（索引の `source-setup` 範囲）。

## 値と既定値

- `on` は設定値を真にし、`off` は偽にします。省略時は parser の既定値 `None` が `False` として扱われるため、ネイティブ runner は要求されません。
- 他の値、値なし、または値の省略は `argparse` の choices 検証で拒否され、usage とエラーを表示して終了します（通常の argparse parse error、終了コード 2）。同じ option を複数回指定した場合は通常の `store` action により最後の値が残ります。

## 実行時の動作

この値が実際に使われるのは `--images qwen-image` を指定し、確認プロンプトで画像モデルの setup を続けた場合です。`--images` が未指定なら既存の `images` 設定が引き継がれ、`--images no` なら画像生成設定を外す経路となり、この option は使われません。setup を続けない回答でも画像生成設定は作られません。

`on` なら setup は `images.native: true` を run config に記録します。画像生成要求時、Strata は別プロセスの `sd-cli` に `--model-args qwen_image_2_1_native=1` を加えます。ネイティブ runner は Qwen-Image-2.1 の diffusion runner を Strata 実装へ切り替える指定で、条件が合わなければ stable-diffusion.cpp の通常 runner が選ばれる実装です。

適用 backend は CUDA と HIP だけです。Vulkan または CPU を `--image-backend` で選んだ場合も `on` 自体は parser で受理されますが、config に `native` キーを作らないため runner 指定は転送されません。backend の自動選択・明示選択は `--image-backend` の設定に従います。

## 適用条件と副作用

画像生成 setup は `sd-cli` の build または既存 build の再利用、Qwen-Image モデルファイルのダウンロードと SHA-256 検証、run config の更新を行います。CUDA/HIP では setup が pinned stable-diffusion.cpp checkout に Strata の runner と CUDA/HIP kernel を適用してから build します。この option を調べるために build やダウンロードを実行したものではありません。

ネイティブ runner の適用・build は CUDA/HIP backend で行われますが、`off` のときもその backend の build に runner のソースが含まれ得ます。実際に `sd-cli` へ切替指定を渡すかどうかは config の `native` 値で決まります。

## 出力とエラー

無効値は parser 段階で拒否されます。画像生成 setup の継続を拒否すると setup は画像モデルを導入せず、画像生成 config を返しません。CUDA toolkit、ROCm、Vulkan SDK など backend の build 要件を満たさない場合は、該当 backend の setup 処理がエラーを出します。これらは `--image-native` 固有の検証ではありません。

## 根拠

- `setup.py:9096-9105` — preview 画像生成 options の parser 宣言。`--image-native` の choices と hidden help 指定。
- `setup.py:9212` — parser による引数解析。
- `setup.py:5080-5104` — `--images` の適用条件、確認、build・download、config への `native` 引き渡し。
- `setup.py:5017-5020` — CUDA/HIP backend で pinned checkout に native runner を適用。
- `tools/image/qimage.py:169-198` — 対応 backend、build fingerprint、config の `native` キー作成条件。
- `tools/image/sdcpp_native/apply.py:1-10, 27-45` — runner の切替条件と通常 runner への fallback。
- `serve/images.py:111-128` — 画像生成時に config の `native` が真なら `sd-cli` に `--model-args qwen_image_2_1_native=1` を追加。
- `docs/IMAGES.md:1-7, 16-27, 48-69` — 画像生成の用途、source checkout 前提、setup 利用例と backend 概要。native option 自体は同ページの setup option 表に記載されていないため、詳細は parser と実装を根拠とした。

## 調査範囲

同一 revision のソースを確認しました。`--help` は補助資料として実行していません（option が `argparse.SUPPRESS` で隠されているため）。この文書は setup の parser と Strata 側の config・runner 引き渡しを説明し、stable-diffusion.cpp の内部アルゴリズムや backend ごとの実行性能は評価していません。
