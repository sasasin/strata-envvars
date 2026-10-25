# `--file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load`（root） |
| オプション | `--file` |
| 別名 | なし |
| 値 | 読み込む expert arena ファイルのパス（文字列） |

## 役割

expert arena の内容をメモリへ読み込む入力ファイルを指定します。`strata-load` は CMake で生成される実行ファイルで、parser は `src/core/load_main.cpp` にあります（`CMakeLists.txt:353-354`）。

## 使い方

```sh
strata-load --file ./experts.bin
```

この例では既定の 2 layer 分を読み込みます。別の範囲を読む場合は `--layers N` を併記します。

## 値と既定値

- `--file` の直後の argv 要素をパスとして受け取ります。値を省略すると `--file needs a value` を stderr に出して終了コード 2 で終了します（`src/core/load_main.cpp:24-29`）。次の要素が別の option に見える文字列でも値として消費します。
- パスの既定値はありません。指定後の `path` が空文字列なら `--file is required` を stderr に出し、終了コード 2 で終了します（`src/core/load_main.cpp:15, 30, 45`）。
- 同じオプションを複数回指定した場合は、ループ中に `path` を代入するため最後の値が残ります（`src/core/load_main.cpp:24-30`）。
- パーサはファイルの存在、拡張子、サイズ、内容形式を事前検証しません。後段の読み込みがパスを開き、読み取りに失敗した場合にエラーになります（`src/core/load_main.cpp:66-70`; `src/core/pinned.cu:856-869, 887-906`）。

## 実行時の動作

受け取ったパスは `load_experts(path, ...)` にそのまま渡されます。読み込む byte 数は `--layers`（既定値 2）× 512 blobs/layer × 1,382,400 bytes/blob で算出され、各 layer のファイル offset から指定範囲を読みます。したがって `--file` が指すファイルには、指定 layer 数に相当するデータが必要です。読み取ったデータは arena の宛先へコピーされ、各 layer の FNV-1a 64 checksum が計算されます（`src/core/load_main.cpp:16, 19-20, 47-50, 66-67`; `src/core/pinned.cu:681-685, 838-849, 893-926`）。

通常は `--no-pin` がないため、読み込み先を `PinnedArena` として確保し、pin/backing の状態を表示します。pinning が拒否された場合の fallback も arena 実装内にあります。arena の確保自体に失敗すると `arena allocation failed` を stderr に出して終了コード 1 です。`--no-pin` と併用すると通常の `malloc` に切り替わりますが、ファイル入力の意味は変わりません（`src/core/load_main.cpp:21, 52-64`; `src/core/pinned.cu:408-524`）。

## 適用条件と副作用

- パスはプロセスの作業ディレクトリ等に対する通常のファイルパスとして `fopen(path, "rb")` に渡されます。読み込みは worker ごとにファイルを開き、各 layer の開始位置へ seek して chunk 単位で行います（`src/core/pinned.cu:856-869, 887-896`）。
- `--layers` が読み込み範囲を決めます。ファイル末尾までを自動検出する処理や、余分な trailing bytes の拒否処理は確認できません。短いファイルは short read として失敗します（`src/core/load_main.cpp:16, 47-50`; `src/core/pinned.cu:893-906`）。
- 読み込み先の arena は既定で pinned memory を試みるため、大きな host memory の確保・pinning が発生します。`--no-pin` は通常メモリ確保へ変更します。`--stream` を併用した場合は、読み込み後にその arena から GPU への転送計測も実行されます（`src/core/load_main.cpp:21-22, 52-67, 83-99`）。
- `--file` は入力専用で、指定したファイルを書き換える処理はこの経路にありません。読み込み失敗時もソース上で確認できるのは入力の open／seek／read とエラー出力です（`src/core/pinned.cu:865-869, 887-906`）。

## 出力とエラー

- 読み込み前に対象 layer 数、固定 geometry に基づく計算 byte 数、backing 情報を stdout に出します（`src/core/load_main.cpp:47-64`）。成功時は読み込み量・所要時間・thread/chunk 情報、最大 4 layer の checksum（残りがあれば省略数）を stdout に出します（同 `:73-82`）。
- 指定パスを開けない場合、loader は `load_experts: cannot open <path>` を stderr に出し、呼び出し元は `loading the experts failed: ...` を出して終了コード 1 で終了します（`src/core/pinned.cu:865-869, 937-943`; `src/core/load_main.cpp:68-70`）。seek 失敗や short read も loader error 経由で同じ終了コード 1 になります（`src/core/pinned.cu:887-906`; `src/core/load_main.cpp:68-70`）。
- 未知の引数は `unknown argument: ...` を stderr に出して終了コード 2 です（`src/core/load_main.cpp:40-43`）。

## 根拠

- parser、値の受け取り、必須判定、既定値、arena 確保と出力: `src/core/load_main.cpp:14-70`
- `--file` を受け取る実行経路、読み込み範囲、ファイル open／seek／short-read、checksum: `src/core/pinned.cu:681-685, 838-948`
- 実行ファイルの build target: `CMakeLists.txt:353-354`
- CMake の条件付き load test でも `strata-load --file <path> --layers 1` として利用: `CMakeLists.txt:365-373`

調査範囲は上記 revision の checkout 内ソースです。同 revision の実行バイナリや Release 配布物は照合していません。
