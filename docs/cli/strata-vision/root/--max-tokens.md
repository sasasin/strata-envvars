# `strata-vision --max-tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`、`strata-vision-hip`、`strata-vision-sycl` |
| オプション | `--max-tokens` |
| 別名 | なし |
| 値 | 整数。正の値は画像あたりの目標上限トークン数として使われる。 |

## 役割

画像を vision encoder に渡す前処理で、画像サイズを制限するための値です。値は mmproj の画像 geometry に基づく画像リサイズ上限へ換算されます。前処理後のトークン数が指定上限の 1/8 の許容幅も超える場合は、その画像をエンコードせず `ERR` として拒否します。これは `strata-vision` の常駐プロセス起動時に指定し、各画像の `ENC` 処理に適用します（`terminal/tools/vision/strata_vision.cpp:7-8, 87-89`、`terminal/tools/vision/own/own_reader.cpp:123-140`）。

## 使い方

```sh
# mmproj を読み込む常駐 reader を起動し、各画像のトークン上限を 1024 にする
strata-vision --mmproj ./vision-mmproj.gguf --max-tokens 1024
```

起動後のプロセスは標準入力で `ENC <画像パス> <出力パス>` と `QUIT` を受け付けます。GPU ビルドでは同じ parser を持つ `strata-vision-hip` / `strata-vision-sycl`（または Metal 対応 `strata-vision`）にも同じ指定を使います（`terminal/tools/vision/strata_vision.cpp:10-13, 36-56`、`terminal/tools/vision/CMakeLists.txt:77-98`）。

## 値と既定値

- `--max-tokens` の次の引数を `std::atoi` で整数に変換します。引数がない場合は `--max-tokens needs a value` を標準エラーに出し、終了コード 2 で終了します。値の範囲や変換結果の妥当性を parser で検査する処理はありません（`terminal/tools/vision/strata_vision.cpp:61-65, 87-89`）。
- オプションを省略した場合の内部値は `0` です。0 以下の場合、リサイズ上限には `geo.max_tokens` が使われます。この revision のソースでは `VitGeometry` の初期値 4096 が使われ、GGUF から token 上限を読み替える処理は確認できません（`terminal/tools/vision/own/own_reader.h:14-19`、`terminal/tools/vision/own/vit_geometry.h:43-44`、`terminal/tools/vision/own/vit_geometry.cpp:37-57`、`terminal/tools/vision/own/image_prep.cpp:205-209`）。
- 正の値は画像上限として適用されます。負数や、数値に変換できず `atoi` が 0 を返す入力は、明示的なエラーにならず既定 geometry の上限と同様に扱われます。重複指定を拒む処理はなく、引数走査中に同じフィールドへ代入するため最後の指定が残ります（`terminal/tools/vision/strata_vision.cpp:61-65, 87-89`）。

## 実行時の動作

画像準備時、正の `--max-tokens` は `patch × patch × merge × merge` を乗じたピクセル上限に換算されます。画像の縦横比を保ちながら encoder の alignment 単位に丸め、上限より大きい画像は縮小します。値が 0 以下なら mmproj 由来の `geo.max_tokens` を代わりに使います（`terminal/tools/vision/own/image_prep.cpp:205-209, 42-59`）。

`--min-tokens` を同時に正の値で指定した場合は同じ前処理関数に渡されます。リサイズはまず最大ピクセル上限を確認し、画像がその上限を超えず、かつ最小ピクセル数を下回る場合に限って拡大するため、最大上限側の条件が先に評価されます（`terminal/tools/vision/strata_vision.cpp:87-89`、`terminal/tools/vision/own/image_prep.cpp:42-59, 205-209`）。

前処理後、算出した画像トークン数が `max_tokens + max_tokens / 8` を超えると画像を拒否します。つまり 1/8 の余裕を許容し、それを超えた場合は出力ファイルを書かず、`ERR ... over the limit ... (vision.max_tokens)` を標準出力へ返して次の入力を処理します（`terminal/tools/vision/own/own_reader.cpp:133-140`）。

GPU 経路では起動時の warm-up にも同じ min/max 値を使います。初期 GPU バッファの token 数は正の指定値または geometry の上限と 4096 の小さい方です。4096 を超える上限を指定しても、ソースコメント上は大きな画像時にバッファを拡張する経路があり、その画像の処理が遅くなる可能性が記されています（`terminal/tools/vision/own/own_reader.cpp:65-76, 102-117`）。

## 適用条件と副作用

- option は `strata-vision`、`strata-vision-hip`、`strata-vision-sycl` で共通の `terminal/tools/vision/strata_vision.cpp` parser を通ります。どの backend でも画像のリサイズと上限チェックに使われます。GPU が有効な場合は warm-up と GPU バッファ確保の大きさにも影響します（`terminal/tools/vision/CMakeLists.txt:77-98`、`terminal/tools/vision/own/own_reader.cpp:65-76, 102-117`）。
- positive な上限は前処理画像の大きさに影響し、上限を大きくするとより多くの画像トークンを処理できる余地が生じますが、特定の性能・メモリ量はソースだけから一律には確定できません。
- 出力ファイルへの書き込みは画像が上限チェックを通過し、encoder が成功した後に行われます。指定先が既存ファイルの場合は `fopen(..., "wb")` により上書きされます（`terminal/tools/vision/own/own_reader.cpp:142-153`）。

## 出力とエラー

- オプション値が欠落すると標準エラーにエラーを出し、終了コード 2 です（`terminal/tools/vision/strata_vision.cpp:63-65`）。
- 数値の範囲外を理由にした起動時エラーはありません。値が正ならリサイズ条件に反映され、0 以下なら geometry 既定値へフォールバックします（`terminal/tools/vision/strata_vision.cpp:87-89`、`terminal/tools/vision/own/image_prep.cpp:205-209`）。
- 画像の前処理が失敗した場合、または上限を 1/8 超過した場合は標準出力に `ERR ...` を返して常駐プロセスは次の入力へ進みます。上限超過時の分岐は出力ファイルを開く処理より前にあります（`terminal/tools/vision/own/own_reader.cpp:131-140, 142-153`）。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:7-13, 61-95` — 共通 CLI 構文、parser、整数変換、欠落値・usage の扱い。
- `terminal/tools/vision/own/own_reader.h:14-19` — 内部 option の初期値と上限の意味。
- `terminal/tools/vision/own/vit_geometry.h:43-49` — geometry の token 既定値と alignment。
- `terminal/tools/vision/own/image_prep.cpp:42-59, 205-225` — 最大・最小ピクセルへの換算と画像サイズ調整。
- `terminal/tools/vision/own/own_reader.cpp:65-76, 102-117, 123-155` — GPU 初期化、warm-up、画像ごとの上限拒否、出力ファイル生成。
- `terminal/tools/vision/CMakeLists.txt:77-98` — CPU/GPU variant が同じ parser 実装を使うこと。
