# `--encode-image`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（エンジン引数） |
| オプション | `--encode-image FILE.rgb` |
| 別名 | なし |
| 値 | RGB 画素を行優先で並べた raw ファイルのパス。画像形式のデコード機能はない |

## 役割

モデルの vision tower だけをロードし、入力 RGB 画像を DeepSeek-V4.1 の画像 span 埋め込みへ変換します。出力をファイルに保存する場合は `--dump-image` を併用します。これは通常の `--ids` 推論で画像を指定するオプションではなく、エンコード専用経路を選ぶフラグです。

## 使い方

```sh
strata-dsv41 --pack /models/example/maya-ds4 \
  --encode-image ./input.rgb --size 448x448 --dump-image ./new-image-span.bf16
```

`--pack` は必須です。`--size` は画像の幅と高さ、`--dump-image` は任意の出力先です。出力先には新しいファイル名を指定してください。既存のファイルを指定すると切り詰められます。

## 値と既定値

- `--encode-image` の値は raw RGB 入力ファイルのパスです。parser は値をそのまま保存し、指定が重複した場合は後の値が使われます（`src/dsv41/ds4_main.cpp:1239`）。
- `--size` は別オプションで `幅x高さ` を渡します。小文字 `x` より前後を `atoi` で整数化し、`x` がなければ高さは 0 です。未指定時は幅・高さとも 0 です。厳密な数値文字列 validation はありません（`src/dsv41/ds4_main.cpp:1241-1245`、`src/dsv41/ds4_main.cpp:1199`）。
- 入力は `幅 × 高さ × 3` バイト以上必要です。読み込みではそのバイト数だけを要求し、ファイル末尾や余分なバイトは検査しません。RGB 以外の形式変換も行いません（`src/dsv41/ds4_main.cpp:1303-1310`）。
- `--dump-image` は省略可能です。省略時はエンコード結果をファイルへ書きません（`src/dsv41/ds4_main.cpp:1197-1199,1322-1326`）。

## 実行時の動作

`--encode-image` が空でないと `vision_only` が有効になり、モデルロード後に画像専用分岐へ進みます。`--pack` のモデルから vision tower をロードし、画像を2回エンコードします（2回目は warm 実行）。成功時、標準エラーへ各回の寸法・span 行数・経過時間を表示します（`src/dsv41/ds4_main.cpp:1282-1295,1303-1327`、`src/dsv41/ds4_model.cu:1985-1995`）。

各画像の幅・高さは正数で、モデルの patch サイズの倍数でなければなりません。さらに patch 数と span token 数がモデルの上限を超えると失敗します（`src/dsv41/ds4_vision.cu:391-411`）。span は BF16 の `[行数][モデル幅]` 配列で、image-start 行、各画像行の aligner 埋め込みと image-newline 行、image-end 行の順に構成されます（`src/dsv41/ds4_model.hpp:174-179`、`src/dsv41/ds4_model.cu:5209-5229`）。

## 適用条件と副作用

- `strata-dsv41` は `STRATA_BUILD_DSV41=ON` の CMake build で作られる独立 executable です。CMake の既定値は OFF であり、Release での配布有無はこの調査では確認していません（`CMakeLists.txt:797-812`）。
- この経路は vision tower を必要とします。`--vision off` を付けると tower がロードされず、エンコード時に `this model has no vision tower (or it is off)` で失敗します。モデルに tower がない場合も同様です（`src/dsv41/ds4_model.hpp:58-59`、`src/dsv41/ds4_model.cu:1985-1995,5209-5216`）。
- `--dump-image PATH` を指定すると `PATH` を `wb` モードで開き、既存ファイルを切り詰めて BF16 span を書きます。出力を開けなかった場合や `fwrite` が短く書いた場合、コードはエラーを報告せず終了コード 0 を返します（`src/dsv41/ds4_main.cpp:1322-1327`）。
- `--encode-image` と `--ids` などを同時に渡す使い方は避けてください。通常の `--ids` 分岐より先に `--profile-run`、`--spec-eval`、`--score` が選択され、`--serve` は画像分岐より先に実行されます（`src/dsv41/ds4_main.cpp:1296-1303`）。

## 出力とエラー

- `--pack` がない、または実行モード指定がない場合は usage を標準エラーへ出して終了コード 2 です（`src/dsv41/ds4_main.cpp:1275-1285`）。
- 入力を開けない、または必要バイト数を読み込めない場合は `maya-ds4: <path>: expected <w> x <h> RGB bytes (--size WxH)` を標準エラーへ出して終了コード 1 です（`src/dsv41/ds4_main.cpp:1304-1310`）。
- tower のロード失敗は `maya-ds4: <理由>`、画像サイズや上限の不適合は `maya-ds4: vision: ...` を標準エラーへ出し、終了コード 1 です（`src/dsv41/ds4_main.cpp:1289-1293,1315-1317`、`src/dsv41/ds4_vision.cu:393-411`）。
- 成功時、`--dump-image` のファイルには span の uint16 BF16 値をヘッダーなしで出力します。span 行数や形状はファイルに付随しないため、必要な寸法情報は呼び出し側で管理してください（`src/dsv41/ds4_main.cpp:1319-1325`、`src/dsv41/ds4_model.cu:5217-5229`）。

## 根拠

- parser、usage、必須条件、処理分岐、標準エラー、ファイル入出力: `src/dsv41/ds4_main.cpp:85-93,1239-1245,1275-1327`
- Vision tower 専用ロードと未搭載時のエラー: `src/dsv41/ds4_model.hpp:58-59`、`src/dsv41/ds4_model.cu:1985-1995,5161-5207,5209-5229`
- RGB 寸法・patch・token 数の validation: `src/dsv41/ds4_vision.cu:391-411`
- executable の build 条件: `CMakeLists.txt:797-812`
