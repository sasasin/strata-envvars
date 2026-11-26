# `STRATA_INJECT_FATAL_ONCE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は fatal GPU error の**テスト用注入**を複数の engine 起動にまたがって一度だけ発生させるためのマーカーファイル名です。この変数だけでは注入は起きません。`STRATA_INJECT_FATAL` が指定する decode-window 回数に達したとき、ここで指定されたファイルを開き、既に読み取り可能なら注入を抑止し、まだ開けなければ作成を試みたうえで fatal error を注入します。通常の GPU エラー判定や生成設定を変更する変数ではありません。読み取りと分岐は `engine/src/program/generate.cpp:3634-3648` にあります。

## 値と判定

値は数値や真偽値として parse されず、`fopen` に渡すパス文字列です。未設定 (`getenv` が null) または空文字列 (`*once == '\0'`) ならファイル確認をせず、注入条件に達した際は抑止されません。`0`、`1`、`true`、`false`、`0anything` も特別扱いされず、そのままファイル名として扱われます。大文字小文字・空白・数値妥当性の検査やパス正規化はこの箇所にありません。パスが実際に開けるかは `fopen` の結果で決まります（`engine/src/program/generate.cpp:3638-3645`）。

| 条件 | unset | 設定時に抑止する条件 | 注入を抑止しない例 |
|---|---|---|---|
| `STRATA_INJECT_FATAL` による注入条件が成立 | マーカーを確認せず注入 | 空でない値を `rb` で開ける（ファイル内容は読まない） | 空文字、存在しないパス、読み取りで開けないパス。`wb` 作成が失敗しても注入は続く |
| 注入条件が不成立 | 変数を読まない | なし | `STRATA_INJECT_FATAL` 未設定・0以下、または N 回目の確認に未到達 |

`rb` で既存ファイルを開けると `fire=false` になり、内容・長さ・中身の値に関係なく注入を止めます。開けない場合は `wb` で作成を試しますが、作成成功の有無にかかわらず `fire` は true のままです。従って、無効なパスや書き込み不能な場所では一度限りの保証はありません。マーカー作成は fatal 終了より前なので、同じパスが次の engine 起動から読み取り可能なら、その起動以降は注入を抑止します。コードがマーカーを削除する処理はありません（`engine/src/program/generate.cpp:3641-3645`）。

## 有効になる条件

- `STRATA_INJECT_FATAL` が正の数として `std::atol` で変換され、engine 内で数える確認回数がその数に一致する必要があります。`STRATA_INJECT_FATAL` は関数内 `static` に一度だけ読み込まれます。未設定は 0、先頭が数値でない文字列は `atol` により 0、数値の後ろに文字があれば数値部分を使います。`STRATA_INJECT_FATAL_ONCE` の値だけでは有効化されません（`engine/src/program/generate.cpp:3634-3645`）。
- カウント対象は `exit_if_gpu_fatal` の呼び出しで、decode window の前に行う呼び出しが明示的に「test hook counts windows」とされています。別の warm-up failure、verify/commit failure、commit wait failure の呼び出しも同じ関数を通ります。従って N は単純な全リクエストの token 数ではなく、この engine プロセスでの該当確認呼び出し数です（`engine/src/program/generate.cpp:16383-16387`, `22981-22993`, `23066-23070`, `23346-23350`）。
- 読み取り箇所は CUDA/HIP engine の `engine/src/program/generate.cpp` にあります。候補名の全参照検索では SYCL と Metal の実装に読み取り箇所はありません。CUDA/HIP ターゲットがこのファイルから `strata` を作ることは `engine/cmake/strata_gpu_engine.cmake:548-551` にあります。SYCL と Metal はそれぞれ別の `generate.cpp` をビルドしています（`engine/sycl/CMakeLists.txt:34-41`, `engine/metal/CMakeLists.txt:176-177`）。
- CLI 引数や他の設定による `STRATA_INJECT_FATAL_ONCE` の上書きはこの実装にありません。サーバーから engine に値を渡す処理もこの変数については見つかりませんでした。プロセス環境に設定された値を engine が参照する箇所だけを確認しています。

## 実行時の詳細

`exit_if_gpu_fatal` の最初に `STRATA_INJECT_FATAL` の数値と `windows` カウンターを関数内 `static` として保持します。各呼び出しでカウンターを進め、指定回目にだけ `STRATA_INJECT_FATAL_ONCE` を `getenv` します。対象変数自体は static cache されず、その判定時点の engine プロセス環境を読みます。親プロセス側で engine 起動後に環境を変えても子プロセスへは伝わりません。同じ engine プロセス内で環境が変更されれば、注入判定時に読まれる値には反映されます。同一プロセスで注入条件が成立するのは一度だけです（`engine/src/program/generate.cpp:3634-3645`）。

マーカーが読めず注入する場合、`exit_gpu_fatal` は stderr に `strata serve: fatal GPU error (injected (STRATA_INJECT_FATAL): an illegal memory access was encountered): the engine ends so that the server can start it again`、stdout に `ERR fatal GPU error: injected (STRATA_INJECT_FATAL): an illegal memory access was encountered` を出して flush し、終了コード 3 で `_Exit` します。通常の fatal GPU error も同じ終了関数を使います（`engine/src/program/generate.cpp:3627-3632`, `3645`）。

サーバーはこの `ERR fatal GPU error` 行を受けると処理中の要求を engine death として失敗させます。サーバー側の説明では要求は 503 となり再送可能で、次の要求で engine を再起動します。fatal GPU error による engine 終了が 10 分間に 3 回になると、サーバーは再起動を止め、10 分経過後の要求で再試行します（`terminal/serve/server.py:1660-1669`, `4798-4824`, `4960-4971`）。

## ログと測定値

測定値はありません。このフックが発火すると、上記の stderr/stdout の fatal error 行と終了コード 3 が観測されます。ファイルが `rb` で開けた場合はこのフック由来のログを出さず、通常の sticky GPU error 判定へ進みます。サーバーが fatal error を認識した際は stdout に `[strata] the GPU reported a fatal error (...)` で始まる行を出します（`terminal/serve/server.py:4817-4819`）。

## 根拠

- `engine/src/program/generate.cpp:3622-3632` — fatal GPU error 時の stderr/stdout と即時終了。
- `engine/src/program/generate.cpp:3634-3648` — `STRATA_INJECT_FATAL` の parse、対象変数の読み取り、マーカー判定と注入条件。
- `engine/src/program/generate.cpp:16383-16387`, `22988-22993`, `23066-23070`, `23346-23350` — 同じ判定関数を呼ぶ warm-up、decode window、commit、commit wait の経路。
- `terminal/serve/server.py:1660-1669`, `4798-4824`, `4960-4971` — サーバー側の要求失敗、fatal 終了の回数制限、再起動。
- `engine/cmake/strata_gpu_engine.cmake:548-551`, `engine/sycl/CMakeLists.txt:34-41`, `engine/metal/CMakeLists.txt:176-177` — backend ごとの engine ソース。
