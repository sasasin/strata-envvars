# `--tpr`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-overlap` |
| コマンド | `strata-overlap` |
| オプション | `--tpr` |
| 別名 | なし |
| 値 | 整数。GEMV の出力行ごとに使う CUDA thread 数 |

## 役割

S2 重みの行分割 GEMV において、出力行ごとの部分和を計算する CUDA thread 数（threads per row）を指定します。`strata-overlap` は専門家重みのコピーと GEMV の重ね合わせを比較する診断用プログラムです。これは推論エンジン全体の実行設定ではなく、この診断プログラム内の固定形状 GEMV にだけ適用されます。

## 使い方

ビルド済み `strata-overlap` に入力重みファイルを指定して実行します。

```sh
strata-overlap --file pack/full/experts.bin --tpr 32
```

`--file` は必須です。`--tpr` を省略すると 32 が使われます。

## 値と既定値

- parser の既定値は `32` です。指定値は `std::atoi` で `int` に変換されます。parser に文字列形式の追加検査はありません。
- 実際に GEMV を起動する CUDA 実装が受理する値は、1〜1024 の範囲にある2の累乗です。したがって `1, 2, 4, ... 1024` が有効です。範囲外または2の累乗でない値は stderr に要件と値を出して終了コード 1 で終了します。
- 同じ `--tpr` を複数回指定した場合、引数ループ内で都度代入されるため最後の指定値が残ります。
- 値を伴わない `--tpr` は parser が `--tpr needs a value` を stderr に出し、終了コード 2 で終了します。

## 実行時の動作

指定値は同一形状（`n_in=2560`, `n_out=640`）の S2 GEMV に渡され、serial と overlapped の両方の測定経路で使われます。kernel は各出力行を指定数の thread に分け、部分和を shared memory 上で還元します。値が増えると行あたりの並列度と shared memory の部分和領域サイズが変わりますが、このソースから特定値が常に速いとは結論できません。

serial 側はコピーと GEMV を default stream に順に積み、overlapped 側は2つの code buffer、copy stream、compute stream、event を使ってコピーと計算を重ねます。`--tpr` 自体が変えるのは GEMV の thread 数であり、両測定の比較結果として時間と比率が標準出力に表示されます。

実行には CUDA/HIP GPU backend を有効にしてビルドした `strata-overlap` が必要です。CMake は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` のときだけ GPU runtime とともにこの target を定義します。プログラムは `--file` の先頭から指定 expert 数（既定 64）分を読み、host pinned arena と CUDA device buffers を確保して処理します。`--tpr` は入力ファイルを変更せず、出力ファイルも作りません。

## 適用条件と副作用

- 指定値はこの実行の二つの GEMV 測定ループにだけ適用されます。GPU kernel 起動と同期を行い、処理時間を測ります。
- `strata-overlap` は実モデルの推論測定ではありません。ソースの注記によれば、CPU expert 経路、router、実トークンで stream する 1440 roles を再現しません。
- 入力の role-sized code 領域は host arena に読み込まれます。arena 確保に失敗すると `arena allocation failed` を stderr に出して終了コード 1 になります。CUDA API 呼び出し失敗もエラー名と CUDA エラー文字列を stderr に出して終了コード 1 になります。

## 出力とエラー

通常時は、1 role の形状・plane サイズと arena 状態を標準出力に表示し、最後に serial/overlapped の経過時間、expert あたり時間、両者の比率と、この測定がモデル化しない要素の注記を表示します。`--tpr` 専用の出力行はありません。

kernel 起動時に不正な `--tpr` が検出されると、CUDA 実装の診断文 `s_gemv_split: threads_per_row must be a power of two in 1..1024, got N` が stderr に出ます。入力ファイルを開けない場合や短い読み込みの場合は、それぞれ `cannot open ...`、`short read on expert N` が stderr に出て終了コード 1 です。GPU 呼び出しの非同期エラーは後続の stream 同期で検出されることがあります。

## 根拠

- `src/core/overlap_main.cpp:41-57` — 引数 parser、既定値 32、`--tpr` の `std::atoi` 変換、missing value と未知引数の失敗経路。
- `src/core/overlap_main.cpp:61-85` — 固定 GEMV 形状、arena 確保、入力読み込みとそのエラー経路。
- `src/core/overlap_main.cpp:87-103` — CUDA device buffer と stream の確保。
- `src/core/overlap_main.cpp:105-153` — serial/overlapped 両方の GEMV 呼び出しへの値の伝達と計測出力。
- `src/core/overlap_main.cpp:154-168` — 測定範囲の注意書き、buffer・event・stream の解放。
- `include/strata/kernels/s_gemv.hpp:48-60,76-83` — 行分割 GEMV と非同期 API の契約。
- `src/kernels/cuda/s_gemv.cu:388-405,467-473` — 1 block / 出力行、thread ごとの部分和と還元。
- `src/kernels/cuda/s_gemv.cu:478-528,538-543` — 1〜1024 の2冪 validation、shared memory サイズ、非同期経路では同期しない動作。
- `CMakeLists.txt:333-363` — GPU backend 有効時に `strata-overlap` target を定義する条件。

調査範囲は上記 checkout の parser、呼び出し先、関連 CMake 定義です。同一 revision の CLI `--help` や Release 配布バイナリは補助資料として確認していません。
