# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load`（ネイティブ CLI、サブコマンドなし） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata-load` の usage を表示して正常終了します。CMake では `src/core/load_main.cpp` からネイティブ実行ファイルとして生成されます（`CMakeLists.txt:353-354`）。

## 使い方

```sh
strata-load --help
```

同じ処理を短縮形でも呼び出せます。

```sh
strata-load -h
```

## 値と既定値

値は不要です。`--help` と `-h` は parser で同じ分岐に入り、オプションを認識するとその場で usage を出力して `0` を返します（`src/core/load_main.cpp:36-39`）。そのため、この分岐より後にある `--file` 必須チェックは実行されず、ヘルプ単独の呼び出しでファイル指定は要求されません（同 `:45`）。

## 実行時の動作

標準出力に次の形式を表示します。

```text
usage: strata-load --file experts.bin [--layers N] [--threads N] [--chunk-mb N]
                   [--no-pin]
```

表示後は `main` から `0` を返します。parser は引数を左から順に処理してヘルプ分岐で直ちに終了するため、ヘルプより前に処理された引数のエラーは先に発生し得ます（`src/core/load_main.cpp:24-43`）。

## 適用条件と副作用

この分岐は usage の出力と正常終了のみを行い、ロード処理や arena の確保には進みません。arena の確保とファイル読み込みは、引数解析および `--file` 必須チェックの後にあります（`src/core/load_main.cpp:45-67`）。

## 出力とエラー

- `--help` / `-h` を認識した場合: usage を標準出力へ出し、終了コード `0`。
- 引数解析中に値が必要なオプションの値が欠けた場合: `stderr` に `<option> needs a value` を出して終了コード `2`。ヘルプより前にこのエラーが起きると、usage は表示されません（`src/core/load_main.cpp:26-28`）。
- 未知の引数の場合: `stderr` に `unknown argument: <argument>` を出して終了コード `2`（同 `:40-42`）。

## 索引との照合・調査範囲

索引の `strata-load` root にある `--help` のリンク先はこの文書と一致します（`docs/cli/README.md:1425-1433`）。ただし索引には parser が受理する短縮 alias `-h` が記載されていません。また、ソースの usage 表示は parser が受理する `--stream` も列挙していません（`src/core/load_main.cpp:34-38`）。この文書は parser の受理動作を記載し、usage 表示の内容との差を区別しています。

調査根拠は同一 checkout の `src/core/load_main.cpp` と `CMakeLists.txt` です。CLI の help は実行せず、ビルドやテストも行っていません。

## 根拠

- parser、alias、usage 出力、終了、引数エラー: `src/core/load_main.cpp:24-45`
- help 後に続くファイル読込経路: `src/core/load_main.cpp:45-67`
- CMake 実行ターゲット: `CMakeLists.txt:353-354`
- 索引の tool / command scope と対象リンク: `docs/cli/README.md:1425-1433`
