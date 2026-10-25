# `--images`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立した DeepSeek-V4.1 engine CLI） |
| オプション | `--images` |
| 別名 | なし |
| 値 | DSI1 形式の画像データファイルへのパス |

## 役割

`--ids` で与えた prompt token 列に対応する画像を読み込み、モデルの vision tower で画像 span に変換してから prompt を推論します。通常の PNG/JPEG ファイルを直接指定する引数ではありません。入力ファイルには DSI1 ヘッダーと、各画像の開始 token 位置・幅・高さ・RGB pixel bytes が必要です（`src/dsv41/ds4_main.cpp:231-261`）。

## 使い方

```sh
strata-dsv41 --pack /models/deepseek/maya-ds4 --ids @prompt.ids --images prompt.dsi --n 32
```

この例は通常の単発推論経路です。`--ids` は token ID の列を受け取り、`@` で始まる値はその後ろのファイルから読み込みます（`src/dsv41/ds4_main.cpp:1329-1354`）。画像ファイルの作成・変換方法はこのオプション自体では指定されていません。

## 値と既定値

- 値を1つ取ります。省略時は空文字列で、画像ファイルを読みません（`src/dsv41/ds4_main.cpp:1197`, `1238`, `1336`）。
- 同じ引数を複数回指定した場合、parser は変数へ順に代入するため最後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1208`, `1238`）。
- 値を省略すると `--images needs a value` を標準エラーへ出して終了コード 2 になります（`src/dsv41/ds4_main.cpp:1202-1206`）。
- 空文字列は parser で受理されますが、後段の `if (!images.empty())` に入らず読み込みは行われません（`src/dsv41/ds4_main.cpp:1336`）。
- ファイル形式は `DSI1` の4 byte magic、32-bit画像数（0〜4096）、各画像について 64-bit開始位置、32-bit幅と高さ、幅×高さ×3 byte のRGBデータです。幅・高さは正数、画素数は最大 `64 << 20` です（`src/dsv41/ds4_main.cpp:231-261`）。

## 実行時の動作

通常推論では `--pack` のモデルをロードした後、`--images` のファイルを読みます。各画像のRGBを `m.encode_image()` に渡し、生成された BF16 span と開始位置を `m.set_images()` に設定してから `--ids` の token を feed します（`src/dsv41/ds4_main.cpp:1282-1295`, `1335-1365`; `src/dsv41/ds4_model.hpp:63-67`, `174-182`）。モデルは画像 span 内の画像 token の埋め込みとして対応する span row を使います（`src/dsv41/ds4_model.cu:5232-5247`）。

この処理にはモデルの vision tower が必要です。`--vision` は既定で on ですが、`--vision off` では tower をロードせず、画像の encode は成功しません。checkpoint に vision tower がない、または tower のロードに失敗した場合も、モデル側の `image_token()` は利用可能な画像 token を返さず、画像 encode は失敗します（`src/dsv41/ds4_model.hpp:58-60`; `src/dsv41/ds4_model.cu:1985-1995`, `5211`, `9093-9096`）。画像幅・高さはモデルの patch size の倍数である必要があり、vision tower の patch/token 上限も適用されます（`src/dsv41/ds4_vision.cu:391-411`）。

適用範囲は通常の `--ids` 推論です。`--serve` は model load 後に先に serve loop へ移り、画像は `GENI` リクエストごとに渡すため、起動時の `--images` 値は処理されません。また `--profile-run`、`--spec-eval`、`--score` も通常の `--ids` 処理より前に return します（`src/dsv41/ds4_main.cpp:1296-1301`, `1335-1355`）。

## 適用条件と副作用

指定したファイルを読み込み、画像ごとに GPU vision tower の encode を実行し、その結果を prompt feed の間だけモデルへ設定します。推論後に `m.set_images({})` で画像 span を解除します（`src/dsv41/ds4_main.cpp:1342-1354`, `1360-1371`）。この通常経路は `--serve`、`--score`、`--profile-run`、`--spec-eval` では画像を読みません。なお通常経路ではファイル構造と画像寸法は検証されますが、画像開始位置が `--ids` 内の画像 token か、変換後の span 全体が画像 token の並びかを CLI 側で検査する処理は確認できません。serve の `GENI` 経路には位置と span の別検証があります（`src/dsv41/ds4_main.cpp:665-675`, `746-755`）。

## 出力とエラー

- ファイルを開けない場合は `maya-ds4: cannot open the pictures' file <path>`、DSI1 として読めない場合は `maya-ds4: <path>: not a pictures' file (DSI1)` を標準エラーへ出し、終了コード 1 です（`src/dsv41/ds4_main.cpp:233-261`, `1336-1341`）。
- vision encode が失敗した場合は encoder のエラーを `maya-ds4:` 付きで標準エラーへ出し、終了コード 1 です（`src/dsv41/ds4_main.cpp:1342-1349`）。無効な画像寸法や vision tower 未ロードも encode error になります（`src/dsv41/ds4_vision.cu:391-411`）。
- 読み込み成功時は画像の位置・寸法・token 数・encode 時間を標準エラーに表示します（`src/dsv41/ds4_main.cpp:1350-1351`）。通常の生成 token 列は標準出力へ出力されます（`src/dsv41/ds4_main.cpp:1395-1396`）。このオプション単独でファイルを書き出す処理はありません。

## 根拠

- `src/dsv41/ds4_main.cpp:87-93` — usage 表示上の引数位置と `--ids` / `--serve` の実行モード。
- `src/dsv41/ds4_main.cpp:1197-1208`, `1238` — parser、値の取得、既定値。
- `src/dsv41/ds4_main.cpp:231-261`, `1335-1371` — DSI1 読み込み、画像 encode、prompt feed、解除処理。
- `src/dsv41/ds4_model.cu:1985-1995`, `5232-5247`, `9093-9100` — vision tower の可用性、画像 token 埋め込み、画像 span の登録。
- `src/dsv41/ds4_vision.cu:391-411` — RGB画像の寸法・patch/token validation。
- `CMakeLists.txt:797-811` — `strata-dsv41` が `STRATA_BUILD_DSV41` により生成される独立 executable であること。

調査は上記 commit の checkout にあるソースを対象としました。既存バイナリの `--help` や Release artifact の動作は確認していません。
