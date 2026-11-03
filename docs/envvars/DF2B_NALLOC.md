# `DF2B_NALLOC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench gemm` を実行するとき、ベンチマーク本体の前に device memory の小さな allocation を追加で行います。回数 `i` ごとの要求サイズは `4096 + 64 * i` bytes です。Strata のエンジンやサーバーの通常実行経路が読む変数ではありません。`dflash2_bench` は SYCL の parity 用 CMake オプション `STRATA_SYCL_PARITY` が有効なときに追加される独立したベンチマーク実行ファイルです（既定値は ON）。

## 値と判定

共通 helper `envi(name, default)` は `getenv()` を呼び、変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を返します。`DF2B_NALLOC` の既定値は `0` です。

| 値 | 判定と効果 |
|---|---|
| 未設定、空文字 | `0`。追加 allocation なし |
| 整数として 0 | `0`。追加 allocation なし |
| 正の整数 `N` | ループを `N` 回実行し、サイズ `4096`, `4160`, `4224`, … bytes の allocation を順に要求 |
| 負の整数 | ループ条件が最初から偽になり、追加 allocation なし |
| その他の文字列 | `atoi()` が先頭から整数として読める部分を変換する。数字で始まらない文字列は `0` になり、数値の後ろの文字は無視される（例: `3junk` は 3）。先頭の空白と符号は `atoi()` の変換規則に従う |

値の検証、上限 clamp、無効値の警告や専用 fallback はありません。大きな正値を指定した場合の回数制限もコードにありません。

## 有効になる条件

- SYCL build で `STRATA_SYCL_PARITY` が有効になり、`dflash2_bench` がビルドされていること。
- 実行時の positional mode が `gemm` であること（`dflash2_bench gemm`）。引数省略時の既定 mode は `bench` で、この allocation loop は通りません。他の mode も同様です。
- `DF2B_NALLOC` 自体に CLI 引数や別環境変数による上書きはありません。CLI mode はこの処理を呼ぶかどうかだけを選びます。

## 実行時の詳細

`main()` は SYCL GPU queue を作成した後に mode を選び、`gemm` のときだけ `run_gemm_bench()` を呼びます。同関数は `DF2B_HOSTALLOC` や `DF2B_BIGALLOC_MB` による別の準備 allocation の後、`DF2B_NALLOC` の回数だけ `sycl::malloc_device(4096 + 64 * i, *Q)` を呼びます。戻り値は保存・検査されず、個々の allocation に対する明示的な失敗ログもありません。その後 `Q->wait()` し、device 名を表示して GEMM timing に進みます。

値は `envi()` を呼ぶたびに環境から読みます。特にこの loop の条件式は反復ごとに再評価されるため、値は static cache されません。Strata 内で環境変数を書き換える処理はこの経路にありません。allocation の失敗時に SYCL runtime が返す値や例外の詳細な挙動は、この Strata ソースだけからは確定できません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — `envi()` の読み取り、空文字時 fallback、および `atoi()` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:614-620` — gemm benchmark の準備 allocation、`DF2B_NALLOC` のループ、queue wait。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — queue 作成後の mode 分岐。`gemm` のみ `run_gemm_bench()` を選択し、省略時は `bench`。
- `sycl/CMakeLists.txt:288-291,437-438` — parity オプション（既定 ON）の条件内で `dflash2_bench` target を定義。
