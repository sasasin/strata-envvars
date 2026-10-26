# `STORE_TEST_THREADS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`tests/dsv41/store_test.cpp` の単体実行用プログラム `ds4_store_test` が `ExpertStore` の I/O queue に設定する worker 数を指定する。Strata の通常の `strata` / `strata-dsv41` 実行時設定ではなく、リポジトリ内での読み取りはこのテスト用ソースの1箇所だけである。CMake の `strata-dsv41` 実行ファイルのソース一覧にも `tests/dsv41/store_test.cpp` は含まれない。

## 値と判定

| 環境変数の状態 | テストプログラムが `cfg.threads` に設定する値 |
|---|---:|
| 未設定 | `8` |
| 設定あり（空文字を含む） | `std::atoi` の結果 |

`atoi` は10進整数として先頭から変換する。先頭空白と符号は受け付け、数字以降の文字列は変換に影響しない。数字として読める文字がない値（空文字、`abc` など）は `0` になる。値全体の検証、エラー報告、明示的な上限はこの呼び出し側にはない。

ただし、`ExpertStore::init()` は queue 作成時に `std::max(1, c.threads)` を渡す。このため、設定値が `0` または負数なら実際の I/O queue worker 数は `1`。正の値ならその値が渡される。

## 有効になる条件

`ds4_store_test` としてこのソースをビルドして実行した場合に限り適用される。調査した `strata-dsv41` の本体ターゲットにはこのテストソースが含まれず、ほかの本番ソースにも変数名の参照はない。従って、本体の `ExpertStore` 設定や通常の推論処理にこの環境変数が作用する根拠は確認できない。

## 実行時の詳細

プログラムが `ExpertStore::Cfg` を組み立てる際に環境を読み、値を `cfg.threads` に代入する。その設定を `st.init(cfg, ...)` に渡し、`ExpertStore::init()` が `IoQueue` を生成する時に worker 数として使う。値は起動中に一度この設定箇所で読み取られ、リクエストごとの再評価や子プロセスへの転送はない。

この変数専用のログや警告はない。プログラムの最終統計は読み込み量や待ち時間などを表示するが、worker 数を表示する処理は確認できない。

## 根拠

- `tests/dsv41/store_test.cpp:16-19` — 独立実行プログラムの `main` と usage。
- `tests/dsv41/store_test.cpp:45-53` — `STORE_TEST_THREADS` の読み取り、未設定時の `8`、および `ExpertStore::init()` への設定渡し。
- `src/dsv41/ds4_store.hpp:58-70,73-96` — `Cfg::threads` と `IoQueue(std::max(1, c.threads))`。
- `CMakeLists.txt:809-811` — `strata-dsv41` 本体ターゲットのソース一覧。この一覧にテスト用 `store_test.cpp` はない。
- ソース全体の完全名検索では `STORE_TEST_THREADS` の参照は `tests/dsv41/store_test.cpp:48` のみ。`docs/DETAILS.md` 等の製品向け資料にも記載は見つからなかった。
