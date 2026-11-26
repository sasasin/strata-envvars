# `STRATA_DBG_DRAFT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL 版の `strata generate` で投機的デコードの各検証窓について、検証に使った token ID 列と target が返した token ID 列、および採用された draft 数を stderr に出す診断用フラグです。検証窓や採用結果を変える処理ではなく、既存の窓・出力を表示するだけです（`engine/sycl/src/program/generate.cpp:14033-14060,14114-14117,14160-14166`）。

名前を環境から直接読む箇所は `engine/sycl/src/program/generate.cpp:14162` の一つです。候補レジストリも backend を `sycl`、状態を「off unless set」と記録しています（`terminal/data/settings-register.json:4843-4857`）。

## 値と判定

`std::getenv("STRATA_DBG_DRAFT") != nullptr` の設定有無判定です。値の文字列や数値は変換・比較しません（`engine/sycl/src/program/generate.cpp:14162`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の `strata generate` が投機的デコード窓を実行 | 出力しない | 空文字、`0`、`1`、`true`、`false`、その他どの設定値でも出力する | 該当なし（環境変数が存在すれば有効） |
| CUDA/HIP backend | この名前を読む実装箇所なし | 該当なし | 該当なし |

空文字も設定済みなので有効です。大文字小文字、前後空白、数値としての妥当性、`0anything` のような内容は判定に影響しません。既定状態は未設定（出力なし）です。CLI 引数や別環境変数による上書き・優先順位はありません。

## 有効になる条件

- `STRATA_ENABLE_SYCL=ON` で構成される実験的 SYCL backend の実行ファイルであること。SYCL は CUDA/HIP と同時に構成できず、CMake の既定値は OFF です（`engine/CMakeLists.txt:23-32`）。
- `strata generate` が投機的デコード部へ進み、少なくとも検証窓を一つ処理すること。コードはプロンプト処理後、出力上限未満かつ EOS 終了でない場合にそのループへ入ります（`engine/sycl/src/program/generate.cpp:13712-13719,14033`）。通常の逐次デコードだけで終わる場合はこの箇所から出力されません。
- モデルや実行条件などが原因で `ver.run(...)` が失敗した場合は診断行より前にエラーを出して戻るため、この窓の診断行は出ません（`engine/sycl/src/program/generate.cpp:14114-14117`）。
- この参照は投機的デコードの `generate` 経路内です。候補名の完全一致検索では SYCL 以外の実装、SYCL server 経路、同梱 Python ツールに読み取り箇所はありません。

## 実行時の詳細

検証窓ごとに target の実行成功後、窓入力 `window` と target 出力 `outv` を比較して採用数 `a` を求め、その直後に環境変数を読みます。`window` と `outv` の各 `T` 個の整数 ID をそれぞれ `draftdbg: window ... | target ...` として stderr に出し、末尾に `accepted <a>` を付けます（`engine/sycl/src/program/generate.cpp:14114-14117,14160-14166`）。

読み取り結果を static 変数などに cache せず、窓のたびに `getenv` を呼びます。そのためコード上はプロセス実行中の環境変更も次の窓の判定対象です。値を未設定から設定済みに変えると以後の対象窓で出力され、設定済みから未設定に戻すと以後は出力されません。窓の選択、target の計算、draft の採用、commit や生成 token の決定にはこの分岐から書き込みを行いません（`engine/sycl/src/program/generate.cpp:14162-14166,14190-14207`）。

## ログと測定値

設定時の stderr 形式は `draftdbg: window` に続く窓入力 ID 群、` | target` に続く target ID 群、` | accepted <整数>` です。各 ID は十進整数で、行末に改行を出します。unset 時はこの行を出しません（`engine/sycl/src/program/generate.cpp:14162-14166`）。この環境変数に関する測定値はありません。

## 根拠

- `engine/sycl/src/program/generate.cpp:13712-13719` — 投機的デコード経路への条件。
- `engine/sycl/src/program/generate.cpp:14033-14060` — 窓ループと窓サイズ決定。
- `engine/sycl/src/program/generate.cpp:14114-14117,14160-14166` — target 実行、採用数算出、環境読み取りと stderr 出力。
- `engine/sycl/src/program/generate.cpp:14190-14207` — 診断後の commit と token 出力。
- `engine/CMakeLists.txt:23-32`; `engine/sycl/CMakeLists.txt:375-377` — SYCL backend の構成条件と実行ファイルへのソース組み込み。
