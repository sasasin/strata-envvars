# `strata-hy4 --mpi-experts`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--mpi-experts` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Hy4 の server 実行で、2 台の Linux CUDA ホストに expert 計算を分散します。rank 0 がリクエストと server の状態を持ち、rank 1 はモデルの expert shard をロードして rank 0 から受け取る routed expert の計算を担当します。これは通常の `strata-hy4` ビルドでは無効で、`STRATA_HY4_DISTRIBUTED` を有効にしたビルドでのみ使えます（`engine/src/hy4flash/run/CMakeLists.txt:4,56-64`、`engine/src/hy4flash/run/hy4_remote_experts.hip.h:31-33,76-85`）。

## 使い方

分散対応ビルドを両ホストから実行でき、同じモデルファイルを各ホストで読み取れる状態にしたうえで、MPI launcher から 2 rank で起動します。launcher の引数形式は MPI 実装により異なります。

```sh
mpiexec -n 2 ./strata-hy4 --serve --mpi-experts --native /shared/model.strata
```

## 値と既定値

値を取らないフラグです。未指定時は無効で、同じ指定を複数回しても真偽値を true にするだけです（`engine/src/hy4flash/run/hy4_main.hip.cpp:354-356,375-400`）。

この parser 登録と実行分岐は `STRATA_HY4_DISTRIBUTED` のコンパイル条件内です。標準の構成は CMake option が `OFF` なので、そのビルドではこの引数は認識されず、unknown argument として終了コード 2 になります（`engine/src/hy4flash/run/CMakeLists.txt:4,56-64`、`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。分散ビルド自体も Linux 以外では CMake が構成エラーにします（同 `CMakeLists.txt:56-59`）。

## 実行時の動作

分散フラグ指定時は `--serve` が必須です。また `--gpus` / `--devices` で GPU 群を指定してはならず、`--gpu` は省略または `0` に限られます。違反すると stderr に要件を出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:360-362,399-405,508-512`）。`HY4_GPUS` の値も初期 GPU 群指定に使われるため、空でないと同じ検査で拒否されます。

MPI 初期化後、world size が 2 で、各共有メモリ node に rank が 1 つずつ存在することを検査します。さらに各ホストで CUDA device がちょうど 1 台見える必要があります。rank 間でモデル section の SHA-256 由来 identity を照合し、一致しなければ分散処理を中断します（`engine/src/hy4flash/run/hy4_main.hip.cpp:581-590`、`engine/src/hy4flash/run/hy4_remote_experts.hip.h:162-170`）。

rank 0 は `hy4_serve_main()` を実行し、rank 1 は同じモデルパスから expert shard 1 をロードして worker になります。実行中は coordinator から expert 入力を rank 1 に送り、worker の出力を戻して集約します（`engine/src/hy4flash/run/hy4_main.hip.cpp:591-601`、`engine/src/hy4flash/run/hy4_remote_experts.hip.h:47-60,76-128`、`engine/src/hy4flash/run/hy4_graph.hip.h:1105-1123,1164-1167`）。

## 適用条件と副作用

- Linux CUDA の分散対応ビルドが必要です。CMake は MPI と NCCL を用いる TP runtime を組み込みます（`engine/src/hy4flash/run/CMakeLists.txt:56-64`、`engine/src/tp/CMakeLists.txt:7-12,31-41`）。
- 2 ホスト・合計 2 rank、ホストごとに 1 rank・可視 CUDA device 1 台という構成に限定されます。複数 GPU の `--gpus` / `--devices` 指定とは併用できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:508-512,582-588`）。
- worker 側も `--native` / `--model` で渡したパスからモデルを開くため、同じモデルを両ホストで読める必要があります（`engine/src/hy4flash/run/hy4_remote_experts.hip.h:76-85,162-170`）。
- rank 間で制御情報および expert の入力・出力を通信します。worker または coordinator の処理に失敗した場合、MPI runtime は rank とメッセージを stderr に出し、`MPI_Abort(..., 1)` で job を中断します（`engine/src/tp/mpi_runtime.cpp:31-35`）。MPI 初期化例外は `Hy4 MPI initialization failed: ...` を stderr に出して終了コード 1 になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:602-607`）。

## 根拠

- `engine/src/hy4flash/run/CMakeLists.txt:4,56-64`、`engine/src/tp/CMakeLists.txt:7-12,31-41` — 分散機能の build option、Linux 条件、および MPI/NCCL runtime のリンク。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:354-356,375-400` — フラグの宣言と条件付き parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-512,578-611` — 未知引数・適用条件のエラー、および MPI 起動と rank ごとの分岐。
- `engine/src/hy4flash/run/hy4_remote_experts.hip.h:31-33,47-60,76-128,162-170` — worker の役割、通信・expert shard の処理、モデル identity。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1105-1123,1164-1167` — coordinator 側の remote expert 呼び出しと結果集約。
- `engine/src/tp/mpi_runtime.cpp:11-24,31-43` — MPI 初期化・rank 情報取得と abort 失敗経路。
