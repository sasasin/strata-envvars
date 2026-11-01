# `DS4_SEQ_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 の Metal エンジンで、通常の prompt 処理を終えた直後に dispatch sequence の値を stderr へ記録する診断用スイッチです。モデル計算、生成結果、終了状態を切り替える設定ではありません。

## 値と判定

`ds4_dbg("DS4_SEQ_LOG")` は環境変数の値を変換せず、`std::getenv(name) != nullptr` で設定の有無だけを調べます。したがって未設定なら無効、空文字を含め何らかの値が設定されていれば有効です。`1` など特定の値を要求せず、`0`、`false`、任意の文字列も有効になります。数値変換、大小文字判定、範囲制限、無効値時の fallback はありません。

## 有効になる条件

- `STRATA_METAL` が定義されたビルドでのみ対象コードがコンパイルされます。非 Metal ビルドでは `ds4_dbg` は常に `false` を返す定義であり、このログ分岐自体もプリプロセッサ条件の外にあります（`src/dsv41/ds4_launch.h:30-37`, `src/dsv41/ds4_main.cpp:1491-1493`）。
- 対象は `strata-dsv41` の通常 prompt 処理です。`--serve` は先に serve ループへ戻り、profile / speculative evaluation / score 経路も通常 prompt の処理より前に戻るため、このログ箇所には到達しません（`src/dsv41/ds4_main.cpp:1410-1415`）。モデル読み込みまたは prompt feed が失敗した場合も、ログ箇所より前に戻ります（`src/dsv41/ds4_main.cpp:1403-1407,1474-1480`）。
- DSV41 エンジンの CMake target は `STRATA_BUILD_DSV41` が有効な場合に追加され、同 option は既定 OFF です（`CMakeLists.txt:906-920`）。このコードの利用には target を含むビルドと Metal 用の `STRATA_METAL` 定義が必要です。
- CLI 引数、設定ファイル、他の環境変数との優先順位や連動は、この読み取り箇所にはありません。

## 実行時の詳細

通常 prompt の全 feed が成功した後、prompt 所要時間の行を stderr に出した直後に環境変数を一度確認します。設定されている場合は `dispatch seq after the prompt: %llu` の形式で `ds4_dispatch_seq()` の戻り値を stderr に出します（`src/dsv41/ds4_main.cpp:1474-1493`）。読み取り結果は static 変数などに cache されませんが、この経路での確認は prompt 完了後の一回だけです。

この箇所は値を読むだけの診断分岐です。ログが出ない場合に警告やエラーを出したり、生成・終了を変えたりする処理はありません。sequence 値を返す `ds4_dispatch_seq` の実装は、この呼び出し元の Strata ソース範囲では定義されていないため、その内部の計数方法はここでは説明しません。

## 根拠

- helper の Metal / 非 Metal 別定義と設定有無判定: `src/dsv41/ds4_launch.h:30-37`
- Metal 条件下の宣言と通常 prompt 後のログ: `src/dsv41/ds4_main.cpp:198-200,1474-1493`
- serve / profile / spec / score の早期 return、および model load / feed 失敗経路: `src/dsv41/ds4_main.cpp:1395-1415,1403-1407,1474-1480`
- DSV41 target の build option と target 定義: `CMakeLists.txt:906-920`
