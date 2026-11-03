# `DF2B_BIGALLOC_MB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench` の GEMM ベンチ開始時に、指定した MiB 数の device memory を確保して `1` で全域を書き込みます。これはベンチ環境のメモリ状態を作るための補助設定で、通常の `strata` 実行経路では参照されません。

## 値と判定

この名前は `envi()` helper を通して読み取られます。helper は変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で `int` に変換します。変換後の値が 0 なら確保を行わず、0 以外なら確保・書き込みへ進みます。

| 入力 | `envi("DF2B_BIGALLOC_MB", 0)` の結果 | この分岐での処理 |
|---|---:|---|
| 未設定、空文字 | 0 | 確保しない |
| `0`、`0abc`、数値で始まらない文字列 | 0 | 確保しない |
| `12`、`12abc` | 12 | `12 << 20` byte 相当を確保し、全域を書き込む |
| `-1` など負の非ゼロ値 | 負の `int` | 条件は真になり、`size_t` へ変換してから 20 bit 左シフトしたサイズで確保・書き込みを試みる |

`atoi` のため文字列全体の妥当性検証、下限・上限の clamp、負値の拒否はありません。数値の後ろにある非数字は変換時に無視されます。`int` の範囲を超える入力に対する処理もこのコードでは定義・検査されていません。

## 有効になる条件

- `sycl/CMakeLists.txt` では `STRATA_SYCL_PARITY` が ON のブロック内で `dflash2_bench` を build target に追加します。
- 実行時に `dflash2_bench` の位置引数が `gemm` のときだけ `run_gemm_bench()` に入り、この変数を読みます。引数なしの既定 `bench`、`test`、その他のモードではこの読み取り箇所に到達しません。
- `dflash2_bench` は `strata` エンジン本体とは別のベンチ用 executable です。

CLI のモード引数が実行経路を選び、環境変数は GEMM 経路内で追加の device allocation を制御します。別の環境変数との優先順位処理はありません。

## 実行時の詳細

`run_gemm_bench()` 冒頭で `envi()` を条件判定に 1 回、allocation サイズ計算と `memset` サイズ計算にそれぞれ 1 回呼びます。`envi()` 自体に cache はなく、各呼び出しで `getenv()` と `atoi()` を行います。通常の単一スレッド実行で環境が変わらなければ同じ値になりますが、3 回の読み取り結果を保存して再利用する実装ではありません。

条件が真なら `sycl::malloc_device()` による確保の後、同じサイズを `Q->memset(bp, 1, size).wait()` に渡します。この箇所には返されたポインタの null 検査、Strata 独自の警告、明示的な終了処理がありません。確保または queue 処理の失敗時の具体的な例外・終了動作は SYCL runtime 側に委ねられており、Strata のこの分岐からは特定できません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — `envi()` の未設定・空文字判定と `atoi()` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:614-620` — `run_gemm_bench()` の開始時に値を読み、device memory 確保と全域 `memset` を行う箇所。
- `sycl/src/kernels/dflash2_bench.cpp:899-902` — `main()` の既定モードと `gemm` を含むモード分岐。
- `sycl/CMakeLists.txt:288-291,437-438` — `STRATA_SYCL_PARITY` 条件内でベンチ executable を追加する箇所。
- `docs/envvars/000_envvers.md:142` — 候補一覧に名前がある箇所。この一覧自体は実装根拠ではありません。
