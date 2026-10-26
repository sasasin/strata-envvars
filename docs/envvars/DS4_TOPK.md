# `DS4_TOPK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 エンジンが通常層で使う「1 token あたりに選ぶ routed expert 数」を、モデル既定値や `--experts` の値より優先して指定するテスト用フックです。ソースは「test, not for users」と明記しています。候補値は `experts_test_override()` が受け取り、有効値なら選択数を返します。通常利用者向けの Faster / Full quality 設定は `--experts` であり、本変数はその設定を上書きします。

## 値と判定

`std::getenv("DS4_TOPK")` で設定有無を確認し、設定されていれば `std::atoi()` の戻り値を検査します。文字列全体の厳密な数値 parse ではありません。

| 状態・値 | 結果 |
|---|---|
| 未設定 | 既に決まっている値（`--experts` または自動ルール）を使う |
| 空文字 | `atoi("")` は `0` となり、既決定値を使う |
| `1` 以上 `model_k` 以下に変換される整数 | その整数に上書き |
| `0`、負数、`model_k` より大きい値 | 既決定値を使う |
| 数字の前に空白や符号がある値 | `atoi` の変換結果が範囲内なら有効 |
| 数字の後ろに文字が続く値 | 数字の先頭部分が変換され、その結果が範囲内なら有効（例: `4abc` は `4`） |
| 数字として変換できない値 | `atoi` の結果 `0` となり、既決定値を使う |

`model_k` は対象モデルの本来の expert 選択数です。たとえば `model_k` が 6 なら `1`〜`6` が有効です。`atoi` の整数範囲を超える入力の結果には依存せず、ここでは有効値として扱いません。

## 有効になる条件

- DeepSeek V4.1 の CUDA エンジンのモデル読み込み経路で参照されます。
- 通常層 (`!l.mtp`) のうち `il == 0` の初期化時に一度だけ呼び出され、その結果が `experts_used` に保存されます。後続の通常層には同じ数が適用されます。
- MTP 層は別の `l.k_exp = g.d_k` を使い、この上書きの対象ではありません。
- 参照箇所は `ds4_experts_rule.hpp` の helper と `ds4_model.cu` の呼び出しに限られます。テストはこの helper の上書きと範囲外での fallback を確認します。空文字そのものの parse はテストしていません。

## 実行時の詳細

モデル読み込み時、まず `experts_per_word(o.experts, vram_all, l.k_exp, integrated)` が `--experts` または GPU メモリ量・統合 GPU の自動ルールから選択数を決めます。その結果を `experts_test_override(..., l.k_exp)` に渡し、`DS4_TOPK` が有効なら置き換えます。通常層ではこの値を `experts_used` に保持し、各層の `l.k_exp` を `min(元の層の値, experts_used)` にします。

`l.k_exp` はルーターの `route()` に渡され、ルーターはその数だけ expert を選択します。各選択 expert の重みは選んだ expert のスコア合計で正規化した後に `route_scale` を掛けます。そのため `DS4_TOPK` はログ表示だけの診断値ではなく、通常層の MoE 計算に使う expert 数と routing weights を変えます。

読み取り結果を static cache する実装ではありませんが、呼び出し位置はモデル読み込み時の最初の通常層だけです。実行中に環境を変更しても、既に読み込まれたモデルの値は更新されません。別のモデルを読み込む場合は、その読み込み時点の環境値が再び参照されます。

選択数がモデル本来の数より少ない場合、stderr に `ds4: experts per word: N (...)` が出ます。括弧内の表示 (`as asked` / `faster mode`) は `DS4_TOPK` の有無ではなく、`o.experts >= 1` かどうかで選ばれます。したがって環境変数で上書きした場合、文言は実際の指定元を表さないことがあります。`DS4_TOPK` 専用の警告や無効値ログはありません。

## 文書との照合

`docs/DEEPSEEK41.md` は利用者向けに `--experts 5`（Faster）と `--experts 6`（Full quality）、および自動選択を説明していますが、`DS4_TOPK` は記載していません。ソース上もテスト用と明記されているため、この環境変数を通常の Faster / Full quality 設定として扱うべきではありません。

## 根拠

- `src/dsv41/ds4_experts_rule.hpp:62-69` — `getenv`、`atoi`、許容範囲、既決定値への fallback。
- `src/dsv41/ds4_model.cu:2038-2064` — モデル読み込み時の呼び出し、通常層への適用、stderr ログ。
- `src/dsv41/ds4_model.hpp:45-47` — `--experts` と expert 数の説明。
- `src/dsv41/ds4_model.cu:7273-7284,9151-9156` — `l.k_exp` を使った routing 経路。
- `src/dsv41/ds4_kernels.cu:501-549` — `k` 個の選択と選択 expert 間での routing weight 正規化。
- `tests/dsv41/experts_rule_test.cpp:53-72` — helper の上書きと範囲外での fallback のテスト。
- `docs/DEEPSEEK41.md:91-95` — 利用者向け `--experts` の説明。
