# `--version`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

`strata-hy4` のバージョン文字列を標準出力へ表示して、終了コード `0` で終了する。モデルの読み込みや推論処理には進まない。ただし、オプション解析より前に実行されるプラットフォーム初期化と、`--version` より前に指定した引数の処理は起こり得る。

## 使い方

```sh
strata-hy4 --version
```

## 値と既定値

オプション自体は値を取りません。出力形式は `strata-hy4 <version>` と改行です。ソースでは `HY4_VERSION` が未定義の場合に `0.1.66` を既定値として定義しています。ビルド時に `HY4_VERSION` が定義されていれば、その値が使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:21-23,385-387`）。

## 実行時の動作

引数を左から解析し、`--version` に到達すると、その場でバージョン文字列を `printf` して `main` から戻ります。そのため、先行するオプションは通常どおり解析されますが、後続の引数は検査されません。たとえば `strata-hy4 --version --unknown` は `--unknown` を処理せずバージョンを表示して終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-388,498-505`）。

## 適用条件と副作用

この入口は CUDA/HIP 用 `strata-hy4` 実行ファイルのトップレベル parser です。CMake は `hy4_main.hip.cpp` を含む `strata-hy4` 実行ファイルを構成します（`engine/CMakeLists.txt:884-892`）。別の実行ファイルである Metal 版などの `--version` の動作はこの文書の対象外です。

`main` は引数解析の前に初期化処理を行います。Linux の HIP ビルドでは条件に応じてプロセスの NUMA memory policy を `MPOL_LOCAL` に設定し、設定結果や警告を標準エラーへ出すことがあります（`engine/src/hy4flash/run/hy4_main.hip.cpp:334-341`; `engine/include/strata/platform/numa_balancing.hpp:71-94`）。CUDA ビルドでは、`CUDA_MODULE_LOADING` が未設定であれば既定値を環境に設定する処理も先に実行されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:342-346`; `engine/include/strata/core/volta_forever.hpp:74-94`）。

また、`--version` より前に指定したオプションによっては解析中に環境変数を変更します。値が必要な先行オプションに値がない場合はバージョン表示まで到達せず、エラーで終了します。したがって、通常の単独指定では推論やモデル読み込みを行いませんが、全ての起動前処理・先行引数の副作用まで省略する保証はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-388,458-469`）。

## 出力とエラー

- `--version` に到達した場合、標準出力に `strata-hy4 <version>` を出し、終了コード `0` を返します。
- `--version` より前に未知の引数がある場合は、標準エラーに `unknown arg <引数>` を出して終了コード `2` を返します。`--version` より後ろの未知引数は検査されません。
- `--version` より前に値を必要とするオプションの値が欠けている場合は、標準出力に `ERR <オプション> needs a value` を出し、プロセスを終了コード `2` で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,498-505`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:21-23` — `HY4_VERSION` の既定値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:334-346` — parser より前に実行される OS/CUDA 初期化。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-388` — 引数解析中の `--version` 出力と即時終了。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,498-505` — 値不足と未知引数の失敗経路。
- `engine/CMakeLists.txt:884-892` — 対象ソースを含む `strata-hy4` 実行ファイルの構成。
- `engine/include/strata/platform/numa_balancing.hpp:71-94`、`engine/include/strata/core/volta_forever.hpp:74-94` — Linux HIP の NUMA policy と CUDA 環境変数の初期化条件。

確認範囲は上記 checkout の parser、version 定義、呼び出し前初期化、CMake target です。ビルド成果物ごとの `HY4_VERSION` の上書き設定は確認できていないため、実行ファイルが出力する具体的な値はビルド設定に依存します。
