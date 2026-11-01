# `DS4_BT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースの全参照を検索。

## 役割

macOS で DeepSeek-V4.1 用の独立実行ファイル `strata-dsv41` が、`SIGSEGV`、`SIGBUS`、`SIGABRT` を受けたときに backtrace を標準エラーへ出す signal handler を登録します。通常の Strata 実行ファイル `strata` の設定ではありません。

## 値と判定

| 環境変数の状態 | 判定・動作 |
|---|---|
| 未設定 | handler を登録しない |
| 空文字を含む、何らかの値を設定 | 値の内容を検査せず handler を登録する |

実装は `std::getenv("DS4_BT")` の null 判定のみです。`1` との比較、数値変換、空文字判定はありません。したがって `DS4_BT=0` や `DS4_BT=false` も設定されていれば有効です。CLI 引数や他の環境変数による上書き・優先順位はありません。

## 有効になる条件

- `src/dsv41/ds4_main.cpp` が `__APPLE__` のときだけ環境変数を読みます。他 OS ではこの読み取りと登録コードがコンパイル対象になりません。
- 対象実行ファイルは独立した `strata-dsv41` です。CMake では `STRATA_BUILD_DSV41` が既定 OFF であり、このオプションを有効にしてビルドした場合に同ターゲットへ `ds4_main.cpp` が含まれます。
- Strata の設定ファイルや通常の `strata` 実行経路がこの変数を読むコードは見つかりませんでした。

## 実行時の詳細

`main()` の冒頭で、モデルや CLI オプションの処理に入る前に一度だけ環境を確認します。設定されている場合、`SIGSEGV` と `SIGBUS` の handler は backtrace を file descriptor 2（標準エラー）へ書き、それぞれ `_exit(139)`、`_exit(138)` で終了します。`SIGABRT` の handler も同様に backtrace を標準エラーへ書き、`_exit(134)` で終了します。未設定の場合、これらの独自 handler は登録されません。プロセス起動後に環境を変更しても、この起動時の判定は再評価されません。

## 根拠

- `src/dsv41/ds4_main.cpp:1284-1295` — `main()` 冒頭の macOS 条件、設定有無判定、および三つの signal handler と終了コード。
- `CMakeLists.txt:906-920` — DeepSeek-V4.1 が独立ターゲットであること、ビルドオプションが既定 OFF であること、および `strata-dsv41` に `src/dsv41/ds4_main.cpp` を含むこと。
- `docs/envvars/000_envvers.md:111` — 候補一覧への掲載。候補名以外の説明根拠には使用していません。
