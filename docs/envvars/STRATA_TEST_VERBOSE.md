# `STRATA_TEST_VERBOSE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の WMMA GEMM parity テスト `hip_prefill_wmma_gemm_parity` が、各ケースの PASS / SKIP / FAIL と、カーネルが拒否する形状の詳細を標準出力に追加する診断用スイッチです。Strata 本体や通常の生成処理からは参照されず、このテスト実行ファイルだけで使われます。

## 値と判定

値の内容は parse せず、`std::getenv("STRATA_TEST_VERBOSE") != nullptr` で設定の有無だけを見ます。

| 環境変数の状態 | 詳細出力 |
|---|---|
| 未設定 | なし |
| 空文字を含む、何らかの値が設定済み | あり |

したがって `STRATA_TEST_VERBOSE=0`、`false`、空文字も有効です。大文字小文字や数値の妥当性は検査されません。値による fallback や範囲制限もありません。

## 有効になる条件

この変数を読むのは `tests/hip/prefill_wmma_gemm_parity.cpp` のテスト実行ファイルだけです。CMake では `STRATA_ENABLE_HIP` が有効な場合のテスト群に登録されます。WMMA parity テストは GPU のアーキテクチャが `gfx11` WMMA 対応でなければ環境変数に関係なくテスト全体を skip（終了コード 77）します。これは verbose 出力の有効・無効とは別の条件です。

## 実行時の詳細

`main()` のテストループ前に一度だけ設定有無を読み、`verbose` に保存します。プロセス実行中に環境変数を変更しても再評価されません。

有効なとき、各 GEMM ケースについて dtype、形状（`T`, `N`, `K`, `ldy`）、`beta`、最大絶対誤差と PASS を出力します。カーネルがケースを受理しない場合は SKIP、失敗時は FAIL を出力します。また、テストが拒否を期待する形状をカーネルが正しく拒否した場合も、その形状と理由を表示します。無効なときも dtype ごとの集計、失敗の stderr 報告、最終結果は通常どおり出力されます。この変数は検査内容、合否判定、終了コードを変えず、追加のケース別表示だけを制御します。

## 根拠

- `tests/hip/prefill_wmma_gemm_parity.cpp:266-278`: テストの `main()`、GPU アーキテクチャによる skip。
- `tests/hip/prefill_wmma_gemm_parity.cpp:331-343`: 環境変数を設定有無で読む箇所とテスト開始時の出力。
- `tests/hip/prefill_wmma_gemm_parity.cpp:361-414`: PASS / SKIP / FAIL と拒否形状の verbose 表示。
- `tests/hip/prefill_wmma_gemm_parity.cpp:420-448`: 通常の失敗報告、集計、終了コード。
- `CMakeLists.txt:727-729,790-796`: `STRATA_ENABLE_HIP` 配下でのテスト実行ファイルと CTest 登録。
