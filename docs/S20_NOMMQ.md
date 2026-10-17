# `S20_NOMMQ`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数は通常の Strata 実行ファイルの設定ではなく、CUDA/HIP の `prefill_fused_iq` テストにあるタイミング計測用フックです。テストの `timing_part()` で設定されていると、fused 経路だけを計測するための分岐を選びます。テストの他の段階や Strata アプリ本体の MMQ 選択を無効化するものではありません。

## 値と判定

値の内容は parse されず、`std::getenv("S20_NOMMQ") != nullptr` という設定有無だけで判定します。

| 状態 | `no_mmq` 判定 |
|---|---|
| 未設定 | `mq` が利用可能なら false。`mq` が利用不可なら true |
| 空文字を含む何らかの値を設定 | true |

`1` である必要はありません。`0`、任意の文字列、空文字も設定されていれば同じ扱いです。`mq` は `mmq_ok(p)` の結果で、この環境変数自体はその可否を変えません。

## 有効になる条件

この判定が使われるのは `timing_part()` 内だけです。テストの CMake ターゲットは CUDA ビルドの `prefill_fused_iq_test` と HIP ビルドの `hip_prefill_fused_iq` で、いずれも `STRATA_BUILD_TESTS` のテスト登録に属します。Strata の通常実行ファイルからこの名前を読む箇所は、対象 HEAD 内で見つかりませんでした。

テストは `--no-timing` を指定すると `timing_part()` 自体を呼ばず、`S20_NOMMQ` は参照されません。一方、タイミング部分より前に実行される `reference_part()` は既定で有効で、そこでの MMQ 実行はこの変数では止まりません（`--no-ref` で参照部分を省略できます）。また `S20_IDSDIAG` も同時に設定すると、タイミング関数内の診断分岐が `mmq_run()` を明示的に呼ぶため、この変数だけではその診断実行を抑止しません。

## 実行時の詳細

`timing_part()` に入るたびに変数を読み、結果をローカルの `no_mmq` に置きます。static cache はありません。設定されている場合、約1秒のウォームアップループから MMQ の計測時間を除き、8回の交互計測でも MMQ 呼び出しを行わず、直接 MMQ 計測も追加しません。fused 計測は引き続き実行します。MMQ の時間配列には計測値の代わりに `1.0f` が追加され、末尾の集計表示で `MMQ path` として出力される値は実測値ではありません。

このモードでも MMQ 利用可能時には MMQ のバッファを確保し、MMQ を計測ループで実行しない場合もそのバッファをダウンロードして比較・表示するコードが残ります。そのため、MMQ の実行結果に依存する比較値はこのモードでは有効な MMQ 測定値として解釈できません。`mq && !no_mmq` の条件で行う実形状での MMQ/fused 経路一致チェックだけは省略されます。したがって、この変数は出力比較やテスト全体を「fused のみ」にするスイッチではありません。

## 根拠

- `tests/cuda/prefill_fused_iq_test.cpp:428-430,456-460,475-480,502-510` — `timing_part()` 内の読み取り、MMQ バッファ、計測ループと sentinel 値。
- `tests/cuda/prefill_fused_iq_test.cpp:481-500` — `S20_IDSDIAG` 分岐は `no_mmq` 判定より前で MMQ を直接呼ぶ。
- `tests/cuda/prefill_fused_iq_test.cpp:524-537,628-640` — バッファのダウンロード、比較、時間表示、および一部比較チェックの条件。
- `tests/cuda/prefill_fused_iq_test.cpp:644-710` — 通常の参照部分とタイミング部分の呼び分け、`--no-ref` / `--no-timing`。
- `CMakeLists.txt:1695-1705,1790-1798` — CUDA/HIP のテスト実行ファイルと CTest 登録。
- `docs/DETAILS.md` — `S20_NOMMQ` の記載は見つかりませんでした。
