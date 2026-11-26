# `STRATA_PENALTY_PROMPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

repeat / frequency / presence penalty が参照する token 履歴の開始位置を選びます。既定では現在の応答の履歴だけを対象にし、環境変数の値が有効なら prompt の履歴も含む従来の窓に戻します。prompt が含まれる場合も、実際に penalty が参照する長さは要求の `penalty_last_n` などの設定で決まります。通常の `strata` 生成経路、SYCL 生成経路、Qwen3.6 系 engine に読み取りがあります（`engine/include/strata/kernels/sampler.hpp:94-103`、`engine/src/program/generate.cpp:21448-21457,21768-21772`、`engine/sycl/src/program/generate.cpp:11585-11592,11725-11731`、`engine/src/qwen35/q36_engine.cu:5170-5174`）。

## 値と判定

各読み取り箇所は `std::getenv` の結果を `penalty_counts_prompt` に渡します。helper は環境変数が設定されており、値の先頭 byte が文字 `'1'` の場合だけ `true` を返します。文字列全体の parse や数値変換はしません（`engine/include/strata/kernels/sampler.hpp:99`、SYCL 側の同じ helper は `engine/sycl/include/strata/kernels/sampler.hpp:74`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 通常・SYCL・Qwen3.6 系の読み取り | `false`（prompt を窓に含めない） | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1`, `anything` |

空文字は設定済みでも先頭 byte が `'1'` ではないため無効です。大文字小文字や後続文字の検証はありません。CLI / request の sampling 値でこの判定が上書きされる分岐はありません。request の `penalty_last_n`、`penalty_repeat`、`penalty_freq`、`penalty_present` は penalty 自体の使用と長さを決め、環境変数は履歴に prompt を含めるかだけを決めます（`engine/src/program/generate.cpp:18824-18832,18917-18920,18951-18965`、Qwen3.6 系の protocol parse は `engine/src/qwen35/q36_engine.cu:5025-5044`）。

## 有効になる条件

- 対応する Strata engine の生成経路が使われる必要があります。通常 engine は `engine/src/program/generate.cpp`、SYCL engine は別実装の `engine/sycl/src/program/generate.cpp` を使います。読み取り箇所には OS 固有の分岐はありません。Qwen3.6 系では `strata` に組み込まれた Qwen35 engine、または `strata-q36` が対象です。Qwen35 の組み込みは `STRATA_HAVE_QWEN35` の compile definition がある build に限られます（`engine/cmake/strata_gpu_engine.cmake:548-551,565-583`）。
- sampling request で penalty 履歴が使われる必要があります。通常経路では `penalty_last_n` を 0 以上にし、repeat 値が 1 以外、または frequency / presence 値が 0 以外の場合に batch slot の penalty 状態を作ります（`engine/src/program/generate.cpp:18951-18965,19459-19464`）。Qwen3.6 系も `last_n != 0` かつ少なくとも一つの penalty 値が既定値と異なる場合だけ penalty を適用します（`engine/include/strata/qwen35/sampling.hpp:24-35`）。
- 通常・SYCL 経路では `penalty_last_n` が正数なら履歴長は `kPenaltyWindowCap` までに制限されます。Qwen3.6 系の `last_n < 0` は履歴全体を使い、正数は末尾から指定数を使います（`engine/src/program/generate.cpp:21448,18961`、`engine/sycl/src/program/generate.cpp:11585`、`engine/include/strata/qwen35/sampling.hpp:24-28`）。
- penalty が未指定・無効で有効な penalty 値もない場合、この変数が有効値でも token 選択に作用する penalty はありません。CLI / request 設定は penalty の有無・長さを制御しますが、prompt を含めるかどうかの環境変数判定は別です。

## 実行時の詳細

通常経路と SYCL 経路では、prompt の末尾 token を最初の decode step が取り込むため、既定の窓はその token から始まり、その後の応答 token を含みます。環境変数が有効なら窓の起点を token 0 にし、prompt と応答を合わせた履歴を penalty の候補にします。通常経路では `penalty_window_from` が起点を選び、その範囲から各 decode window 用の履歴行を組み立てます（`engine/include/strata/kernels/sampler.hpp:100-104`、`engine/src/program/generate.cpp:21768-21772,22964-22973`）。SYCL も同じ helper を使い、各行の履歴を構築します（`engine/sycl/include/strata/kernels/sampler.hpp:75-79`、`engine/sycl/src/program/generate.cpp:11725-11731,12748-12759`）。

Qwen3.6 系は既定で prompt の末尾 token だけから履歴を開始し、有効値なら prompt 全体を初期履歴として保持します。その後の penalty 適用は `penalty_last_n` と penalty 値に従います（`engine/include/strata/qwen35/sampling.hpp:20-35,38-45`、`engine/src/qwen35/q36_engine.cu:5170-5174,4571-4576`）。

読み取り結果は各読み取り箇所の関数ローカル `static const bool` に保存されます。通常経路では solo decode と batch slot admission に別々の static があり、SYCL も通常 decode 用の static です。Qwen3.6 系にも別の static があります。各値はその箇所が最初に実行された時に確定し、同じプロセス内で環境を後から変更してもその箇所の判定は更新されません（`engine/src/program/generate.cpp:19459-19464,21448-21457`、`engine/sycl/src/program/generate.cpp:11585-11592`、`engine/src/qwen35/q36_engine.cu:5172-5174`）。

## ログと測定値

この変数の値や判定を出力するログ、専用の警告・エラー・終了経路はありません。これは履歴範囲を切り替える処理であり、コードから生成 token の同一性は保証されません。

## 根拠

- `engine/include/strata/kernels/sampler.hpp:94-104` — 通常 engine の helper と履歴窓起点。
- `engine/sycl/include/strata/kernels/sampler.hpp:69-79` — SYCL engine の同じ判定。
- `engine/src/program/generate.cpp:19459-19464,21448-21457,21768-21772,22964-22973` — batch admission、sampling request、通常 decode の窓と履歴行。
- `engine/sycl/src/program/generate.cpp:11585-11592,11725-11731,12748-12759` — SYCL 側の読み取りと履歴行。
- `engine/include/strata/qwen35/sampling.hpp:20-45`、`engine/src/qwen35/q36_engine.cu:4571-4576,5170-5174` — Qwen3.6 系の penalty と初期履歴。
- `engine/cmake/strata_gpu_engine.cmake:548-551,565-583` — engine 実行ファイルと Qwen35 engine の組み込み条件。
