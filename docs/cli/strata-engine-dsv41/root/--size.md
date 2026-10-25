# `--size`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（`STRATA_BUILD_DSV41=ON` で生成される独立エンジン） |
| オプション | `--size` |
| 別名 | なし |
| 値 | `幅x高さ`。幅・高さは画素数として整数変換される |

## 役割

`--encode-image` で渡す RGB 生画像の幅と高さを指定します。`--size` 自体は画像エンコードモードを選びません。画像エンコード時に、入力ファイルから読み込む RGB バイト数とエンコーダーへ渡す寸法を決めます。

## 使い方

```sh
strata-dsv41 --pack /path/to/model-pack --encode-image input.rgb --size 448x448 --dump-image span.bf16
```

`input.rgb` は幅×高さ×3 バイトの RGB データとして読み込まれます。`--encode-image` が画像エンコード経路を選び、`--dump-image` を指定した場合は画像の span を出力ファイルへ書きます。パック指定は通常のモデル読み込みに必要です。CLI の使用形は `src/dsv41/ds4_main.cpp:85-93`、パックと実行モードの確認およびモデル読み込みは `src/dsv41/ds4_main.cpp:1277-1295` にあります。

## 値と既定値

- 値のない `--size` は `--size needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。
- 値は `std::atoi` で `x` より前を幅、`x` より後を高さとして変換します。小文字 `x` がなければ高さは 0 です。`atoi` のため、数値全体の厳密な形式検証やエラー検出は行われません（`src/dsv41/ds4_main.cpp:1241-1245`）。
- 既定値は幅 0、高さ 0 です。明示しない場合や変換できない値では、画像エンコード用の RGB バッファが空になり、入力ファイルの検査に失敗します（`src/dsv41/ds4_main.cpp:1197-1199,1303-1310`）。
- 同じオプションを複数回指定したときは parser が順に代入するため、最後に指定した値が残ります（`src/dsv41/ds4_main.cpp:1200-1201,1241-1245`）。

## 実行時の動作

`--encode-image` が指定されると `vision_only` でモデルを読み込み、通常の生成ではなく vision tower のみを使う経路に進みます。`--size` はこの経路で、`max(0, 幅) × max(0, 高さ) × 3` バイトのバッファを作り、入力ファイルからそのバイト数を読み取ります。ファイルが開けない、寸法が0以下、または必要バイト数を読み切れない場合は `expected 幅 x 高さ RGB bytes (--size WxH)` を stderr に出し、終了コード 1 になります（`src/dsv41/ds4_main.cpp:1288-1295,1303-1311`）。

その後 `Model::encode_image` が vision tower に寸法を渡します。幅・高さは正で、モデルの patch サイズの整数倍である必要があります。また、画像 patch 数および生成される画像 token 数がモデル上限を超える場合はエラーになります（`src/dsv41/ds4_model.cu:5209-5217`、`src/dsv41/ds4_vision.cu:391-411`）。画像エンコードは同じ入力に対して2回行われ、各回の寸法・span 行数・所要時間が stderr に出ます（2回目は warm-up とコメントされています。`src/dsv41/ds4_main.cpp:1312-1321`）。

## 適用条件と副作用

- `--size` はトップレベル parser が受理しますが、実際の寸法利用箇所は `--encode-image` の分岐だけです。`--encode-image` がない呼び出しでは寸法は使われません（`src/dsv41/ds4_main.cpp:1238-1245,1303-1327`）。
- `--pack-info` が指定されると先に pack-info 経路で戻るため、併記した `--size` は使われません。また `--profile-run`、`--spec-eval`、`--score` の分岐は画像エンコード分岐より先に処理されます（`src/dsv41/ds4_main.cpp:1277-1284,1296-1303`）。
- `--vision off` を併記するとモデル読み込み時に vision tower がロードされず、画像エンコードは `this model has no vision tower (or it is off)` で失敗します（`src/dsv41/ds4_main.cpp:1233-1234,1288-1293`、`src/dsv41/ds4_model.cu:1985-1995,5209-5212`）。
- `--dump-image` は任意です。指定されて出力ファイルを開けた場合、span の BF16 データを書き込みます。ファイルを開けない場合も parser は確認せず、書き込みを飛ばして終了コード 0 になります（`src/dsv41/ds4_main.cpp:1322-1327`）。既存ファイルを指定すると `wb` で開くため上書きされます。
- 指定寸法から作る入力バッファの上限検査は parser にはありません。巨大な寸法を指定した場合の確保失敗や整数境界での挙動はこの調査では実行確認していません（`src/dsv41/ds4_main.cpp:1303-1306`）。

## 出力とエラー

- `--size` の値不足: stderr に不足メッセージ、終了コード 2（`src/dsv41/ds4_main.cpp:1202-1207`）。
- RGB 入力が期待バイト数に満たない、または寸法が実質0: stderr に期待寸法、終了コード 1（`src/dsv41/ds4_main.cpp:1303-1311`）。
- patch サイズ不一致、画像 token 上限超過、vision tower 不在など: エラー文字列を `maya-ds4:` 付きで stderr に出し、終了コード 1（`src/dsv41/ds4_main.cpp:1312-1317`、`src/dsv41/ds4_vision.cu:399-411`、`src/dsv41/ds4_model.cu:5209-5217`）。
- 正常時の span ファイルは `--dump-image` 指定時のみ生成されます。確認したコードでは書き込み結果を検査していません（`src/dsv41/ds4_main.cpp:1322-1327`）。

## 根拠

- parser と値変換: `src/dsv41/ds4_main.cpp:1197-1207,1238-1245`
- help の構文と画像エンコードの位置づけ: `src/dsv41/ds4_main.cpp:85-93`
- モード判定、vision tower の読み込み、入力検証、出力: `src/dsv41/ds4_main.cpp:1277-1327`
- vision-only 時の tower 読み込み条件: `src/dsv41/ds4_model.cu:1985-1995`
- RGB 寸法、patch 整合性、画像上限の検査: `src/dsv41/ds4_vision.cu:391-411`
- ビルド条件と独立実行ファイル: `CMakeLists.txt:797-811`

調査対象 checkout は `git rev-parse HEAD` で上記 commit、`git status --short --branch` で `## main...origin/main`（未コミット変更なし）でした。既存ビルド済み CLI の help は実行していません。ソース中の usage 表示と parser を照合しています。巨大な寸法の確保失敗等、実行を要する境界挙動は未確認です。
