# `TAB_TEST_DEBUG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数は通常の Strata 実行ファイルの設定ではなく、CUDA の `prefill_mmq_tab_test` が比較失敗時に追加の差分情報を表示するための診断フックです。通常の推論経路やプロンプト処理を制御する用途は、対象 commit の Strata 所有ソースから確認できませんでした。

## 値と判定

テスト内の `same_bits()` は `std::getenv("TAB_TEST_DEBUG")` の null 判定だけを行います。値の文字列や数値は parse しません。

| 状態 | 失敗比較時の追加表示 |
|---|---|
| 未設定 | なし |
| 設定あり（空文字を含む） | あり |

追加表示では、比較対象の `float` を先頭から走査し、異なる要素を最大6件まで index と両値（`%.9g`）で出し、続けて異なる float の総数を出します。環境変数の値はこの診断の有効・無効以外には使いません。

## 有効になる条件

`TAB_TEST_DEBUG` は `tests/cuda/prefill_mmq_tab_test.cu` 内でのみ参照されています。CMake では `prefill_mmq_tab_test` ターゲットは `STRATA_BUILD_TESTS` と `_strata_mmq_tab_on` の両方が真の場合だけ追加され、CTest に登録されます。したがって、この変数の効果はそのテスト実行時に限られます。テストが比較成功した場合は `same_bits()` が早期 return するため、変数を設定していても差分詳細は出ません。

## 実行時の詳細

バイト列比較で不一致があると、まず常に `FAIL <what>: first differing byte <i> of <n>` を標準出力に表示します。続いて `TAB_TEST_DEBUG` が設定されていれば、float として解釈した比較バッファについて差分を表示します。失敗数を加算してテストを継続し、最終的な比較結果に応じてプロセスは 0（失敗なし）または1（失敗あり）で終了します。この変数は `same_bits()` の不一致経路で都度読み取られ、static cache されません。

## 根拠

- `tests/cuda/prefill_mmq_tab_test.cu:135-156` — byte 比較、常時の失敗表示、環境変数判定、最大6件の float 差分と差分総数、失敗カウント。
- `tests/cuda/prefill_mmq_tab_test.cu:515-525,619-620` — CUDA device / pointer-table build の確認と skip、最終終了コード。
- `CMakeLists.txt:1713-1718` — `STRATA_BUILD_TESTS AND _strata_mmq_tab_on` の条件付きでテスト executable と CTest を登録。
- `docs/DETAILS.md:1925-1940` — pointer-table MMQ の説明と同テストの役割。`TAB_TEST_DEBUG` 自体の説明はありません。
- `docs/000_envvers.md:725` — 調査候補一覧での名前。
