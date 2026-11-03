# `DF2B_DUPN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench` が、`DF2B_DUP` で選んだ名前のカーネル起動を追加で何回実行するかを指定します。追加起動を含むベンチマーク時間を測り、選択したカーネルの反復コストを比較するための診断用設定です。通常の `strata` 推論実行からは読み取られません。

## 値と判定

起動時に共通 helper `envi()` が `std::getenv()` で読みます。未設定または空文字なら既定値 `1`、それ以外は `std::atoi()` の結果を使います。文字列全体の検証や範囲制限はありません。

| 環境値 | `g_dupn` | 追加起動の動作 |
|---|---:|---|
| unset / 空文字 | 1 | `DF2B_DUP` と一致した起動を各 layer で 1 回追加 |
| `1` | 1 | 同上 |
| 正の整数 `N`（`N != 1`） | N | `g_layer == 0` のときだけ N 回追加 |
| `0`、数字で始まらない文字列 | 0 | 追加起動なし |
| 負の整数 | 負数 | ループ条件を満たさず追加起動なし |

`atoi()` は先頭の空白と符号を許し、先頭の整数部分を読み、後続文字は無視します。たとえば `2tail` は 2、`tail2` は 0 です。値の範囲外入力に対する明示的な検査はありません。

## 有効になる条件

- `STRATA_ENABLE_SYCL=ON` で SYCL backend を構成し（CUDA/HIP との同時指定は CMake が拒否）、`STRATA_SYCL_PARITY=ON` のときに追加される `dflash2_bench` を実行する必要があります。`STRATA_SYCL_PARITY` の既定値は ON です。
- 追加起動は、別の環境変数 `DF2B_DUP` が空でなく、`DO(name, call)` の `name` と完全一致するときだけ起きます。`DF2B_DUP` が未設定または空なら `DF2B_DUPN` を設定しても効果はありません。
- `g_dupn == 1` なら layer 条件を問わず一致する起動を追加します。1 以外では `g_layer == 0` の場合に限って追加します。`record_block()` は layer ループで `g_layer` を 0 から 4 に設定します。一方 `record_context()` はこれを更新しないため、初回の context 処理では初期値 0、後続では直前の block 処理が残した 4 が参照されます。

## 実行時の詳細

`main()` の冒頭で一度読み、グローバル変数 `g_dupn` に保存します。後続の `getenv()` 呼び出しや再評価はありません。対象実行ファイルでは引数が `test` ならテスト、それ以外（引数なしを含む）は既定の `bench` へ進みますが、値の読み取り自体はモード分岐より前です。

`DO` マクロは通常の `call` を実行した後、`DF2B_DUP` と `name` が一致すると `g_dupn` 回、同じ `call` を追加実行し、最後に `D.stamp(name)` を呼びます。`record_block()` では `embed`、`gemm:qkv`、`attention` などの名前付き起動、`record_context()` では context 更新の起動が対象です。追加分も同じ in-order SYCL queue に投入されるため、ベンチマークの実行時間やプロファイル対象の区間に含まれます。重複起動そのものに対する専用のログや値の表示、無効値警告はありません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — `envi()` の unset / empty 判定と `atoi()` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:203-209` — `g_dup`、`g_dupn`、`g_layer` と追加起動を行う `DO` マクロ。
- `sycl/src/kernels/dflash2_bench.cpp:230-257` — layer ごとの `g_layer` 更新と、重複可能な名前付き起動。
- `sycl/src/kernels/dflash2_bench.cpp:259-272` — `record_round()` が context と block を実行する順序。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — `main()` での一度の読み取り、queue 作成、モード選択。
- `sycl/CMakeLists.txt:289-290,437-438` — parity オプションと `dflash2_bench` target。
- `CMakeLists.txt:14-21` — SYCL backend の opt-in と構成条件。
