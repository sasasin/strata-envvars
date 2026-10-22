# `STRATA_GDN_CHUNK`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の実験ビルドで、prompt の Gated DeltaNet（GDN / DeltaNet）再帰計算に、従来の token ごとの recurrence の代わりに 64-token 単位の chunked recurrence を選びます。通常の recurrence は前 token の state に依存して token を順番に処理します。chunked 経路は chunk 内の処理を cumsum・行列計算・forward の段階に分け、chunk 間では state を順に引き継ぎます。演算順序が変わるため、同じ recurrence の計算ですが bit-exact ではありません。

環境変数は `gdn_recurrence_variant()` が呼ばれるたびに読みます。これは prompt の GDN 層を処理する `gdn_recurrence()` から呼び出されます。通常の decode recurrence ではなく、prefill の prompt 経路にある切替です。

## 値と判定

値は空でない場合に `std::atoi()` で整数へ変換されます。文字列全体の妥当性検査はありません。数値の prefix が変換され、変換できない文字列は 0 になります。

| 値 | `gdn_recurrence_variant()` の動作 |
|---|---|
| 未設定、空文字 | `chunk_env = -1`。chunked 経路を選ばない |
| `0`、または `atoi()` 結果が 0 | chunked 経路を選ばない |
| `1` など `atoi()` 結果が 1 以上 | `serial` でなく `T > 0` なら chunked を要求する |
| 負の整数（例: `-1`） | `chunk_env >= 0` が偽なので chunked 経路を選ばない |

したがって `1tail` は 1 として有効、`2tail` は 2 として有効、`true` や空白だけの値は 0 として無効です。先頭空白や符号は `atoi()` の変換規則に従います。数値として `2` 以上を指定しても、再帰経路を有効にする判定自体は `0` 以外の非負値かどうかです。

## 有効になる条件

- `STRATA_EXPERIMENTAL_SM60=ON` で構成した CUDA ビルドであること。通常の CUDA ビルドにはこの chunked Volta recurrence が組み込まれません。HIP ビルドではこの切替経路を使いません。
- `STRATA_GDN_REC_HEADS` が設定されていないこと。値が空でも設定されていれば `serial` が true となり、chunked dispatch は無効です。
- GDN recurrence の token 数 `T` が 64 以上であること。`T` が 1〜63 の場合は環境変数が有効値でも従来経路になります。
- `T > 0` であること。

`STRATA_GDN_CHUNK` の正値で chunked dispatch を要求した場合、64-token 境界までを chunked recurrence に渡し、残り 1〜63 token は従来の `gdn_rec_cols_pipe_kernel` で処理します。出力 norm は全 `T` token に対して実行されます。

コード上、chunked dispatch の条件には GPU compute capability の判定はありません。WMMA 実装を使えるかは別に判定されます。デバイスが cc 7.0 で WMMA の shared-memory 属性設定にも成功した場合に WMMA を選び、それ以外は FMA 実装へ進みます。つまり、実験ビルドで値を有効にしても、その GPU で WMMA が選べるとは限りません。

## 実行時の詳細

`gdn_recurrence_variant()` は未設定・空文字を `-1`、それ以外を `atoi()` の結果として扱います。`STRATA_GDN_REC_HEADS` が未設定で、`T > 0`、かつ変換値が 0 以上なら、0 以外の値で chunked を選びます。`T >= 64` のとき `T - T % 64` token を `gdn_chunk_recurrence()` に渡し、残りがあれば pipelined recurrence に渡します。

`gdn_chunk_recurrence()` も呼び出しごとに同じ変数を読みます。ここでは値がちょうど `2` の場合だけ WMMA を避け、FP32-only FMA scan を選びます。それ以外の chunked 有効値は、cc 7.0 で必要な CUDA 属性設定に成功していれば WMMA、それ以外なら FMA です。そのため `STRATA_GDN_CHUNK=1` は cc 7.0 で WMMA を試し、`=2` は FMA を強制します。

値は `static` にキャッシュされず、各 recurrence 呼び出し時に再評価されます。呼び出しの合間にプロセス環境が変更された場合、後続の呼び出しでは反映されます。chunk kernel は 64-token ごとの chunk を順番に処理し、scratch workspace を呼び出し間で再利用します。

## 関連資料と測定値

`docs/DETAILS.md` の `STRATA_GDN_CHUNKED` の説明は別の環境変数です。これは CUDA の別の GDN chunked recurrence と HIP gfx11 の経路を含み、`STRATA_GDN_CHUNK` の仕様や測定結果として扱えません。

Strata の `bench/results/2026-10-02-gdn-chunk/RESULTS.md` は、V100-SXM2-16GB（2 枚中 1 枚を使用）、CUDA 12.8、driver 570.x、`STRATA_EXPERIMENTAL_SM60=ON`、`CMAKE_CUDA_ARCHITECTURES=70` の build で、`bench/gdn_chunk_bench` を 5〜20 iteration 実行した結果を記録しています。そこでは chunked 経路は従来 recurrence より 4〜6 倍遅く、opt-in とされています。同資料の計測値であり、他の GPU・設定での性能を示すものではありません。

## 根拠

- `CMakeLists.txt:181-219,714-718` — 実験ビルドの設定と chunk source の CUDA 限定組み込み。
- `src/prefill/prefill.cpp:3235-3243` — prompt GDN 処理から `gdn_recurrence()` を呼ぶ経路。
- `src/prefill/kernels.cu:2609-2674` — `STRATA_GDN_CHUNK` の parse、serial / `T` 条件、および chunked dispatch 条件。
- `src/prefill/kernels.cu:2685-2692` — 64-token prefix と tail の処理、out norm。
- `src/prefill/gdn_chunk.cu:523-528,531-579,601-620` — HIP・compute capability の判定、`=2` による FMA 選択、WMMA / FMA の起動。
- `include/strata/prefill/gdn_chunk.hpp:8-12,50-53` — chunked recurrence の性質と数値演算順序。
- `docs/NVIDIA_V100.md:97-105` — V100 の opt-in switch 一覧。
- `bench/results/2026-10-02-gdn-chunk/RESULTS.md:1-26` — 計測条件と結果（実装の根拠ではなく測定記録）。
