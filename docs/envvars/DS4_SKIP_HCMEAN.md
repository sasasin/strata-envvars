# `DS4_SKIP_HCMEAN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されませんでした。

## 役割

DeepSeek V4.1（DS4）エンジンで、drafter 用 tap を作る `hc_mean` 計算をスキップする診断用フックです。実装上は計算結果を代替生成せず、`hc_mean` の出力バッファを書き込まないまま戻ります。これは Metal ビルドでのみ環境変数として評価されます。

## 値と判定

| 状態 | Metal ビルドでの判定 |
|---|---|
| 未設定 | 無効。通常の `hc_mean` 実装へ進む |
| 空文字を含む任意の設定値 | 有効。文字列の内容を調べず、設定有無だけで判定する |

数値変換、文字列比較、範囲制限、無効値時の fallback はありません。CLI 引数や別の環境変数との優先順位も実装されていません。Metal 以外では `ds4_dbg` が常に `false` を返すため、この変数は読み取られず、設定しても分岐に影響しません。

## 有効になる条件

- `STRATA_METAL` が定義された Metal ビルドであること。
- DS4 の drafter が有効（`g.n_mtp > 0`）で、処理対象 layer が `g.d_targets` に含まれ、対応する `hc_mean` 呼び出しに到達すること。
- 値の条件は「環境変数が設定されていること」のみ。`=1` は必要ありません。

DS4 の対象 tap 呼び出しは chunk 処理中、layer 分割処理中、または `tap()` から行われます。通常の CUDA/HIP ビルドでは、これらの呼び出しがあっても `ds4_dbg` の Metal 専用判定は無効です（`src/dsv41/ds4_model.cu:8642-8650,8841-8849,9680-9689`）。

## 実行時の詳細

`hc_mean()` は Metal ビルドで `ds4_dbg("DS4_SKIP_HCMEAN")` を確認し、真なら直ちに return します。値は毎回 `std::getenv` で確認されるため、この箇所に static cache はありません。プロセス起動後に環境を変更できる実行環境であれば、後続呼び出しは変更後の設定を読みます。

この return は `out`（呼び出し側では `d.tap`）を更新しません。しかし呼び出し側はその後も `d.tap` から pinned host buffer `h_taps` へコピーをキューします。`h_taps` は次の drafter window の入力として使われるため、変数を有効にした場合、tap の正常な算出結果は渡らず、その後の drafter 入力に影響し得ます。コードにはこのスキップを通知する専用ログ、警告、エラー、終了経路はありません。環境変数が設定されていること自体で失敗を返す処理もありません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — `ds4_dbg` は Metal でのみ環境を参照し、その他のビルドでは常に false。
- `src/dsv41/ds4_kernels.cu:2541-2549` — `DS4_SKIP_HCMEAN` が設定されていると `hc_mean` が return し、通常の Metal host 処理および kernel fallback を実行しない。
- `src/dsv41/ds4_model.cu:8642-8650,8841-8849,9680-9689` — drafter 対象 tap の生成後も `d.tap` を `h_taps` へコピーする呼び出し側。
- `src/dsv41/ds4_model.cu:1038-1039,2739-2743,7702-7708` — `h_taps` の用途と確保、次の drafter projection への読み込み。
