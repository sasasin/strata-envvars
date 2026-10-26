# `GR_PRELOAD`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`metal/tests/gr2_parity.cpp` の `gr2_parity` テストで、BF16 側の down kernel として通常版 `gr_down3_*` ではなく、重みを正規化計算より前にレジスタへ読み込む `gr_down3b_*` を選びます。候補一覧にはありますが、確認できた参照はこのテストだけであり、Strata の通常実行経路を制御する環境変数ではありません。

## 値と判定

値の内容は parse せず、`std::getenv("GR_PRELOAD")` が null かどうかだけを見ます。したがって未設定なら無効、設定されていれば有効です。`GR_PRELOAD=`, `0`, `false` も設定済みなので有効になります。大文字小文字、数値、文字列全体の比較はありません。

この判定に数値変換、fallback、clamp はありません。`gr2_parity` の実行中、BF16/Q8_0 を切り替えるループの各反復で参照されます。プロセス起動後の環境変更を反映するかどうかはコードから確認できません（テスト中に環境を書き換える処理はありません）。

## 有効になる条件

- `metal/tests/gr2_parity.cpp` からビルドされた `gr2_parity` を実行する場合に限ります。
- 変数が設定されていても、選択分岐は `q8 == 0`、すなわち BF16 側だけです。Q8_0 側では `gr_down3_8_*` が選ばれます。
- `--bench` の有無によらず同じカーネル選択分岐を通ります。
- Strata の Metal エンジン本体にこの名前の参照はなく、通常の生成・推論経路への効果は確認できません。

## 実行時の詳細

テストは `std::getenv("GR_PRELOAD")` の有無に応じて pipeline 名を組み立てます。未設定時または Q8_0 側では `gr_down3_{F}_{tt}_{rps}`、設定済みで BF16 側では `gr_down3b_{tt}_{rps}` を要求します。続けてその名前の pipeline を作成し、down projection 用 dispatch に使います（`metal/tests/gr2_parity.cpp:71-83`）。

`gr_down3b` は BF16 専用で、各 lane が担当する行の重みをレジスタにロードしてから正規化処理を行うカーネルです。カーネルは `metal/kernels/gr2.metal:207-235` で定義され、テストが要求する `gr_down3b_{TT}_{RPS}` 名の specialization は同ファイルの `:302-303` で登録されています。環境変数自体がログ出力、ファイル書き込み、プロセス起動を行う処理はありません。

## 根拠

- 全リポジトリでの名前参照は `metal/tests/gr2_parity.cpp:78-81` の2回のみ。いずれも `getenv` の null 判定です。
- `metal/tests/gr2_parity.cpp:30-35` は当該プログラムの `main` と Metal context / kernel library の初期化を示します。
- `metal/kernels/gr2.metal:207-235,302-303` は BF16 専用カーネルと登録名を示します。
- 検索範囲: 対象 commit の Strata リポジトリ全体（`.git` を除く）。外部依存や生成済みコードの動作は調査対象に含めていません。
