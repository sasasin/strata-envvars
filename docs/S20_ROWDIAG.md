# `S20_ROWDIAG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

通常の Strata 実行ファイルの設定ではありません。名前の直接参照は `tests/cuda/prefill_fused_iq_test.cpp` の一箇所だけで、CUDA/HIP の fused IQ prefill テストが fused 出力と MMQ 出力の差が大きい pair を表示するための診断フックです。`STRATA_PF_FUSED` などの実行時カーネル設定とは別で、製品実行の計算や出力を制御しません。

## 値と判定

| 状態 | 診断出力 |
|---|---|
| 未設定 | なし |
| 設定あり（空文字を含む） | あり |

判定は `std::getenv("S20_ROWDIAG")` の null 判定だけです。値の内容は parse しないため、`0`、`false`、空文字を含む任意の設定値で有効になります。数値範囲や無効値時の fallback はありません。

## 有効になる条件

`prefill_fused_iq_test` の timing part が実行され、このコードに到達することが条件です。`--no-timing` では実行されません。CMake では CUDA の `STRATA_BUILD_TESTS` が有効な場合に `prefill_fused_iq_test` を登録し、HIP ビルドでは `hip_prefill_fused_iq` として同じテストソースを使います。テストは利用可能な GPU/kernel 条件を満たさない場合に終了コード 77 で skip する経路があります。

この環境変数を通常の Strata サーバーや CLI に渡しても、この参照箇所は実行されません。リポジトリ内の通常実行ソース、セットアップ、サーバーに同名の読み取りはありません。

## 実行時の詳細

テストが fused と MMQ の出力を取得した後、各 routing pair について、fused 行と対応する MMQ 行の最大絶対差を計算します。MMQ 行の最大絶対値が 0 より大きい場合はそれで割り、そうでなければ最大絶対差をそのまま指標にします。指標の大きい順に並べて先頭12件を stdout に表示します。各行には pair、token、expert とその row 数、fused row の位置、expert 内の相対位置、指標が含まれます。これは診断表示だけで、比較結果の合否判定、計算の選択、出力値の変更は行いません。

MMQ 非対応の形式ではテストが MMQ 出力をゼロ配列として用意するため、この診断値は fused とゼロ配列との比較になります。その場合、MMQ との誤差として解釈できません。テストソースのコメントにも HIP では一部形式が reference のみとあります。

判定は timing part 内の通常の分岐で pair と chunk ごとに毎回行われ、static cache されません。プロセス起動後に環境変数を変える挙動はコードでは扱っていません。

## 根拠

- `tests/cuda/prefill_fused_iq_test.cpp:1-16` — 対象を CUDA/HIP fused IQ テストとし、デバイス条件を記載しています。
- `tests/cuda/prefill_fused_iq_test.cpp:450-505,577-598,704-710` — timing part の入力準備・診断・呼び出しです。
- `CMakeLists.txt:1695-1705,1783-1794` — テストターゲットと CTest 登録です。
- Strata の実行コード、セットアップ、サーバーにおける同名参照は HEAD 全体の検索で見つかりませんでした。`docs/DETAILS.md` にこの変数の説明や測定値はありません。
