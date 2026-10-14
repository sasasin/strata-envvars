# `STRATA_NVFP4_PREFETCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

NVFP4 の CPU 行カーネルが、重みブロックを処理するときに発行するソフトウェア prefetch の先読み距離をバイト単位で指定する。対象は Strata 独自の AVX-512 / AVX2 NVFP4 カーネルで、ゲート・アップ行と down 行の両方に使われる。CUDA/HIP の NVFP4 カーネルにはこの変数の読み取りはない。

## 値と判定

| 環境変数の状態・値 | カーネル内の値 | 動作 |
| --- | ---: | --- |
| 未設定 | `2048` | 各 NVFP4 ブロック処理で、現在の重みブロック先頭から2048バイト先を prefetch する |
| 空文字 | `0` | prefetch を発行しない |
| 整数として `0` | `0` | prefetch を発行しない |
| 正の整数 | `atoi` の変換結果 | そのバイト数先を prefetch する |
| 負の整数 | 負値 | `> 0` の条件を満たさず、prefetch を発行しない |
| 数字で始まらない文字列 | `0` | `atoi` の結果が0なので、prefetch を発行しない |

読み取りは `std::atoi` であり、文字列全体の厳密な数値検証はしない。したがって、先頭に整数として読める部分がある文字列はその部分が変換され、例えば `128x` は128として扱われる。未設定と空文字は異なる。コードに clamp や距離の上限確認はない。

## 有効になる条件

- 対象は NVFP4 expert の CPU 処理で、実行時 CPU 機能判定を通り、対象次元 `n` が NVFP4 ブロック幅に整合し、ブロック数がカーネルの上限以内である必要がある。AVX-512 が使える場合は通常 AVX-512 経路が先に選ばれ、選べない場合は AVX2 経路が候補になる。
- `STRATA_NO_NVFP4_512` が設定されていれば AVX-512 経路を選ばず、`STRATA_NO_NVFP4_256` が設定されていれば AVX2 経路を選ばない。設定有無の判定なので、空文字を含め、値が存在すればその経路を無効にする。両経路が使えなければ `ggml-cpu` の dot 経路へ進み、この変数は使われない。
- 実際の prefetch 命令は、先読み距離が正の場合に限り発行される。AVX-512 と AVX2 のそれぞれの翻訳単位に独立した設定値がある。

## 実行時の詳細

AVX-512 と AVX2 の `prefetch_distance()` は、初回呼び出し時に関数内 `static const int` を初期化する。そのため、環境変数はプロセス起動時ではなく、その翻訳単位の NVFP4 行カーネルが最初に使われた時点で読み取られ、以後の環境変更は同じカーネル内の値に反映されない。各 `row_dot` は NVFP4 重みブロックを走査し、各ブロックで距離が正なら `_mm_prefetch(..., _MM_HINT_T0)` を実行する。これは行カーネルに対するヒントであり、結果の数値計算を変える分岐ではない。

同梱診断・ベンチマーク `nvfp4_avx512_parity` にも環境変数の読み取りがある。`--bw` の表示で prefetch 値を出すためのもので、未設定時には `2048` と表示する。明示的な空文字なら表示欄は空になる一方、カーネル側では `atoi("") == 0` として prefetch が無効になる。この診断プログラムは通常の Strata サーバー動作とは別の実行ファイルである。

## 根拠

- `src/kernels/cpu/nvfp4_avx512.cpp:47-55` と `src/kernels/cpu/nvfp4_avx2.cpp:47-55`: 変数の読み取り、`atoi`、未設定時の2048、初回呼び出し時の static cache。
- `src/kernels/cpu/nvfp4_avx512.cpp:100-110` と `src/kernels/cpu/nvfp4_avx2.cpp:93-103`: 各重みブロックで正の距離だけ prefetch を発行する。
- `src/kernels/cpu/native_expert.cpp:194-218, 233-278`: NVFP4 のゲート・アップ／down 行処理で AVX-512、AVX2、`ggml-cpu` の順に条件付きで選択する。
- `src/kernels/cpu/nvfp4_avx512.cpp:152-179` と `src/kernels/cpu/nvfp4_avx2.cpp:161-178`: 次元がブロック幅に整合すること、カーネルが複数 token を分割して処理すること。
- `src/kernels/cpu/expert_layout.cpp:41-73, 110-143`: AVX-512 / AVX2 の CPU・OS 状態判定。AVX-512 は AVX512F/BW/VL/VNNI 等、AVX2 は FMA/F16C/AVX と OS の AVX 状態保存を確認する。
- `src/kernels/cpu/nvfp4_avx512_parity.cpp:193-248` と `CMakeLists.txt:1607-1611`: `--bw` のベンチマーク表示と CPU parity 実行ファイルの登録。
- `docs/NVFP4.md:166-180`: CPU NVFP4 カーネルの概要と測定条件。`STRATA_NVFP4_PREFETCH` 自体の既定値や意味は文書化されていないため、上記は実装から確認した内容である。
