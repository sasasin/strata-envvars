# `STRATA_PLE_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL ビルドの PLE 直接 I/O reader が、行読み込みの ticket を回収するとき、待ち時間を分けて `stderr` に出す診断用スイッチです。PLE の有効化、読み込み方式、読み込む行、計算結果を選ぶ変数ではありません。環境変数が設定されている場合も PLE の読み込みと decode は通常の分岐で進み、追加されるのは時刻の記録とトレース行の出力です（`engine/sycl/src/ngram/ple_reader.cpp:97-100,157-168,256-263,509-545`）。

この読み取りは SYCL 用 `engine/sycl/src/ngram/ple_reader.cpp` にあります。SYCL の CMake は共通 `engine/src/kernels/ngram.cpp` とこの reader を一緒に `strata_kernels` へ含めます（`engine/sycl/CMakeLists.txt:278-287`）。CUDA 系の CMake は同じ `ngram.cpp` と別の `engine/src/ngram/ple_reader.cpp` を含みますが、後者には変数の読み取りも trace 出力もありません（`engine/cmake/strata_gpu_engine.cmake:104-106`; `engine/src/ngram/ple_reader.cpp:98-103`）。従って、この変数の効果は SYCL reader の実装に限られます。

## 値と判定

`ple_trace()` は `std::getenv("STRATA_PLE_TRACE") != nullptr` の結果だけを使い、文字列を parse しません。関数内の `static const bool` に保存され、最初の呼び出しで判定されます（`engine/sycl/src/ngram/ple_reader.cpp:97-100`）。

| 条件 | unset | 設定されている値 | 判定 |
|---|---|---|---|
| SYCL reader | trace 無効 | `1`、`0`、`true`、`false`、空文字、その他任意の文字列 | すべて trace 有効（値の内容・大文字小文字・空白・数値としての妥当性は検査しない） |
| `engine/src/ngram/ple_reader.cpp` を使うビルド | 読み取りなし | 読み取りなし | この変数による動作なし |

したがって、SYCL では空文字や `0` も「設定あり」です。CLI 引数による値の上書きや、無効値時の fallback はありません。最初の `ple_trace()` 呼び出しより後にプロセス環境を変えても、そのプロセスの判定は変わりません。

## 有効になる条件

- SYCL 用 reader が組み込まれた実行ファイルを使い、PLE の `Direct` I/O reader が ticket を処理する必要があります。共通 `PleTable` は `--ple-io direct` のときだけ `PleReader::open()` を呼びます。`--ple-io mmap` または `ram` は mapped table 経路なので、この trace は出ません（`engine/src/program/generate.cpp:6264-6276`; `engine/src/kernels/ngram.cpp:449-465`）。
- PLE table を開いている必要があります。`--no-ple` などで PLE が使われない場合は reader が動きません（`engine/src/program/generate.cpp:6269-6289`; `engine/sycl/src/core/layer.cpp:1670-1680`）。
- 自動 residency policy が PLE の方式を `mmap` に切り替えた場合も reader を通りません。明示的な `--ple-io` は自動切替の条件から除外されます（`engine/src/program/generate.cpp:6303-6307,6351-6367`）。
- `--ple-sync-submit` を指定すると reader は caller thread で処理します。同期モードの `collect()` には `ple trace` の `fprintf` がないため、変数が設定されていても行は出ません（`engine/src/program/generate.cpp:6274-6276,3901-3905`; `engine/sycl/src/ngram/ple_reader.cpp:509-545`）。
- threaded `collect()` で正常に回収され、ticket の読み込み job 数が `1..199` の場合に限って行を出します。job 数 `0` または `200` 以上では出力されません。読み込みエラー時も出力条件へ進む前に `false` で返るため、trace 行はありません（`engine/sycl/src/ngram/ple_reader.cpp:509-530`）。

## 実行時の詳細

通常の `strata generate` は `--ple-io` の既定値を `direct` とし、PLE table が指定されれば direct reader を開きます。direct reader はデフォルトで worker thread を使い、decode では `ple_issue_token()` が行読み込みを開始し、埋め込み処理後の `ple_finish_token()` が `PleTable::collect()` を呼んで結果を待ちます（`engine/src/program/generate.cpp:817-823,6264-6289`; `engine/src/kernels/ngram.cpp:639-647,666-678`; `engine/sycl/src/core/layer.cpp:1670-1689`; `engine/sycl/src/program/generate.cpp:13463-13484`）。

設定ありの場合、reader は最初の job の submit 時刻と最後の行コピー完了時刻を記録します。正常な threaded `collect()` の終了時に次の形式で `stderr` へ出します。時間の単位はすべてマイクロ秒です（`engine/sycl/src/ngram/ple_reader.cpp:157-168,256-263,523-530`）。

```text
ple trace: %3u jobs  issue->submit %8.1f  submit->last %8.1f  last->return %8.1f  collect wait %8.1f us
```

各値は ticket 作成から最初の submit まで、最初の submit から最後の行コピー完了まで、最後の行コピー完了から `collect()` の出力直前まで、そして `collect()` の呼び出しから待ち解除までです。job は未キャッシュ行のページ読み込みをまとめた数です（`engine/sycl/src/ngram/ple_reader.cpp:454-492,523-530`）。このトレース分岐は読み込み job の選択や PLE 行の decode を切り替えません。

`collect()` が失敗した場合は reader のエラーを返し、SYCL の `ple_finish_token()` が `ple_finish_token: ` を前置します。generate 呼び出し側は `strata generate: <error>` を stderr に出して終了コード `1` を返します。失敗時には `ple trace:` 行は出ません（`engine/sycl/src/ngram/ple_reader.cpp:520-522,524-530`; `engine/sycl/src/core/layer.cpp:1678-1681`; `engine/sycl/src/program/generate.cpp:13482-13484`）。この環境変数自体が警告、終了、I/O failure を起こす処理はありません。

## ログと測定値

ログ文言は上記の `ple trace: ... us` です。`docs/DETAILS.md` にこの変数の測定値や性能効果の記述は見つからず、コードも速度向上・低下の値を示していません。トレースは待ち時間を観測するための出力であり、測定値の主張はありません。

## 根拠

- `engine/sycl/src/ngram/ple_reader.cpp:97-100` — 設定有無だけを見る判定と初回呼び出し時の static cache。
- `engine/sycl/src/ngram/ple_reader.cpp:157-168,256-263,509-545` — job 時刻記録、出力形式・出力条件、同期経路と失敗経路。
- `engine/sycl/CMakeLists.txt:278-287` — SYCL の reader と共通 PLE table 実装の組み込み。
- `engine/src/ngram/ple_reader.cpp:98-103` — 非 SYCL reader に同変数の読み取りがないこと。
- `engine/src/program/generate.cpp:6264-6289,6303-6307`; `engine/src/kernels/ngram.cpp:449-465,639-647,666-678` — PLE table の direct/mmap 選択と reader の呼び出し。
- `engine/sycl/src/core/layer.cpp:1670-1689`; `engine/sycl/src/program/generate.cpp:13463-13484` — decode 呼び出し、エラーの stderr 出力と終了コード。
- `engine/cmake/strata_gpu_engine.cmake:104-106` — CUDA 系の別 reader 実装。
