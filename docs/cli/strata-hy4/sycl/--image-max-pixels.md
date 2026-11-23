# `--image-max-pixels`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--image-max-pixels` |
| 別名 | なし |
| 値 | 画像の最大ピクセル数を表す整数値 |

## 役割

SYCL 版の server モードで処理する画像について、Vision encoder に渡す前のリサイズ計算に使う最大ピクセル数を指定します。画像はリクエストで受け取り、幅・高さが 32 の倍数になるようにリサイズされます。このオプションはサーバー起動時に設定され、各画像リクエストに適用されます。

## 使い方

```sh
# Vision shard を有効にした SYCL server を起動し、画像の上限を 1,048,576 ピクセルにする
strata-hy4-sycl --serve --native SQ32.strata --vision Hy4-Flash-Vision.strata --image-max-pixels 1048576
```

画像ファイルそのものはこの CLI 引数では渡しません。server の生成リクエストに `image=<path>` を含めると、その画像に指定した上限が使われます。

## 値と既定値

- 値は `atoll` で `int64_t` に変換されます。既定値は `1048576` です（`engine/src/hy4flash/sycl/sy_main.cpp:102,152`）。
- parser に正値・範囲・変換結果の検査はありません。欠落した値は `ERR --image-max-pixels needs a value` を標準出力に出して終了コード 2 で終了します（同 `sy_main.cpp:109-115,152`）。
- 値の許容範囲や 0・負数を指定したときの結果は実装で定義・検証されていません。リサイズ計算はこの値を上限として平方根・除算に使うため、通常の正のピクセル数を指定してください（`engine/src/hy4flash/run/hy4_vision.h:129-144`）。

## 実行時の動作

parser は値を `image_max_pixels` に格納し、`--serve` 経路で `ServeOpts` に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。server はリクエスト内の各画像パスを `prepare_picture` に渡し、この上限と `VitCfg().min_pixels` をリサイズ計算に使います（`engine/src/hy4flash/sycl/sy_serve.h:351-368`）。

リサイズでは入力画像の寸法を 32 の倍数に丸め、丸め後の面積が上限を超える場合に縮小します。一方、面積が `min_pixels` より小さければ拡大します。SYCL の最小値は `4096` です（`engine/src/hy4flash/run/hy4_vision.h:38-43,129-144`）。したがって、上限値が最小値より小さい場合の最終寸法が指定上限以下になることは保証されません。

この値はサーバー起動時に一度渡され、リクエストごとの画像の画素寸法と、その後 `image_token_count` が計算する画像プレースホルダー数に影響します（同 `sy_serve.h:361-375`、`engine/src/hy4flash/run/hy4_vision.h:147-148`）。

## 適用条件と副作用

- この値を実際に参照するのは `--serve` の処理です。単体推論経路でも parser は値を受理しますが、`--serve` 分岐後の単体推論処理ではこの変数を使用しません（`engine/src/hy4flash/sycl/sy_main.cpp:152,215-250`）。
- 画像リクエストには正常な Vision shard が必要です。`--vision` で指定した shard の検査に失敗すると画像機能は無効になり、画像リクエストは `ERR image: this engine was started without the Vision shard ...` で拒否されます（`engine/src/hy4flash/sycl/sy_main.cpp:137-139`、`engine/src/hy4flash/sycl/sy_serve.h:313-321,354-358`）。
- リサイズ前の画像読み込みとリサイズは CPU 側で行われます（`engine/src/hy4flash/sycl/sy_serve.h:348,361-368`）。

## 出力とエラー

- 画像ファイルを開けない場合やデコードできない場合は `prepare_picture` が失敗します。server はエラーを `ERR image: ...` としてプロトコル出力し、そのリクエストを処理せず次の入力へ進みます（`engine/src/hy4flash/run/hy4_vision.h:259-280`、`engine/src/hy4flash/sycl/sy_serve.h:360-373`）。
- 画像の縦横比が 200 を超える場合も画像準備に失敗します（`engine/src/hy4flash/run/hy4_vision.h:129-130,276-280`）。
- 画像ファイル数と prompt の画像 placeholder 数が一致しない場合は `ERR image: ... files for ... image placeholders` を出力し、そのリクエストを処理しません（同 `hy4_vision.h:290-296`、`engine/src/hy4flash/sycl/sy_serve.h:369-373`）。
- 画像の準備と placeholder 展開に成功すると、画像ごとに `IMG <番号> <placeholder数>` がプロトコル出力されます（`engine/src/hy4flash/sycl/sy_serve.h:374-375`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:102,152` — 既定値、parser 登録、`atoll` による変換。
- `engine/src/hy4flash/sycl/sy_main.cpp:109-115,215-248` — 値必須時の失敗経路と server 設定への受け渡し。
- `engine/src/hy4flash/sycl/sy_serve.h:28-48,313-321,348-375` — serve 設定、Vision shard の可否確認、画像リクエストでの利用と応答。
- `engine/src/hy4flash/run/hy4_vision.h:38-43,127-148,258-296` — 画素値の最小値、リサイズ上限の計算、画像読み込み・失敗条件・placeholder 数。

調査範囲は上記 revision の SYCL parser とその画像処理経路です。`atoll` の不正文字列や範囲外値に対する C ライブラリ固有の変換結果、および 0・負数でのリサイズ結果は Strata 側で検証・規定していないため、ここでは断定していません。
