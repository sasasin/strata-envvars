# `DF2B_POS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL と Metal の DFlash2 ベンチマークで、合成 ring の現在位置を指定します。履歴タグと各ラウンドの位置メタデータを作るための診断・測定用設定です。Strata の通常の推論・サーバー経路では読み取られません。

## 値と判定

両実装とも、空でない値は `std::atoi()` で整数に変換し、数値全体の検証や範囲チェック、clamp はしません。先頭の空白や符号に続く整数部分が変換され、数字の後ろの文字は無視されます。数字で始まらない非空文字列は `atoi` の結果 0 になります。変換可能範囲を超える値について、Strata 側に検査や fallback はありません。

| 値 | SYCL `dflash2_bench` | Metal `df2_bench` |
|---|---:|---:|
| 未設定 | 600 | 600 |
| 空文字 | 600（helper が既定値を返す） | 0（設定ありとして `atoi("")` に渡す） |
| `0`、負数、整数 | 変換した整数をそのまま使用 | 変換した整数をそのまま使用 |
| `12tail` | 12 | 12 |
| `true`、`text` | 0 | 0 |

## 有効になる条件

- SYCL では独立した `sycl/` build の `dflash2_bench` が対象です。実行モードが `bench`（引数省略時の既定）または未知のモード名のとき `run_bench()` が呼ばれ、この変数を読みます。`test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` モードでは読みません。ターゲットは `STRATA_SYCL_PARITY` が ON の場合に定義され、このオプションの既定値は ON です。
- Metal では macOS 向けの独立した `metal/` build が `metal/tests/*.cpp` から個別実行ファイルを作り、その一つとして `df2_bench` をビルドします。`df2_bench` の `main()` が実行開始時に読み取ります。
- どちらも通常の `strata` 推論・サーバー実行ファイルには組み込まれません。SYCL の `argv[1]` は実行モードを選び、Metal の `argv[1]` は kernel directory を指定します。これらの引数や他の環境変数が `DF2B_POS` を上書きする処理はありません。

## 実行時の詳細

SYCL は `run_bench()` の開始時に一度読み、ローカル定数 `POS` に保持します。`reset_ring()` は `POS` より前の最大 `RING - 16` 個分の位置タグを合成 ring に設定し、各 warm-up・測定ラウンドでは `set_meta()` に `POS` を渡して context と anchor の位置メタデータを作ります。`config: ring pos ...` の行に採用値が stdout 出力されます。負数の場合、`reset_ring()` のタグ設定ループは開始位置が `max(0, POS - (RING - 16))`、終了位置が負の `POS` となるため実行されませんが、負の位置はその後のメタデータには渡されます。値の妥当性を検査する処理はなく、範囲外値での結果は保証されません。

Metal は `main()` の起動時に一度読み、`POS` としてベンチマーク内で使います。context position の 8 行に `POS - 8` から `POS - 1` を設定し、anchor position に `POS` を設定します。`config: pos ...` の行に採用値を stdout 出力します。値による専用の警告、エラー、終了分岐はありません。読み取り値は static cache ではなくローカル変数ですが、いずれの実行経路にも再読込はありません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56-57`: `envi()` の unset／空文字処理と `atoi` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:174-188`: ring のタグ設定範囲と位置メタデータの生成。
- `sycl/src/kernels/dflash2_bench.cpp:486-512,525-583`: `POS` の読取・ring 初期化・表示、および warm-up、direct launch、graph、profile 経路での再利用。
- `sycl/src/kernels/dflash2_bench.cpp:894-901`: モード選択と `run_bench()` への既定・fallback 経路。
- `sycl/CMakeLists.txt:288-291,437-438`: `STRATA_SYCL_PARITY` の既定値と `dflash2_bench` ターゲット。
- `metal/tests/df2_bench.cpp:62-82`: Metal ベンチの起動、`DF2B_POS` の unset 判定、変換、既定値。
- `metal/tests/df2_bench.cpp:278-283,441`: `POS` からの context／anchor position 設定と表示。
- `metal/CMakeLists.txt:1-11,41-48`: Metal の独立 build と `tests/*.cpp` からの実行ファイル生成。
