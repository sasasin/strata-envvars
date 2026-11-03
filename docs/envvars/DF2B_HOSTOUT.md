# `DF2B_HOSTOUT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版の開発用 `dflash2_bench` で、DFlash2 の select kernel に渡す出力先を host 側バッファにするか device 側バッファにするかを選びます。これはベンチマーク専用の設定です。通常の `strata` 実行経路がこの変数を読む箇所は見つかりませんでした。

## 値と判定

`envi()` は変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で整数に変換します。`DF2B_HOSTOUT` の既定値は `0` です。

| 環境値 | `g_host_out` | 出力先とコピー |
|---|---:|---|
| 未設定、空文字 | 0 | select の出力先は `D.d_out`。`g_io` が真なら後続で `D.d_out` から `D.h_out` へコピー |
| 数値変換結果が 0 | 0 | 上記と同じ。例: `0`, `false`, `junk` |
| 数値変換結果が 0 以外 | 非 0 | select の出力先は `D.h_out`。この呼び出し箇所での `D.d_out` から `D.h_out` へのコピーは行わない |

`atoi()` は文字列全体の厳密な検証をしません。先頭の空白と符号の後にある数字部分を読み、数字が始まらなければ 0 になります。したがって `1`, `1tail`, `-1` はいずれも非 0 として扱われ、`true` は 0 として扱われます。整数型に収まらない入力の結果はこのコードから保証できません。

## 有効になる条件

- 変数の読み取り箇所は `sycl/src/kernels/dflash2_bench.cpp` だけです。CUDA/HIP 版や通常のエンジン起動時にこの名前を読む参照は確認できませんでした。
- 対象 executable `dflash2_bench` は SYCL CMake プロジェクトの `STRATA_SYCL_PARITY` 条件内で定義されています（この CMake option の既定値は ON）。通常の top-level 構成からは `STRATA_ENABLE_SYCL=ON` のときだけ SYCL サブプロジェクトへ進みます。
- `main()` のベンチマーク初期化で一度値を読み、グローバル変数に保存します。実行中の環境変更を再読込するコードはありません。
- `argv[1]` は `bench` / `test` などの実行モード選択に使われますが、`DF2B_HOSTOUT` の値を上書きしません。値が出力先に使われるのは `record_context()` の select 呼び出しです。
- `record_round()` の `io` 引数により `g_io` が設定されます。`g_io` が偽の場合、この呼び出し経路では追加の D2H コピーを行いません。グラフ計測経路はその外側で `D.d_out` から `D.h_out` へのコピーを明示的に記録しています。

## 実行時の詳細

`record_context()` は select kernel に、`g_host_out` が 0 以外なら `D.h_out` とその確率領域、0 なら `D.d_out` とその確率領域を渡します。0 の場合はさらに `g_io` が真なら `Q->memcpy(D.h_out, D.d_out, 64 * 4)` をキューに追加します。非 0 の場合はこのコピーを省きます。

この変数について、無効値を知らせる専用ログ、警告、終了コード分岐は実装されていません。変換後の 0/非 0 がそのまま出力先選択に使われます。ベンチマークの結果表示は既存の標準出力経路に従い、変数専用の表示はありません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — 未設定・空文字時の既定値処理と `std::atoi()` による変換。
- `sycl/src/kernels/dflash2_bench.cpp:203-207,255-256` — グローバル設定、select の出力先選択、条件付き D2H コピー。
- `sycl/src/kernels/dflash2_bench.cpp:259-271,894-901` — `g_io` の設定、ベンチマーク内の呼び出し、起動時の一度の読み取り。
- `sycl/src/kernels/dflash2_bench.cpp:551-564` — グラフ計測での compute-only 記録と外側の明示的な結果コピー。
- `sycl/CMakeLists.txt:289-290,437-438` — parity 条件内の SYCL `dflash2_bench` executable 定義。
- `CMakeLists.txt:12-21` — `STRATA_ENABLE_SYCL` による SYCL サブプロジェクト選択。
