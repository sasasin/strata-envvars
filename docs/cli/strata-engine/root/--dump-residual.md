# `--dump-residual`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root scope） |
| オプション | `--dump-residual` |
| 別名 | なし |
| 値 | `PATH`。保存先ファイルのパス文字列 |

## 役割

生成処理の最後に保持している residual `R` をファイルに保存します。ヘッド処理と各層の値を比較して問題箇所を調べる用途です。通常の生成結果に加えて診断データを出力します。ヘルプには「final R (`hc x n_embd`, f32)」と記載されています（`src/program/generate.cpp:881-884`）。

## 使い方

```sh
strata --pack model.gguf --tokens 1,2,3 --dump-residual /tmp/residual.bin
```

`--pack` と `--tokens` は通常の生成に必要な入力の例です。保存先には、既存ファイルを誤って切り詰めない新しいパスを指定してください。

## 値と既定値

- `PATH` は次の argv 要素をそのまま受け取り、`std::string` に格納します。数値・拡張子・パスの存在確認といったオプション固有の検証はありません（`src/program/generate.cpp:2416-2420,2468`）。
- 省略時は空文字列のままなので出力しません（`src/program/generate.cpp:489,16901`）。空文字列を明示した場合も同じです。
- オプションを複数回指定すると、各値が同じ変数に代入され、最後の値が使われます（`src/program/generate.cpp:2468`）。
- 値を省略すると `--dump-residual needs a value` を標準エラーに出して終了コード 2 で終了します。値の取得処理は次の argv 要素を無条件に消費するため、`--stats` などオプションらしい文字列も値として扱われます（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

通常の生成処理と出力統計の後、値が空でなければ `ss.R` を GPU からホストメモリへコピーし、保存します。これは位置ごとの履歴ではなく、その処理時点の `R` 一つです（`src/program/generate.cpp:16867-16915`）。

ファイルはバイナリモード `wb` で開かれます。先頭に `int32_t` 2 個（`hc`, `n_embd`）を書き、その後に `hc * n_embd` 個の `float` を続けます。ヘッダーと float 配列は C++ の `fwrite` でそのまま書き出されるため、この実装は別のバイト順や数値表現への変換を行いません（`src/program/generate.cpp:16902-16915`）。

## 適用条件と副作用

- 既存の通常エンジン引数 parser が対象です。Qwen3.6 系のモデルは、モデルヘッダー判定後に専用 `qwen35::run` へ振り分けられる場合があります。その経路は通常 parser を通りません（`src/program/generate.cpp:2393-2408`）。Qwen 専用 parser でこのオプションが利用できるかは、本書の root scope では確認していません。索引も Qwen 専用 parser を別 scope にしています（`docs/cli/README.md:1128-1134,1318-1322`）。
- 指定先がすでに存在すれば、`fopen(..., "wb")` により内容を切り詰めて上書きします。親ディレクトリの作成は行いません（`src/program/generate.cpp:16907-16910`）。
- オプションは生成後に GPU から `R` を読み戻してファイルへ書くため、生成処理に加えて readback とファイル I/O が発生します（`src/program/generate.cpp:16901-16915`）。
- 索引上の対象は `src/program/generate.cpp` の通常エンジン parser です。実験的な SYCL build にも同名の parser と出力処理がありますが、別の実装です（`sycl/src/program/generate.cpp:472,810-813,1809,13005-13031`）。本書ではその build の実行確認はしていません。

## 出力とエラー

- GPU から `R` を読み戻せない場合、標準エラーに `strata generate: reading R back failed` を出し、終了コード 1 で終了します（`src/program/generate.cpp:16902-16905`）。
- ファイルを開けない場合、標準エラーに `strata generate: cannot write <PATH>` を出し、終了コード 1 で終了します（`src/program/generate.cpp:16907-16910`）。
- 書き込み後は標準出力に保存先、行列寸法、nonfinite 数、`mean|.|`、`max|.|` を表示します（`src/program/generate.cpp:16916-16923`）。
- `fwrite` と `fclose` の戻り値は検査されていません。そのため、ディスク不足などによる書き込み失敗があっても、この処理自身がエラーとして検出する保証はありません（`src/program/generate.cpp:16912-16915`）。

## 根拠

- 索引の tool ID と root scope: `docs/cli/README.md:1128-1134,1162-1168`。
- 標準 engine の値格納、ヘルプ、parser、値取得: `src/program/generate.cpp:489,881-884,2416-2420,2468`。
- Qwen family の早期振り分け: `src/program/generate.cpp:2393-2408`。
- `R` の読み戻し、ファイル形式、エラーと診断表示: `src/program/generate.cpp:16900-16923`。
- 実験的 SYCL 実装での同名オプション: `sycl/src/program/generate.cpp:472,810-813,1809,13005-13031`。
