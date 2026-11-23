# `--image`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、トップレベル） |
| オプション | `--image` |
| 別名 | なし |
| 値 | 画像ファイルのパスを1つ取る。繰り返し指定できる |

## 役割

オフライン推論で読む画像ファイルを指定する。各画像は `--tokens` で渡したプロンプト内の画像プレースホルダー1個に対応し、指定順に展開される。サーバーモード用ではなく、その経路ではリクエストの画像入力をサーバーが処理する（`engine/src/hy4flash/run/hy4_main.hip.cpp:449,544-611`、`engine/src/hy4flash/run/hy4_serve.hip.h:386-413`）。

## 使い方

```sh
strata-hy4 --model MODEL.strata --tokens prompt.ids --vision Hy4-Flash-Vision.strata --image photo.jpg --gen 1
```

`prompt.ids` はトークン ID 列で、画像を入れる位置に画像プレースホルダー ID を1個含める。複数画像では `--image` を必要回数繰り返し、プレースホルダーの順序と合わせる（`engine/src/hy4flash/run/hy4_main.hip.cpp:449,632-638,668-684`）。

## 値と既定値

- 値はファイルパス文字列で、parser 自身による拡張子・空文字列・パス形式の検証はない。値のない `--image` は共通の値取得処理で標準出力に `ERR --image needs a value` を出して終了コード `2` で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,449`）。
- 既定値は画像なし。複数回指定すると上書きではなく、各値がベクターに追加され、後で指定した順に読み込まれる（`engine/src/hy4flash/run/hy4_main.hip.cpp:348,449,668-678`）。
- JPEG、PNG、BMP、GIF のデコードを実装コメントで示している。画像は RGB として読み込まれ、Vision 前処理用にリサイズされる（`engine/src/hy4flash/run/hy4_vision.h:150-153,258-287`）。

## 実行時の動作

通常のオフライン経路では、モデル読み込み後に画像ファイルを開いてデコード・リサイズする。既定の上限は `--image-max-pixels` と同じ初期値 `4,194,304` ピクセルで、下限は `VitCfg().min_pixels` の `4,096`。画像辺は 32 の倍数になるよう調整され、縦横比が 200 を超える画像は拒否される。`--image-max-pixels` は上限値だけを変える別オプションである（`engine/src/hy4flash/run/hy4_main.hip.cpp:350,450,668-677`、`engine/src/hy4flash/run/hy4_vision.h:38-43,127-148,258-287`）。

画像ごとに、`--tokens` にある画像トークン ID を1個ずつ対応づける。この offline 経路が参照する `VitCfg().image_token` は `120120` で初期化され、ここでは shard manifest を読んで上書きしていない。個数が画像ファイル数と一致しない場合は失敗する。一致した各プレースホルダーは、リサイズ後の画像寸法から計算した複数の画像トークンに展開される。画像入力には `--vision FILE` も必要（`engine/src/hy4flash/run/hy4_main.hip.cpp:448-450,668-685`、`engine/src/hy4flash/run/hy4_vision.h:38-43,147-148,290-310`）。

画像があると、Runner 初期化後に画像用に VRAM 約 1.25 GiB を空け、Vision shard の読み込みと画像エンコードを行う。成功時は画像数・行数・エンコード時間を標準エラーに出し、エンコーダーを解放して Runner に Vision context を設定する（`engine/src/hy4flash/run/hy4_main.hip.cpp:718-730`）。

## 適用条件と副作用

- `--image` は `--serve` より前に parser で受理されるが、serve 分岐では `image_files` を `ServeOpts` に渡さず、そのままサーバー起動処理へ進む。サーバーは個別リクエストの `image=<path>` を処理するため、serve 起動時の `--image` は画像入力にならない（`engine/src/hy4flash/run/hy4_main.hip.cpp:449,544-575,611`、`engine/src/hy4flash/run/hy4_serve.hip.h:386-413`）。
- `--load-only` はモデル読み込み直後に終了するため、この指定と併用した `--image` は画像デコード・検証に使われない（`engine/src/hy4flash/run/hy4_main.hip.cpp:658-668`）。
- 指定画像を開き、ファイル全体をメモリに読み込んでデコードする。GPU の空き領域を画像処理用に確保するため既存の VRAM キャッシュを解放する（`engine/src/hy4flash/run/hy4_vision.h:259-287`、`engine/src/hy4flash/run/hy4_main.hip.cpp:721-724`）。

## 出力とエラー

- ファイルを開けない場合は `image: cannot open <path>`、デコードできない場合は `image: cannot decode ...`、縦横比が 200 を超える場合は画像寸法付きのエラーを標準エラーへ出し、終了コード `1` で終了する（`engine/src/hy4flash/run/hy4_vision.h:259-280`、`engine/src/hy4flash/run/hy4_main.hip.cpp:671-676`）。
- 画像指定時に `--vision` がない場合、または画像数と画像プレースホルダー数が異なる場合は `image: ...` を標準エラーへ出して終了コード `1` で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:679-682`、`engine/src/hy4flash/run/hy4_vision.h:290-297`）。
- Vision shard の読み込みまたは画像 context の構築に失敗した場合は `images: <理由>` を標準エラーへ出し、終了コード `1` で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:721-725`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347-350,375-383,448-450` — `--image` の parser、値取得、画像なしの初期状態、関連オプション。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-638,658-685` — offline 経路でのトークン読込、画像処理、Vision 必須条件、プレースホルダー展開。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:718-730` — Vision エンコードと VRAM キャッシュ解放。
- `engine/src/hy4flash/run/hy4_vision.h:38-43,127-153,258-310` — 既定画像設定、寸法調整、ファイル読込、プレースホルダー個数検証。
- `engine/src/hy4flash/run/hy4_serve.hip.h:386-445` — serve 時はリクエストの `image=` パスを処理する経路。

同一 revision の `strata-hy4 --help` は実行していない。値の検証と効果は parser および使用箇所のソースから確認した。
