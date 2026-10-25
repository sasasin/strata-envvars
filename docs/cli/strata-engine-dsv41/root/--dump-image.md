# `--dump-image`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DSV41 エンジンの root 引数） |
| オプション | `--dump-image` |
| 別名 | なし |
| 値 | 出力ファイルのパス。値は必須だが、パスの形式・拡張子の検証はない |

## 役割

`--encode-image` で RGB 画像をエンコードした結果を、指定先へ BF16 の生データとして保存します。PNG/JPEG 等の画像ファイルを出力するオプションではありません。コマンドの usage は `--encode-image FILE.rgb --size WxH --dump-image OUT` の組み合わせを示しています（`src/dsv41/ds4_main.cpp:85-94`）。

## 使い方

```sh
strata-dsv41 --pack /models/deepseek/maya-ds4 \
  --encode-image input.rgb --size 448x448 --dump-image /tmp/image-span.bf16
```

`--pack` はモデル pack のパス、`--encode-image` は入力 RGB バイト列、`--size` は幅と高さです。実行すると vision tower を使って画像を処理し、出力先をバイナリ書き込みモードで開きます（`src/dsv41/ds4_main.cpp:1282-1294,1303-1327`）。例の出力先が既存なら切り詰められるため、必要に応じて別のパスを指定してください。

## 値と既定値

- 値は次の argv 要素から文字列として読み取られ、`--dump-image` の省略時に使われる既定パスはありません（`src/dsv41/ds4_main.cpp:1200-1208,1240`）。
- 値を省略すると `--dump-image needs a value` を stderr に出して終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1202-1206`）。空文字列を渡した場合は出力先が空として扱われ、エンコード結果をファイルに書かず終了コード `0` になります（`src/dsv41/ds4_main.cpp:1322-1327`）。
- 出力のファイル形式や拡張子は検証されません。保存されるのは `uint16_t` 要素の列で、各要素は BF16 の1値です（`src/dsv41/ds4_main.cpp:1322-1325`、`src/dsv41/ds4_model.hpp:176-179`）。

## 実行時の動作

parser は値を `enc_out` に格納します。これは `--encode-image` の値 `enc_rgb` とは別の変数です（`src/dsv41/ds4_main.cpp:1197-1199,1238-1240`）。モデル pack が必須で、`--serve` 以外では `--ids`、`--encode-image`、`--score`、`--profile-run`、`--spec-eval` のいずれかの実行モード指定も必要です。`--dump-image` だけでは実行モードにならず、usage を stderr に表示して `2` で終了します（`src/dsv41/ds4_main.cpp:1282-1285`）。

画像出力は `--encode-image` の値が空でない場合に限り実行されます。この経路では `--size` から幅・高さを `atoi` で取得し、入力ファイルから `幅 × 高さ × 3` バイトを読みます。入力 RGB が不足するか開けないと `maya-ds4: <入力>: expected <幅> x <高さ> RGB bytes (--size WxH)` を stderr に出し、`1` で終了します（`src/dsv41/ds4_main.cpp:1241-1245,1303-1311`）。`--size` の値自体に厳密な形式検査はなく、`x` がなければ高さは `0` になります（同 `:1241-1245`）。

モデルロード後、同じ画像の `encode_image` を2回呼び出します（2回目は warm-up とするコメントがあります）。エンコードに失敗するとエラー文字列を stderr に出して `1` で終了します。成功時は画像サイズ・span の行数・所要時間を stderr に表示し、`--dump-image` の値が空でなければそのパスを `"wb"` で開き、span の全要素を2バイトずつ書きます（`src/dsv41/ds4_main.cpp:1312-1327`）。出力はモデル次元 `dim` の BF16 行で構成され、vision 実装では image start、行ごとの aligner rows と image newline、image end が span に含まれます（`src/dsv41/ds4_model.cu:5214-5230`、`src/dsv41/ds4_model.hpp:176-179`）。

## 適用条件と副作用

- `--dump-image` は `--encode-image` と `--size` による vision-only エンコード経路で使用されます。`--encode-image` がなければ、この値は出力に使われません。`--serve`、`--profile-run`、`--spec-eval`、`--score` が同時に指定され、それらの先行分岐が実行される場合も dump 出力処理には到達しません（`src/dsv41/ds4_main.cpp:1296-1303`）。
- `--encode-image` が指定されると `vision_only` が有効になり、モデルは vision tower のみをロードする設定になります（`src/dsv41/ds4_main.cpp:1288-1294`、`src/dsv41/ds4_model.hpp:58-59`）。vision tower のロードに失敗するとモデルロードが失敗し、stderr に `maya-ds4: <エラー>` を出して `1` で終了します（`src/dsv41/ds4_model.cu:1985-1995`）。画像 tower がない、または `--vision off` の場合、エンコード関数は `this model has no vision tower (or it is off)` を返して失敗します（同 `:5209-5213`、parser は `src/dsv41/ds4_main.cpp:1233-1234`）。
- 出力パスを既存ファイルにすると `fopen(..., "wb")` により切り詰めます。出力先を開けない場合、コードはエラーを表示せず書き込みを飛ばして `0` を返します。また `fwrite` の戻り値を確認しないため、書き込み失敗・部分書き込みも終了コードには反映されません（`src/dsv41/ds4_main.cpp:1322-1327`）。
- 実行ファイルは CMake の `STRATA_BUILD_DSV41=ON` で生成する独立 engine target です。同 option は CMake で既定 `OFF` とされます。GPU backend がない構成ではこの engine target ではなく host-side benchmark を作る分岐が記載されています（`CMakeLists.txt:797-811,2378-2385`）。この調査では特定 build の実行ファイルや Release 配布物を照合していません。

## 出力とエラー

| 条件 | 出力・終了 |
| --- | --- |
| `--dump-image` の値がない | stderr に `--dump-image needs a value`、終了コード `2` |
| `--dump-image` だけで pack または実行モードが不足 | usage を stderr に表示、終了コード `2` |
| RGB 入力が開けない、空サイズ、または必要バイト数を読めない | `maya-ds4: ... expected ... RGB bytes (--size WxH)` を stderr に表示、終了コード `1` |
| vision tower のロード・画像エンコード失敗 | `maya-ds4: <エラー>` を stderr に表示、終了コード `1` |
| エンコード成功 | `vision: ...` の要約を stderr に表示。出力先を開けていれば BF16 span を書き、終了コード `0` |
| 出力先を開けない／書き込みが部分的 | 明示的なエラー確認なし。コード上は終了コード `0` になり得る |

根拠は `src/dsv41/ds4_main.cpp:1202-1208,1282-1285,1303-1327` と `src/dsv41/ds4_model.cu:1985-1995,5209-5230` です。

## 調査範囲

指定された checkout のソースと CMake 設定を調査しました。同 revision の既存 CLI `--help` は実行していません。また、実際の GPU/backend・モデル pack での実行結果、OS ごとの `fopen` の詳細、Release artifact の内容は確認していません。

## 根拠

- parser、usage、実行モード選択、入力・出力・エラー処理: `src/dsv41/ds4_main.cpp:85-94,1190-1208,1238-1245,1282-1327`
- vision-only 設定とモデルロード時の tower 失敗: `src/dsv41/ds4_main.cpp:1288-1294`、`src/dsv41/ds4_model.cu:1985-1995`
- span の形式とエンコード時の組み立て: `src/dsv41/ds4_model.hpp:176-179`、`src/dsv41/ds4_model.cu:5209-5230`
- optional engine target と build 条件: `CMakeLists.txt:797-811,2378-2385`
