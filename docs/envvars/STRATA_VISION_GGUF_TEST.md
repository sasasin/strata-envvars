# `STRATA_VISION_GGUF_TEST`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`tests/terminal/test_vision_gguf_meta.py` の `VisionGgufMetaTest.test_unknown_tensor_types_do_not_stop_the_vocabulary_load` が実行する、ビルド済み `strata-vision-gguf-test` バイナリのパスを指定します。Strata の通常のエンジン、サーバー、セットアップ処理が読む設定ではなく、この端末テスト専用の選択変数です。

選択されたバイナリはテスト用の GGUF を一時ディレクトリに作り、TQK6/TQK7 型の tensor を含むファイルから Strata の `strata_open_text_model()` が語彙を読めることなどを確認します。この変数自体はその処理内容を変えず、テストが実行する実行ファイルを選びます。

## 値と判定

| 値 | テストの挙動 |
|---|---|
| 未設定、空文字 | `os.environ.get(..., "")` が空文字となり、テストを skip する |
| 空でないパスだが通常ファイルでない | `Path(binary).is_file()` が偽となり、テストを skip する |
| 通常ファイルへのパス | そのパスを実行ファイルとして起動する |

文字列の形式や実行可能属性を事前検証する処理はありません。相対パスはテストプロセスの現在ディレクトリ基準です。ファイルが存在しても起動できない場合、または実行時エラーの場合に skip へ戻る処理はなく、`subprocess.run()` の起動エラーまたは後続の assertion failure になります。

## 有効になる条件

- `tests/terminal/test_vision_gguf_meta.py` の当該 unittest が実行対象であること。
- 環境変数の値が空でなく、その値の指す場所が通常ファイルであること。
- そのファイルが実行可能で、テストが期待する処理を完了すること。

対象バイナリは `tools/vision/CMakeLists.txt` の `strata-vision-gguf-test` CMake target で定義されています。`EXCLUDE_FROM_ALL` のため通常の全 target ビルドには含まれず、明示的にこの target をビルドして用意します。ターゲットは `llama` にリンクされ、出力先は `${CMAKE_BINARY_DIR}/bin` です。

## 実行時の詳細

テストメソッドごとに環境から値を読みます。値がない、またはファイルが見つからない場合は、`STRATA_VISION_GGUF_TEST is not set (build the strata-vision-gguf-test target)` を理由に skip します。値が有効なファイルパスなら、その実行ファイルを `[binary, temporary_directory]` の引数で起動します。標準出力と標準エラーは捕捉され、timeout は120秒です。

子プロセスの終了コードが0であることと、標準出力に `GGUF-META PASS` が含まれることをテストが要求します。テスト用 C++ プログラムは TQK6/TQK7 の型番号145/146を含む2種類の一時 GGUF を作成し、`strata_open_text_model()` が語彙全体を読み、header only の経路を使うことなどを確認して、各 fixture を削除します。最後に `GGUF-META PASS` または `GGUF-META FAIL` を出し、失敗数に応じて終了コードを返します。

この Python テスト内の変数読み取りはメソッド実行時に行われるため、テストプロセス開始後でも、メソッドが評価される前に環境が変更されればその値が使われます。起動した子プロセスには通常の `subprocess.run()` の環境継承が適用されますが、この環境変数を子プロセス向けに上書きするコードはありません。

## 根拠

- 変数の読み取り、未設定/空文字/非ファイル時の skip、バイナリ起動、timeout、終了コードと出力の確認: `tests/terminal/test_vision_gguf_meta.py:14-22`。
- CMake target、`EXCLUDE_FROM_ALL`、リンク先、出力場所: `tools/vision/CMakeLists.txt:138-142`。
- テストバイナリの引数、fixture の作成、語彙読み込み確認、header only 確認、出力文字列と終了コード: `tools/vision/gguf_meta_test.cpp:83-109`。

調査対象 commit で確認した範囲では、この環境変数の参照は上記端末テストに限られます。実行時エンジンの挙動を切り替える変数ではありません。テストやバイナリの実行は行っていません。
