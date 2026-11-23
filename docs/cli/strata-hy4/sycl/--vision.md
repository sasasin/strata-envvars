# `--vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--vision` |
| 別名 | なし |
| 値 | Vision shard の `.strata` ファイルパス（文字列） |

## 役割

`strata-hy4-sycl --serve` に Hy4-Flash の Vision shard を指定し、GEN 要求に画像を含める機能を有効にします。起動時には shard の形式を検査し、実際の画像要求が来たときに重みを読み込んで画像を符号化します。SYCL の通常生成経路では値を保存するだけで、Vision 処理には使われません。

## 使い方

```sh
# Vision shard を使える状態で SYCL のエンジン line protocol を起動する
strata-hy4-sycl --serve --native Hy4-Flash.strata --vision Hy4-Flash-Vision.strata
```

画像要求は起動後の GEN line protocol で `image=<path>` を指定します。`--vision` は起動時に shard を選び、要求内の画像ファイルパスを直接指定するオプションではありません。

## 値と既定値

- `--vision` は1つの値を必須とし、parser は次の argv 要素をそのままパスとして受け取ります。値の存在確認や形式検査は parser では行いません。値を省略すると `ERR --vision needs a value` を stdout に出し、終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:107-115,137-139`）。
- 既定値は空文字列で、オプションを省略した場合は Vision shard を指定しません（`engine/src/hy4flash/sycl/sy_main.cpp:100-102`）。同じオプションを複数回指定すると変数への代入が繰り返されるため、最後の値が残ります（同 `sy_main.cpp:137-139`）。
- 空文字列は `vision` が空のままとなり、検査を行わないため、オプション省略時と同様に画像機能が無効です。空でない値について、ファイルを開けない、Vision shard でない、manifest/configuration または tensor dtype が非対応の場合は起動時検査に失敗します。検査失敗は起動拒否ではなく、画像機能を無効化する警告になります（`engine/src/hy4flash/sycl/sy_main.cpp:137-139`; `engine/src/hy4flash/run/hy4_vision.h:68-75,92-110`; `engine/src/hy4flash/sycl/sy_serve.h:313-322`）。

## 実行時の動作

parser は値を `vision_path` に格納します。`--serve` の分岐に入る場合だけ `ServeOpts.vision` へ渡され、Serve 側は値が空でなければ `vision_probe` で shard を検査します。検査に成功した場合、INFO 応答の `images=1` に反映されます（`engine/src/hy4flash/sycl/sy_main.cpp:137-139,215-249`; `engine/src/hy4flash/sycl/sy_serve.h:28-48,313-333`）。

Vision shard の重み本体は起動時には読み込まず、画像を含む要求を初めて処理するときに `VisionEncoder::load` が読み込みます。その後、要求に含まれる各画像をデコード・リサイズし、image placeholder 数と画像数を照合してから符号化します（`engine/src/hy4flash/sycl/sy_serve.h:348-375,393-406`; `engine/src/hy4flash/sycl/sy_vision.h:390-406`; `engine/src/hy4flash/run/hy4_vision.h:258-287,290-310`）。リサイズ上限は同じ ServeOpts に渡される `--image-max-pixels` の値が使われます（`engine/src/hy4flash/sycl/sy_main.cpp:102,152,242-244`; `engine/src/hy4flash/sycl/sy_serve.h:361-364`）。

`--serve` を付けない通常生成経路では、parser が値を受け取っても ServeOpts に渡されず、通常生成処理は `vision_path` を参照しません（`engine/src/hy4flash/sycl/sy_main.cpp:137-139,215-249,250-280`）。また `vision_requested` フラグも設定・転送されますが、この checkout の SYCL Serve 実装内では参照されず、実際の有効判定は `vision` パスが空かどうかで行われます（同 `sy_main.cpp:100,137-139,242-244`; `engine/src/hy4flash/sycl/sy_serve.h:44,317-322`）。

## 適用条件と副作用

- 有効なのは SYCL 実行ファイルの `--serve` 経路です。CUDA/HIP や Metal 実装の挙動はこの文書の対象外です。
- 指定ファイルは起動時に開かれて Vision shard として検査されます。成功しても、重みを pinned host memory に読み込むのは画像要求時です（`engine/src/hy4flash/run/hy4_vision.h:68-115`; `engine/src/hy4flash/sycl/sy_serve.h:313-322`; `engine/src/hy4flash/sycl/sy_vision.h:390-406`）。
- shard の検査に失敗してもサーバー起動自体は続きますが、画像付き GEN 要求は `ERR image: this engine was started without the Vision shard ...` で拒否されます。画像ファイルを開けない・デコードできない・画像数と placeholder 数が合わない場合も、要求単位で `ERR image: ...` が返ります（`engine/src/hy4flash/sycl/sy_serve.h:351-378`; `engine/src/hy4flash/run/hy4_vision.h:258-287,290-296`）。
- parser は画像ファイルや shard のパスを検査しません。shard の読込時にファイルが開けない、読み込みが短い、または符号化の準備に失敗した場合は、要求に `ERR image: ...` を返します（`engine/src/hy4flash/sycl/sy_vision.h:390-400`; `engine/src/hy4flash/sycl/sy_serve.h:393-403`）。

## 出力とエラー

- オプションの値がない場合: stdout に `ERR --vision needs a value`、終了コード `2`（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 起動時の shard 検査失敗: stderr に `[vision] disabled: <理由>` を出し、Serve は続行します（`engine/src/hy4flash/sycl/sy_serve.h:317-322`）。
- 画像要求時に shard が無効なら protocol 応答 `ERR image: this engine was started without the Vision shard ...` を返します。画像準備・符号化失敗も `ERR image: <理由>` を返し、その要求を続行しません（同 `sy_serve.h:351-378,393-403`）。
- 初回の画像要求で shard を読み込むと、stderr に読み込み量・所要時間・device arena 容量が出ます（`engine/src/hy4flash/sycl/sy_vision.h:390-406`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:100-115,137-139`: 初期値、値の取得、および値なし時のエラー。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-249`: Serve 経路だけで Vision パスを ServeOpts に引き渡す。
- `engine/src/hy4flash/sycl/sy_serve.h:313-333,348-378,393-406`: 起動時 probe、画像要求の判定・処理、protocol エラーと INFO 出力。
- `engine/src/hy4flash/run/hy4_vision.h:68-115,258-287,290-310`: shard 検査、画像読込・リサイズ、画像 placeholder の対応検査。
- `engine/src/hy4flash/sycl/sy_vision.h:390-406,552-575`: shard の遅延読込と画像符号化。
