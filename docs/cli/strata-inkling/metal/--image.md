# `strata-inkling-metal --image`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--image` |
| 別名 | なし |
| 値 | 画像ファイルのパス（文字列） |

## 役割

Metal 版 Inkling-2 の起動時に指定画像を Vision encoder で処理し、埋め込みの形状と統計値を表示する任意の画像検査入力です。画像を通常のテキスト prompt に挿入する指定ではありません。parser は `--image` の値を `image_path` に保存し、値が空でなければ runner 初期化後に Vision をロードして画像を encode します（`engine/src/inkling2/metal/ink_metal_main.cpp:418-446,491-508`）。

## 使い方

```sh
strata-inkling-metal --model ./Inkling-2-Mini.strata \
  --vision ./Inkling-2-Mini-Vision.strata --image ./sample.png
```

`--model` は必須です。`--image` を処理するには `--vision` で Vision shard のパスも指定してください（`engine/src/inkling2/metal/ink_metal_main.cpp:444-446,470-473`; `engine/src/inkling2/metal/ink_metal_runner.h:768-774`）。

## 値と既定値

- 値を1つ取ります。次の argv 要素をそのままファイルパスとして受け取り、拡張子やファイル存在を parser 時点では検査しません（`engine/src/inkling2/metal/ink_metal_main.cpp:432-437,446`）。
- 未指定時は空文字列のままで、画像検査処理は実行されません（同 `:418,496-497`）。
- `--image` を複数回指定した場合は、後の値が前の値を置き換えます（同 `:432-446`）。
- 値を省略すると `missing value for --image` を stderr に出して終了コード 2 で終了します（同 `:434-436`）。空文字列を値にした場合は `image_path.empty()` が真となり、画像検査を実行しません（同 `:496-497`）。

## 実行時の動作

通常のモデルと runner を初期化した後、`image_path` が空でなければ `ensure_vision()` を呼び、続けて `encode_image_file()` でファイルを読み込みます。成功すると `[VISION] OK` として token 数、モデル hidden 次元、埋め込み RMS、先頭4要素を stdout に表示します。その後も処理は続き、指定がなければ既定のテスト prompt を設定し、通常の selfcheck / bench 等の後続経路へ進みます（`engine/src/inkling2/metal/ink_metal_main.cpp:496-516`）。

Vision shard のロードは遅延され、runner 初期化時には `--vision` の値を pending path として保持します（`engine/src/inkling2/metal/ink_metal_runner.h:617-618`）。画像処理時に既に Vision がロード済みなら再利用し、未ロードかつ Vision path が空なら `metal vision path not configured` を返します（同 `:768-774`）。画像は decoder で RGBA として読み込まれ、長辺が4096 pixelを超える場合は縮小し、幅・高さを `patch * merge`（定義上20×2）単位に切り上げてパディングし、Metal Vision encoder に渡されます（`engine/src/inkling2/metal/ink_metal_vision.h:146-169,171-189`）。

## 適用条件と副作用

- Metal 版 `strata-inkling-metal` の起動引数です。CUDA/HIP 版・SYCL 版の `--image` は別 parser と別の挙動を持つため、この文書の対象外です（Metal parser: `engine/src/inkling2/metal/ink_metal_main.cpp:417-468`; CLI 索引: `docs/cli/README.md:1549-1570`）。
- `--vision` が必要です。未指定・空の場合、`ensure_vision()` が失敗し、`[ERROR] vision: metal vision path not configured` を stderr に出して終了コード 1 になります（`engine/src/inkling2/metal/ink_metal_runner.h:768-774`; `engine/src/inkling2/metal/ink_metal_main.cpp:500-502`）。
- Vision shard の open、サイズ、header、metadata 読み込みなどに失敗した場合も画像処理は失敗します（`engine/src/inkling2/metal/ink_metal_vision.h:75-92`）。画像が開けない・decode できない場合は `stbi_load` の失敗をエラーにし、メイン側が `[ERROR] vision: ...` を出して終了コード 1 で終了します（同 `:151-153`; `engine/src/inkling2/metal/ink_metal_main.cpp:500-502`）。
- 画像 pixel と Metal encoder 用の一時バッファをメモリに読み込み・確保し、埋め込み統計を stdout に出します。画像ファイルを書き換える処理は確認できません（`engine/src/inkling2/metal/ink_metal_vision.h:152-189,191-204`; `engine/src/inkling2/metal/ink_metal_main.cpp:504-508`）。

## 出力とエラー

- 成功時: stdout に `[VISION] OK: <tokens> tokens x <dims> dims, rms=..., first4=[...]` を出力します（`engine/src/inkling2/metal/ink_metal_main.cpp:504-508`）。
- Vision 設定または画像 decode に失敗した場合: stderr に `[ERROR] vision: <理由>` を出力し、終了コード 1 です（同 `:500-502`）。
- `--image` の値がない場合: stderr に不足値を表示し、終了コード 2 です（同 `:434-436`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-468` — Metal CLI の引数 parser、値の取得、未指定値・未知引数のエラー。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-509` — 必須モデル確認、runner 初期化、画像検査の呼び出し、出力と失敗時終了。
- `engine/src/inkling2/metal/ink_metal_runner.h:617-618,768-774` — Vision shard の遅延ロードと Vision path 未設定時の失敗。
- `engine/src/inkling2/metal/ink_metal_vision.h:75-92,146-189,191-204` — shard の読み込み、画像 decode・縮小・padding と Metal encoder 用メモリ確保。
- `docs/cli/README.md:1549-1570` — `strata-inkling-metal` のコマンド階層と `--image` の索引リンク。
