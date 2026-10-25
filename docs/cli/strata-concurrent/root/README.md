# `strata-concurrent`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-concurrent` |
| コマンド | `strata-concurrent`（独立したネイティブ実行ファイル） |
| 主な実装 | `src/core/concurrent_main.cpp` |
| ビルド条件 | CMake で CUDA または HIP backend を有効にした場合に target を定義 |

## 役割

CPU の expert データ読み取りと GPU の転送・計算を単独および同時に動かし、双方のスループット低下を測る診断用プログラムです。通常のモデル推論 CLI ではなく、CPU 側は VNNI expert kernel の代わりに arena を繰り返し読むループを使います。そのため、この結果は CPU の実 expert 計算性能や製品推論の性能そのものを測るものではありません。

## 代表的な使い方

```sh
# CMake build で生成した strata-concurrent を、入力データとともに実行
./build/strata-concurrent --file experts.bin

# 読み込む expert 数、CPU 読み取り thread 数、GPU role 数を指定
./build/strata-concurrent --file experts.bin --experts 4096 --cpu-threads 6 --gpu-roles 256
```

`--file` は必須です。数値引数を省略したときは `--experts 4096`、`--cpu-threads 6`、`--gpu-roles 256` です。個別の値の扱いは [`--file`](--file.md)、[`--experts`](--experts.md)、[`--cpu-threads`](--cpu-threads.md)、[`--gpu-roles`](--gpu-roles.md) を参照してください。

## 実行モードと動作

このコマンドには対話式・server 起動などのモード切替はありません。実行すると次の処理を順に行います。

1. `--file` から固定サイズの expert データを読み、`experts × 409,600` byte の `PinnedArena` を確保します。各 expert について入力ファイルの `i × 1,382,400` byte の位置へ seek し、そこから 409,600 byte を読みます。したがって、引数で指定した expert 数に応じた範囲を持つ入力が必要です。
2. GPU メモリー、入力・出力バッファ、copy/compute stream を準備します。
3. CPU 読み取りのみ、GPU 処理のみ、両方同時の順に実行し、経過時間・CPU read GB/s・GPU roles/s を表示します。CPU 側は pinned arena の全域を64 byte strideで読み、GPU 側は role plane の host-to-device 転送と `s_gemv_split_async` による計算を行います。
4. CPU と GPU の単独時に対する同時実行時の throughput 低下率を表示して終了します。

主な副作用は大きな host memory の確保・pinning と GPU memory の確保および GPU 計算です。既定の 4096 experts では arena の容量は `4096 × 409,600` byte（約 1.56 GiB）で、GPU 側にも作業用領域を確保します。入力ファイルは読み取り専用で開き、このプログラムは結果ファイルを作成しません。

## 注意点

- `strata-concurrent` は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効な CMake 構成でのみ target が定義されます。実行には GPU runtime と利用可能な GPU が必要です。各 backend / platform でのビルド・実行可否はこの調査では確認していません。
- CPU 側は実際の VNNI kernel ではなく read loop です。ソースコメントは、CPU と GPU が DRAM 帯域を奪い合うかを測るためと説明しています。
- parser は数値を `atoi` で変換しますが、範囲 validation はありません。入力値の正当性を確認し、負数や非数値文字列を渡さないでください。
- `--help` / `-h` 専用処理はありません。これらを渡すと未知引数の usage 表示となり、終了コード 2 です。
- 入力不足・arena 確保失敗・CUDA API 失敗などでは測定が完了しません。GPU API エラーはエラー内容を stderr に表示して終了コード 1、ファイルを開けない場合や short read も stderr に表示して終了コード 1 です。必須 `--file` の欠落、値の欠落、未知引数は終了コード 2 です。

## 関連文書

- [CLI 文書索引](../../README.md) — `strata-concurrent` と関連オプションの scope。

## 根拠

- `CMakeLists.txt:333-358` — GPU backend 条件と `strata-concurrent` target の定義・リンク。
- `src/core/concurrent_main.cpp:52-76` — 引数 parser、既定値、必須引数、usage と失敗時終了コード。help 専用 parser 分岐はありません。
- `src/core/concurrent_main.cpp:78-94` — 固定寸法、arena 容量、入力 seek/read、開始時の表示。
- `src/core/concurrent_main.cpp:96-110,125-147` — GPU memory / stream の準備、転送・計算経路。
- `src/core/concurrent_main.cpp:112-123,149-188` — CPU read loop、3実行条件、測定値と比較出力。
- `src/core/concurrent_main.cpp:33-37,82-91,196` — GPU API エラー、arena・file・short read の失敗経路と正常終了。
- `include/strata/core/pinned.hpp:45-59,97-99` — `PinnedArena` の容量・有効性・data access。
