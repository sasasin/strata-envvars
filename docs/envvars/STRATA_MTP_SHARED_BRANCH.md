# `STRATA_MTP_SHARED_BRANCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP draft layer の MoE 計算で、shared expert を router と routed experts の計算と別 stream / queue に分岐させるかを制御します。分岐を有効にすると shared expert の計算を先に side stream / queue へ投入し、routed experts の処理と並行させ、combine の前に完了を待ちます。無効の場合は routed experts の処理後、同じ主 stream / queue 上で shared expert を計算します。MTP drafter の当該処理を実行しないプロセスでは効果はありません。

## 値と判定

HIP ビルド以外では `std::getenv()` で取得した値を `std::atoi()` に渡し、結果が 0 でなければ分岐を有効にします。文字列全体の妥当性検査はありません。`atoi` が先頭の空白と符号付き10進数を読めるため、たとえば `2`、`-1`、`1junk` は有効、`0`、`0junk`、空文字、数値に変換できない文字列は無効です。

| ビルド | 未設定 | 設定時 |
|---|---|---|
| CUDA / SYCL（非-HIP） | 有効 | `atoi(value) != 0` のとき有効 |
| HIP | 無効 | 値を読み取らず、常に無効 |

判定値は関数内の `static const bool` に保存されます。最初に MTP draft 関数がこの判定へ到達した後、プロセス内で環境変数を書き換えても再評価されません。明示的なログ出力や値不正時の警告はありません。

## 有効になる条件

- MTP drafter のこの MoE 実行経路に入ること。
- 非-HIP ビルドであり、環境変数が未設定、または設定値の `atoi()` 結果が非ゼロであること。
- HIP では常に無効。HIP 用実装は side stream / event を作らず、shared expert を主 stream で実行します。

この値は shared expert の並列実行方法を切り替えます。shared expert の出力は routed expert の計算と別の `shared_` バッファに書かれ、両方の完了後に combine が実行されます。

## 実行時の詳細

CUDA 実装は未設定を既定 ON とし、`STRATA_USE_HIP` のビルドでは環境変数の読み取り自体をコンパイル時に除外して OFF に固定します。CUDA は drafter 初期化時に side stream と fork/join event を作成します。分岐 ON では主 stream 上で fork event を記録し、side stream がそれを待ってから shared expert を実行します。同時に主 stream は router と routed experts を処理し、routed experts の処理後に join event を待ってから combine に進みます。分岐 OFF では routed experts の処理後、主 stream 上で shared expert を実行してから combine します。

SYCL 移植版にも同じ値判定があります。side queue と event を用いて shared expert の投入を分岐し、combine の前に queue barrier で合流します。いずれの実装も分岐設定を理由とする標準出力・標準エラーのログは出しません。stream / event / barrier の失敗時は `err` に `mtp: the shared expert's branch` または `mtp: the shared expert's join` を設定して処理を失敗させます。

## 根拠

- `src/core/mtp.cpp:867-895` — 値の読み取りと既定値、CUDA の fork、shared expert の side stream 実行と join event 記録。
- `src/core/mtp.cpp:914-923` — routed experts の後に join を待つ経路、および分岐 OFF 時の shared expert 実行。
- `src/core/mtp.cpp:433-440` — 非-HIP ビルドで side stream と event を初期化し、HIP はその初期化を除外。
- `sycl/src/core/mtp.cpp:1001-1045,1059-1070` — SYCL 移植版の値判定、shared expert の queue 分岐と combine 前の合流。
- `sycl/src/core/mtp.cpp:523-529` — SYCL queue と event の初期化。
- `cmake/hip_backend.cmake:89` — HIP runtime target に `STRATA_USE_HIP=1` を定義。

`docs/DETAILS.md` と関連 docs には、この環境変数の挙動や測定値の説明を確認できませんでした。したがって性能差や出力同一性については記載していません。
