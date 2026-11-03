# `DS4_TEST_SAMPLE_FAIL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSV41 エンジンのサンプル token を host 側へ取り戻す `tok_back()` で、指定した回数目のサンプルを意図的に失敗扱いにするテスト用フックです。CUDA のコピー／同期エラーと同じく `-1` を返し、Project Maya #619 のサンプル失敗処理を確認する目的がコードコメントに記されています。通常の生成設定ではありません。

この名前の環境読み取りは `src/dsv41/ds4_model.cu` の `tok_back()` に一箇所あります。同関数は通常サンプル、speculative verify の置換サンプル、複数会話 verify の一部から呼ばれます。DSV41 のビルド自体はトップレベル CMake で既定 OFF の `STRATA_BUILD_DSV41` により選択されます。Metal 側も同じ `ds4_model.cu` をコンパイルします（`CMakeLists.txt:931-945`、`metal/CMakeLists.txt:132-146`）。

## 値と判定

`tok_back()` がプロセス内で初めて呼ばれたとき、`std::getenv()` の値を `std::atol()` で `long` に変換し、`fail_at > 0` の場合だけ呼び出し回数を数えます。文字列全体の検証や範囲制限はありません。

| 環境値 | 判定 |
|---|---|
| 未設定 | `fail_at = 0`。失敗を注入しない |
| 空文字、数字で始まらない文字列、`0`、負数 | 変換後が正数でないため注入しない |
| 正の整数（例: `1`, `3`） | その番号の `tok_back()` 呼び出しで一度 `-1` を返す |
| 数字の後ろに文字がある値（例: `2tail`） | `atol()` が先頭の数値部分を変換するため、`2` として扱う |

`atol()` のため、先頭の空白と符号も数値変換の対象です。数値範囲外の文字列に対する独自のエラー処理はありません。CLI 引数、設定ファイル、別の環境変数による上書きや優先順位もありません。

## 有効になる条件

- `tok_back()` を含む DSV41 エンジンをビルドし、そのサンプル経路を通ること。トップレベル CMake の `STRATA_BUILD_DSV41` は既定 OFF で、ON のときも `STRATA_HIP_GFX906` では DSV41 ターゲットを作りません（`CMakeLists.txt:931-945`）。Metal ビルドでも同じモデルソースを含みます。
- 値の変換結果が正数であること。
- そのプロセスで `tok_back()` が指定番号まで呼ばれること。ここで数えるのはリクエストごとではなく、同一プロセス内の呼び出しです。

すべてのサンプル経路がこのフックを通るわけではありません。たとえば DSV41 の複数会話 decode には `step_multi()` で複数行をまとめて処理する経路があり、この環境変数が指すのはあくまで `tok_back()` を呼ぶ経路です。

## 実行時の詳細

`tok_back()` は `d.tok` の device-to-host コピーと stream 同期の前に、静的な `fail_at` と `calls` を確認します。正数設定時、`calls` が設定値と一致した一回だけ stderr に `ds4 sample: injected failure (DS4_TEST_SAMPLE_FAIL=%ld)` を出して `-1` を返し、通常の CUDA コピー／同期は行いません。`fail_at` は初回呼び出し時に static 初期化されるため、その後の環境変更は反映されません。失敗注入後も `calls` は増え続けますが、一致判定は一度だけ成立します。通常のコピーまたは同期が失敗した場合も、別のログ `ds4 sample: <CUDA error text>` を出して `-1` を返します（`src/dsv41/ds4_model.cu:11167-11184`）。

直接の `Model::sample()` と speculative verify の `sample_row()` はどちらも `tok_back()` の戻り値を呼び出し元へ返します（`src/dsv41/ds4_model.cu:11223-11240,14453-14468`）。通常の単一会話 serve は負の token を stderr の `ds4 serve: the sample failed` とともにキャンセルし、生成済み token を `T -1` として送らず、`DONE ... cancel` を出します（`src/dsv41/ds4_main.cpp:1428-1432,1467-1477`）。通常の CLI decode は `strata-dsv41: the sample failed` を stderr に出して終了コード 1 で戻ります（`src/dsv41/ds4_main.cpp:2726-2733`）。speculative verify が失敗した場合は `round()` が `-1` を出力候補に加えるため、上記の単一会話側チェックで検出されます（`src/dsv41/ds4_main.cpp:308-327`）。

`--parallel` の serve scheduler では、`round()` が返した候補を `Act::tok` に設定してから次の `T` 行を書きます。該当箇所に負数をキャンセル扱いするチェックはありません（`src/dsv41/ds4_main.cpp:1607-1611,1637-1655`）。したがって、この経路では同じ `-1` が通常 serve と同じエラー処理になるとはコードから確認できず、フックを用いた検証ではこの相違に注意が必要です。

## 根拠

- 直接の読み取り、数値変換、process-wide 呼び出しカウント、注入ログと `-1` の返却、通常 CUDA エラー時の戻り値: `src/dsv41/ds4_model.cu:11167-11184`
- `sample_row()` と `Model::sample()` からの呼び出し: `src/dsv41/ds4_model.cu:11223-11240,14453-14468`
- speculative verify の `sample_row()` 呼び出し: `src/dsv41/ds4_model.cu:11297-11317`
- DSV41 build 条件とターゲット: `CMakeLists.txt:931-945`; Metal 側の同一モデルソース: `metal/CMakeLists.txt:132-146`
- 単一会話 serve の失敗処理と `DONE` 出力: `src/dsv41/ds4_main.cpp:1428-1432,1467-1477`
- CLI decode の失敗終了: `src/dsv41/ds4_main.cpp:2726-2733`
- `round()` が負の sample 結果も候補へ追加する処理、および `--parallel` scheduler の扱い: `src/dsv41/ds4_main.cpp:308-327,1607-1611,1637-1655`

`docs/DETAILS.md` にはこの変数の説明は見つかりませんでした。ビルドや実行による挙動確認は行わず、上記は対象 commit のソース記述に基づきます。
