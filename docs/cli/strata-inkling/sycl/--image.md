# `--image`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL） |
| オプション | `--image` |
| 別名 | なし |
| 値 | 画像ファイルのパス。引数を文字列として受け取る |

## 役割

`--image` は `--vision` と組み合わせた任意の Vision エンコーダー確認用画像を指定する。指定した画像を Vision shard でエンコードし、トークン数と埋め込みの統計を表示する。SYCL の通常のテキスト生成に画像を渡すオプションではない。

## 使い方

```sh
strata-inkling-sycl --model model.strata --vision vision.strata --image sample.png
```

モデル本体のロード後、`vision.strata` をロードして `sample.png` をエンコードする。実行環境に対応する SYCL デバイスと必要なモデルファイルがあることが前提。

## 値と既定値

- 値は `--image` の直後の argv 要素を文字列として受け取り、`image_path` に格納する。数値変換やパス形式の事前検証はない（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-118`）。
- 既定値は空文字列。複数回指定した場合は、ループで後から処理された値が残る（同 `:103-104`, `:112-118`）。
- 後続の argv 要素がない場合、`need()` は空文字列を返すため画像処理条件を満たさず、専用の validation エラーにもならない。次の要素が `--` で始まっていても値として消費する（同 `:112-118`, `:185-196`）。

## 実行時の動作

1. `--image` の値は `image_path` に保存される（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-118`）。
2. `--model` が必要で、モデル本体のロードに成功した後、`vision_path` と `image_path` の両方が空でない場合だけ Vision 処理へ進む（同 `:166-183`, `:185-190`）。
3. Vision shard をロードし、画像をエンコードする。成功時は標準出力に `[VISION]`、画像パス、出力トークン数、埋め込みの平均・L2 ノルム・先頭4要素を表示する（同 `:187-195`）。
4. 画像ファイルは stb_image で読み込まれ、読み込み失敗時はエラーとなる。長辺が4096ピクセルを超える画像は長辺4096に縮小し、Vision の patch サイズと merge サイズの積の倍数に余白を付けてからエンコードする（`engine/src/inkling2/sycl/ink_sy_vision.h:24-32`, `:339-369`）。

## 適用条件と副作用

- `--vision` も指定されていなければ `--image` は受理されますが使用されません。片方だけを指定した場合もエンコード条件を満たさず、警告なしに画像処理を行いません（`engine/src/inkling2/sycl/ink_sy_main.cpp:185-196`）。
- `--info` はモデル情報を表示して先に終了するため、`--vision` と `--image` も指定していても画像処理には進みません（同 `:171-181`）。
- Vision shard を読み込み、画像データと中間テンソルをホスト・デバイス間で扱い、SYCL デバイス上でエンコードします。処理後、画像データとデバイス側一時バッファを解放します（`engine/src/inkling2/sycl/ink_sy_vision.h:51-97`, `:115-130`, `:333-369`）。
- stb_image のコンパイル設定では PNG、JPEG、BMP、GIF が有効です。ほかの形式の受理はこの実装から確認できません（同 `:24-32`）。

## 出力とエラー

- Vision shard のロード失敗または画像のデコード／エンコード失敗は、`[ERROR] <詳細>` を標準エラー出力に出して終了コード `1` で終了します（`engine/src/inkling2/sycl/ink_sy_main.cpp:187-190`）。Vision shard のファイルオープン失敗、短いヘッダー、manifest 解釈失敗、Section 1 の読み込み失敗、および画像デコード失敗の詳細は `engine/src/inkling2/sycl/ink_sy_vision.h:51-86`, `:339-343` にあります。
- 画像処理が成功すると、上記の統計を標準出力に出し、その後は通常の runner 初期化・指定モードの処理を続けます（`engine/src/inkling2/sycl/ink_sy_main.cpp:191-205`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — parser、初期値、`--image` の値取得。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-196` — `--model` 必須条件、`--info` の早期終了、`--vision` と `--image` の併用条件、出力・エラー経路。
- `engine/src/inkling2/sycl/ink_sy_vision.h:24-32`, `:339-369` — 画像デコーダー設定、画像読み込み、縮小・padding、エンコード呼び出し。
- `engine/src/inkling2/sycl/ink_sy_vision.h:51-97` — Vision shard の読み込みと失敗経路。
