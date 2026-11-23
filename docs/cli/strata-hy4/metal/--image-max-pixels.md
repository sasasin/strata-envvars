# `--image-max-pixels`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal`（サブコマンドなし） |
| オプション | `--image-max-pixels` |
| 別名 | なし |
| 値 | 画像の最大ピクセル数を表す整数（`int64_t` に変換） |

## 役割

画像入力を HY4 Vision 用にリサイズするときの最大画素数を指定する。オフライン推論では `--image` で渡した各画像、serve モードではリクエスト内の各画像に使われる。画像を渡さない実行では値は画像処理に使われない。

## 使い方

```sh
# オフライン推論: 画像を約 1 Mi ピクセル以下になるようリサイズする
strata-hy4-metal --model model.strata --tokens prompt.ids --vision vision.strata \
  --image input.png --image-max-pixels 1048576

# serve: リクエスト画像に適用する上限を指定する
strata-hy4-metal --model model.strata --serve --vision vision.strata \
  --image-max-pixels 1048576
```

## 値と既定値

- 省略時の値は `4194304` ピクセル（4 Mi ピクセル）。
- 値は `atoll` で読み取り、`int64_t` に格納する。parser に正数・範囲の検査はない。数値でない文字列なども専用の validation error にはならず、変換結果がそのまま後段へ渡る。`--image-max-pixels` の値がない場合を確認する parser のガードもないため、値を必ず指定する。
- `smart_resize` はまず高さ・幅を 32 の倍数に丸め、その面積が指定値を超える場合は面積を下げる方向に寸法を計算する。上限以下でも、丸めた面積が最小値 `4096` 未満なら最小値を満たす方向へ拡大する。このため、特に小さい上限値では指定値が最終寸法の厳密な上限になるとは限らない。
- 正数以外や極端な値に対する挙動を保証する validation はソース上にないため、通常の指定には正の整数を使う。

## 実行時の動作

parser の既定値 `4194304` または指定値を、オフライン経路では各 `--image` の `prepare_picture` に直接渡す。画像ファイルをデコードした後、Vision 設定の最小値とこの上限値を `smart_resize` に渡して寸法を決め、CPU 上で RGB 画像をリサイズする。オフラインで画像を使うには `--vision FILE` も必要で、画像ファイルの数は `--tokens` 内の画像 placeholder 数と一致させる。

`--serve` 経路では値を `ServeOpts.image_max_pixels` にコピーし、各プロトコルリクエストの `image=<path>` を処理する際に使う。画像リクエストを有効にするには `--vision` で利用可能な Vision shard を渡す必要がある。serve の画像対応は起動時に shard を probe して決まり、利用できない場合は画像リクエストに `ERR image: this engine was started without the Vision shard ...` を返して次のリクエストへ進む。

## 適用条件と副作用

- オプションは Metal runner 専用であり、この文書は `strata-hy4-metal` の scope を扱う。別 backend の既定値や挙動は対象外。
- オフライン経路では `--image` が1つ以上ある場合にだけ画像読み込み・デコード・リサイズが起きる。`--vision` が空、画像を開けない、形式をデコードできない、またはアスペクト比が 200 を超える場合は画像処理に失敗する。
- serve 経路では画像を含むリクエストごとに画像ファイルを読み込み、リサイズする。画像 placeholder と画像ファイル数が合わない場合も当該リクエストはエラーになる。
- 指定値の利用によるファイル書き換えは確認できない。画像は読み込み対象で、リサイズ画像を出力ファイルへ保存する処理はこの経路にない。

## 出力とエラー

- オフライン経路で画像準備に失敗すると stderr に `image: <理由>` を出して終了コード `1` を返す。`--vision` がない場合も同様に終了する。画像 placeholder と画像数の不一致も `expand_image_pads` のエラー理由を出す。
- serve 経路の画像エラーは stdout のプロトコル行 `ERR image: ...` として返し、プロセスは次のリクエスト処理を続ける。
- 値そのものの範囲エラーや警告は parser に実装されていない。異常値での寸法計算結果・失敗条件の詳細はソースから安全に確定できない。

## 根拠

調査対象 Strata checkout は `git rev-parse HEAD` で `73d4f4196c25a65e02f6b9ef25d354826ce55105`、状態は `## main...origin/main`（変更表示なし）。対象コードと関連箇所は次のとおり。

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1498-1502` — `image_max_pixels` の宣言と既定値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1600-1603` — `--vision`、`--image`、`--image-max-pixels` の parser。値を `atoll` で変換する。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1642` — serve 分岐で `ServeOpts` に値を渡す。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1682-1699` — オフライン画像処理、失敗時の stderr と終了コード、Vision 指定と placeholder 拡張。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:24-38` — serve オプション構造体の値と既定値。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:292-304` — serve 起動時の Vision shard probe と画像対応状態の通知。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:320-350` — リクエスト画像の準備、値の使用、画像エラー応答。
- `engine/src/hy4flash/run/hy4_vision.h:38-43` — Vision 寸法設定の最小画素数 `4096`。
- `engine/src/hy4flash/run/hy4_vision.h:127-145` — 32 倍数への丸め、上限・最小画素数に応じた寸法計算、アスペクト比検査。
- `engine/src/hy4flash/run/hy4_vision.h:258-287` — ファイル読み込み、デコード、`smart_resize` 呼び出し、画像準備エラー。
- `engine/src/hy4flash/run/hy4_vision.h:290-310` — placeholder 数と画像数の一致検査、画像 placeholder の拡張。
