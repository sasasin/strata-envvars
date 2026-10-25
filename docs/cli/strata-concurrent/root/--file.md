# `--file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-concurrent` |
| コマンド | `strata-concurrent` |
| オプション | `--file` |
| 別名 | なし |
| 値 | expert データファイルのパス（1 引数） |

## 役割

CPU 側のメモリ読み込みと GPU 側の expert 転送・計算を同一プロセスで実行し、両者の帯域干渉を測る実験用プログラムに入力ファイルを渡します。製品の推論 CLI ではありません。CMake では CUDA または HIP backend が有効な場合に `strata-concurrent` が生成されます（`CMakeLists.txt:333-358`）。

## 使い方

```sh
strata-concurrent --file /path/to/experts.bin
```

この例は構文を示すものです。入力には後述の固定レイアウトを満たすファイルが必要です。

## 値と既定値

`--file` は値を1つ取り、既定値はありません。省略時、または空文字列を値として渡した場合は `--file is required` を標準エラーに出して終了コード 2 で終了します。値の後に別の `--file` を指定すると、後のパスが使われます。ファイル形式やパスを事前検証する parser はありません。値が欠けている場合は `<option> needs a value` を標準エラーに出して終了コード 2 で終了します。未知の引数（`--help` を含む）では usage を標準エラーに出して終了コード 2 になります（`src/core/concurrent_main.cpp:60-76`）。

## 実行時の動作

プログラムは各 expert について入力ファイルの `i * 1,382,400` byte 位置へ seek し、そこから 409,600 byte を読みます。読み取った領域は pinned host arena に連続配置されます。このレイアウト・読み込み幅は固定されており、ヘッダーやファイル全体のサイズを検査しません。必要な箇所まで読み込めない場合は `short read` を標準エラーに出し、終了コード 1 で失敗します（`src/core/concurrent_main.cpp:78-92`）。

ファイルを開けない場合は `cannot open <path>` を標準エラーに出し、終了コード 1 で終了します。arena を確保できない場合は `arena allocation failed` を出して終了コード 1 です（`src/core/concurrent_main.cpp:82-92`）。ファイルへの書き込みは行いません。

既定では `--experts` が 4096 のため、読み込み対象は合計 1,677,721,600 byte（約 1.56 GiB）です。ファイルは expert ごとに 1,382,400 byte 間隔でその先頭領域を読みます。`--experts` を併用すると読み込み回数・arena サイズが変わります（`src/core/concurrent_main.cpp:54-59,78-90`）。

読み込み後は CPU のみ、GPU のみ、CPU と GPU の同時実行を順番に行い、各モードの時間・CPU read GB/s・GPU roles/s と干渉指標を標準出力に表示します。CPU 側は arena の読み込みループであり、実際の VNNI 推論 kernel ではありません。GPU 側は読み込んだ領域を転送して kernel を実行します（`src/core/concurrent_main.cpp:112-188`）。このため実行は CPU/GPU の計算資源とメモリ帯域を消費し、入力ファイルを読み込みます。

## 適用条件と副作用

`--file` は GPU runtime を使う `strata-concurrent` の実行時に適用されます。このターゲットは `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` の条件内でのみ定義されています（`CMakeLists.txt:333-358`）。本調査ではバイナリの build・実行を行っていないため、個々の環境での GPU 初期化可否や runtime エラーの表示・終了経路は確認していません。

既定値では約 1.56 GiB の pinned host arena を確保し、GPU 用メモリ・stream も作成します。さらに CPU-only 区間は 3 秒間動作し、全体で3つの測定区間を実行します（`src/core/concurrent_main.cpp:149-179`）。実行前に入力パス、ファイルの十分な長さ、使用可能なホストメモリと GPU 環境を確認してください。

## 出力とエラー

- パス未指定・空値: `--file is required`、終了コード 2。
- 値の欠落: `<option> needs a value`、終了コード 2。
- `--help` など未知引数: usage、終了コード 2。
- arena 確保失敗、ファイルを開けない、必要な読み込みが短い: 各エラーを標準エラーへ出し、終了コード 1。
- 成功時: arena 容量等と各測定結果を標準出力へ出す。

いずれも `src/core/concurrent_main.cpp:60-94,170-188` に基づきます。GPU API 呼び出しの失敗は helper `check` がエラー名と runtime のエラー文字列を標準エラーに出し、終了コード 1 で終了します（`src/core/concurrent_main.cpp:33-38,96-110`）。

## 根拠

- parser、必須判定、値欠落・未知引数の失敗経路: `src/core/concurrent_main.cpp:52-76`
- arena サイズ、ファイル位置と読み込み長、open/short-read 失敗: `src/core/concurrent_main.cpp:78-92`
- GPU runtime 呼び出しとエラー出力: `src/core/concurrent_main.cpp:33-38,96-110`
- 測定処理、待機、標準出力: `src/core/concurrent_main.cpp:112-188`
- build 条件: `CMakeLists.txt:333-358`

