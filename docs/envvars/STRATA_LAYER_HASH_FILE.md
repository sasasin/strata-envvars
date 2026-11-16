# `STRATA_LAYER_HASH_FILE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 実装の `Verifier::run()` が各レイヤーの CPU expert 処理を終えた後、GPU が host-visible memory に公開した activation rows・routed expert IDs・weights と CPU expert の出力 rows を FNV-1a でハッシュし、指定ファイルへ 1 行ずつ記録する診断用フックです。ハッシュ結果は検証・ログ用途に書き出されるだけで、生成や expert の選択を分岐させません（`sycl/src/core/verify.cpp:154-159, 2587-2600`）。

この読み取り・書き込みは `sycl/src/core/verify.cpp` にだけあります。通常の `Verifier::run()` 経路で有効で、別の `Verifier::service()` による pipelined window 経路には書き込み処理がありません（`sycl/src/core/verify.cpp:2278-2279, 2593-2600, 4183-4189, 4242-4260`）。

## 値と判定

値を真偽値として parse せず、ファイルパスとして扱います。`std::getenv` が `nullptr`（未設定）または先頭文字が NUL（空文字）なら出力を無効にします。それ以外は文字列全体を `std::fopen(path, "w")` に渡します。したがって `1`、`true`、`0`、空白を含む文字列なども、空でない限りパスとして扱われます。文字列の trim、大小文字変換、数値変換やパスの事前検証はありません（`sycl/src/core/verify.cpp:160-165`）。

| ビルド・条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の `Verifier::run()` 経路 | `getenv` が `nullptr` なので出力なし | 空でないパス。`fopen(..., "w")` が成功した場合にファイル出力 | 空文字。非空でもファイルを開けなければ `FILE*` が null となり出力なし |
| SYCL の pipelined `Verifier::service()` 経路 | 読み取り箇所なし | 該当なし | 値にかかわらずこのフックによる出力なし |
| SYCL 以外 | 対象名の読み取り箇所なし | 該当なし | 該当なし |

`docs/envvars/000_envvers.md` の機械生成メタデータは `parse: "flag"` としていますが、実装は真偽値ではなくパスを受け取り、`"0"` もファイル名として開こうとします（`sycl/src/core/verify.cpp:160-165`）。

## 有効になる条件

- `sycl/src/core/verify.cpp` を含む SYCL backend のビルドであること。CMake の `_engine` ソース一覧に同ファイルが含まれます（`sycl/CMakeLists.txt:257-264`）。
- `Verifier::run()` が実行され、レイヤーの doorbell と payload の待ち合わせを通過し、CPU expert pool の呼び出し後まで処理が到達すること（`sycl/src/core/verify.cpp:2278-2279, 2579-2593`）。
- 環境変数が最初の `layer_hash_file()` 呼び出し時点で非空であり、指定先を `"w"` モードで開けること（`sycl/src/core/verify.cpp:160-165`）。
- `Verifier::service()` を使う pipelined window は別経路であり、この出力処理を通りません。prompt の pipelined reader は `pipe && pl_pw >= 1 && STRATA_LOGPOS 未設定` の場合に `read_windows_pl()` へ分岐します（`sycl/src/program/generate.cpp:10881-10884`）。
- CLI 引数、設定ファイル、他の環境変数によるこの値の上書きや優先順位はありません。実装にその処理はありません（`sycl/src/core/verify.cpp:160-165`）。

## 実行時の詳細

`layer_hash_file()` 内の関数ローカル `static FILE*` が、初回呼び出し時に一度だけ環境変数を読みます。初回が未設定または空なら null を、非空なら `fopen(path, "w")` の結果をプロセス内に保持します。その後の環境変更は反映されません。ファイルは初回オープン時に `"w"` で開かれるため既存内容を切り詰めます（`sycl/src/core/verify.cpp:160-165`）。

`Verifier::run()` は doorbell payload の待ち合わせ後、`pool(...)` を呼び、続いて `windows` 番号・layer 番号・行数 `n` と4個のハッシュを書き出します。ハッシュ対象はそれぞれ `n * n_embd * 4` bytes の activation、`n * k * 4` bytes の routed IDs、同じく weights、`n * k * n_embd * 4` bytes の出力です。各ハッシュは初期値 `1469598103934665603`、乗数 `1099511628211` の byte-wise FNV-1a です（`sycl/src/core/verify.cpp:167-172, 2579-2600`）。

出力行は `window layer rows xhash idshash whash yhash` の順で、実際には各 hash を小文字の16桁16進数で出します。書き込みごとに `fflush` します。ファイルオープン失敗、`fprintf` / `fflush` の失敗を検査する分岐や専用ログはありません。また、この関数から `fclose` されず、FILE はプロセス終了まで保持されます（`sycl/src/core/verify.cpp:160-165, 2593-2600`）。

## ログと測定値

このフック固有の stdout/stderr メッセージはありません。観測できる出力は指定ファイルへの行です。Strata の `docs/DETAILS.md` に本変数の説明や測定値は見つかりませんでした。ハッシュ差分を用いて二つの実行を比較する用途はソースコメントに記載されていますが、ここでは性能・正確性の測定値を主張しません（`sycl/src/core/verify.cpp:154-159`）。

## 根拠

- `sycl/src/core/verify.cpp:154-172` — 用途コメント、パスの読み取りとファイルオープン、FNV-1a 実装。
- `sycl/src/core/verify.cpp:2278-2279, 2579-2600` — 通常の `run()` における pool 呼び出し後の出力、行フォーマット、hash 対象、flush。
- `sycl/src/core/verify.cpp:4183-4189, 4242-4260` — `service()` が別の pipelined 経路であること。
- `sycl/src/program/generate.cpp:10881-10884, 10810-10828` — `STRATA_LOGPOS` と `read_windows_pl()` を使う prompt pipeline 経路。
- `sycl/CMakeLists.txt:257-264` — SYCL engine に `verify.cpp` が含まれること。
