# `STORE_TEST_NOCMP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前は Strata 本体の実行時設定ではなく、`tests/dsv41/store_test.cpp` のテスト用プログラムが、ExpertStore の読み出し内容を元ファイルと照合するサンプル比較を省くために読みます。候補一覧 `docs/envvars/000_envvers.md` にはありますが、ソース全体での参照はこの1箇所だけです。

## 値と判定

`std::getenv("STORE_TEST_NOCMP")` の結果が null かどうかだけを判定します。未設定なら比較を行い、値が設定されていれば比較を省きます。値の内容は parse されず、空文字も「設定あり」として比較を省きます。数値変換、境界値、無効値の扱いはありません。

## 有効になる条件

`ds4_store_test` に相当するテストプログラムを実行し、ループ内の `a % 17 == 0` の反復に到達した場合にだけ影響します。CMake の DeepSeek V4.1 ブロックには `strata-dsv41` や複数の `ds4_*_test` ターゲットがありますが、`tests/dsv41/store_test.cpp` または `ds4_store_test` のターゲット登録は確認できませんでした。したがって、この環境変数が通常の `strata` / `strata-dsv41` 実行に作用する根拠はありません。

## 実行時の詳細

テストは各反復で `st.ensure()` を呼び、`a % 17 == 0` の反復では、変数が未設定の場合、取得できた expert の3行列を `pread_full()` で元ファイルから読み、ExpertStore の内容と `memcmp()` で比較します。設定時はこの比較だけを飛ばします。ExpertStore の `ensure` / `release` や、その後の prefetch・shrink 処理はこの判定の外で続きます。

読み取りは比較対象となる反復ごとに行われ、static cache はありません。ソース内にこの環境値を変更する処理はないため、プロセス起動後の外部変更が反映されるとは確認できません。この変数による警告や専用ログはありません。最終行の `compared ... matrices` は実施した比較数を表示し、比較を省略すれば通常その数は減ります。差分が見つかった場合の終了コード `1` も比較結果に基づきます。比較を省いたデータの正しさは、この実行では検証されません。

## 根拠

- `tests/dsv41/store_test.cpp:1-4,16-18`: ファイル先頭の説明とテストプログラムの CLI。
- `tests/dsv41/store_test.cpp:64-82`: 反復ごとの `ensure`、設定有無によるサンプル比較の分岐、比較後の `release`。
- `tests/dsv41/store_test.cpp:105-111`: 比較件数と不一致数の出力、不一致数に基づく終了コード。
- `CMakeLists.txt:906-920,966-1008`: `STRATA_BUILD_DSV41` 配下の本体・テストターゲット一覧。`store_test.cpp` / `ds4_store_test` の登録はない。

