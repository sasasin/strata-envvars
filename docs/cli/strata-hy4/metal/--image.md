# `--image`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--image` |
| 別名 | なし |
| 値 | 画像ファイルへのパスを1つ指定。複数回指定できる |

## 役割

Metal 版 Hy4-Flash のオフライン実行で入力画像を指定する。各画像を読み込んで ViT 用サイズに変換し、`--tokens` で指定した入力中の画像 placeholder と順番に対応させてから画像行をエンコードする。画像を使う場合は Vision shard の `--vision` も必要。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids \
  --vision Hy4-Flash-Vision.strata --image picture.png --gen 128
```

画像を複数使う場合は、入力 token 列の placeholder 順に `--image` を繰り返す。

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids \
  --vision Hy4-Flash-Vision.strata \
  --image first.png --image second.png --gen 128
```

## 値と既定値

`--image` は引数の次の文字列をファイルパスとして追加する。既定値は画像なし（空のリスト）。画像の数やファイル形式を parser 段階では検査せず、各指定は入力順に処理される。画像ファイルを開けない場合、またはデコードできない場合はエラーになる。画像の読み込みには `fopen` と `stb_image` を使い、RGB 3 チャンネルとしてデコードする。(`engine/src/hy4flash/metal/hy4_metal_main.cpp:1498-1500,1600-1602`; `engine/src/hy4flash/run/hy4_vision.h:258-287`)

## 実行時の動作

コマンドライン走査時に各値を `image_files` へ追加する。`--serve` が指定されていない通常実行では、`--tokens` のファイルから読み込んだ token 列の各画像 placeholder を、対応する画像のサイズに応じた placeholder 列へ展開する。画像ファイル数と元の placeholder 数が一致しなければ処理を中止する。(`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1510,1601,1676-1681,1682-1700`; `engine/src/hy4flash/run/hy4_vision.h:290-310`)

画像は辺長が32の倍数となるよう `smart_resize` でサイズを調整し、ViT に渡す。画像の読み込み・placeholder 展開は CPU 側で行い、通常実行では Runner 初期化後に Vision shard をロードして画像をエンコードする。(`engine/src/hy4flash/run/hy4_vision.h:38-43,127-148,258-287`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`)

`--vision` と併用する。通常実行では `--image` があるときに限って `--vision` の未指定をエラーにする。画像の最大ピクセル数は別オプション `--image-max-pixels` で変えられ、既定は `4194304`。(`engine/src/hy4flash/metal/hy4_metal_main.cpp:1498-1500,1600-1602,1684-1697`)

`--serve` を指定すると、serve 処理へ進んだ後にオフライン用 `image_files` は参照されない。このモードの画像は起動時の `--vision` shard と serve プロトコルのリクエスト画像で扱われるため、起動コマンドの `--image` は入力画像として使われない。(`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675,1682-1684`; `engine/src/hy4flash/metal/hy4_metal_serve.h:320-350`)

## 適用条件と副作用

- 画像を指定する場合、token 入力に画像 placeholder があり、個数が `--image` の指定数と一致する必要がある。対応順はそれぞれの入力順。(`engine/src/hy4flash/run/hy4_vision.h:290-308`)
- 画像をファイルから読み込み、画像サイズの調整と Vision shard によるエンコードを行う。GPU 側処理は Vision encoder の呼び出しで行われる。(`engine/src/hy4flash/run/hy4_vision.h:259-287`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`)
- `--image` の値そのものに対する parser の形式・範囲検証はない。実際の失敗条件として、ファイルを開けない、デコードできない、縦横比が200を超える、画像数と placeholder 数が異なる、Vision shard が未指定またはロードできない場合がある。(`engine/src/hy4flash/run/hy4_vision.h:258-280,290-296`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1684-1697,1773-1779`)

## 出力とエラー

画像ファイルを開けない・デコードできない場合や placeholder 数が一致しない場合は、標準エラーに `image: ...` を出して終了コード `1` で終了する。Vision shard のロードまたは画像エンコードに失敗した場合は `images: ...` を標準エラーに出し、終了コード `1` で終了する。(`engine/src/hy4flash/metal/hy4_metal_main.cpp:1684-1697,1776-1779`; `engine/src/hy4flash/run/hy4_vision.h:258-296`)

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1502,1600-1602` — Metal CLI の引数処理、値の格納先、画像最大ピクセル数の初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675,1676-1705` — serve とオフライン実行の分岐、token 入力・画像の処理とエラー経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782` — Vision shard のロード、画像エンコードと失敗経路。
- `engine/src/hy4flash/run/hy4_vision.h:38-43,127-148,258-310` — Vision 画像設定、サイズ調整、画像読み込み・デコード、placeholder 数照合と展開。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:320-350` — serve モードではリクエストの画像を使い、起動時 shard がない場合に画像要求を拒否する処理。
