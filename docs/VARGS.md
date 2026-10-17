# `VARGS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`VARGS` は、同梱の Qwen3.5 vision encoder 用ラッパー `tools/qwen35/q36_venc.py` が `strata-vision` を起動するときに、標準の `--mmproj` / `--model` 引数の後ろへ追加する引数列を指定するための環境変数です。Strata エンジン本体が読む設定ではなく、この Python 診断・比較ツールの起動補助です。

## 値と判定

| 状態 | `q36_venc.py` が使う値 |
|---|---|
| `STRATA_VARGS` が未設定、`VARGS` も未設定 | 空文字（追加引数なし） |
| `STRATA_VARGS` が未設定、`VARGS` が設定済み | `VARGS` の値 |
| `STRATA_VARGS` が設定済み（空文字を含む） | `STRATA_VARGS` の値。`VARGS` にはフォールバックしない |

選ばれた文字列は Python の `str.split()` で空白区切りに分割され、得られた各要素をそのまま `subprocess.Popen` の argv リストに追加します。引用符やバックスラッシュを解釈するシェル処理はありません。したがって、空白を含む一つの引数を引用符で囲んでも、その引用符はシェル構文として除去されず、文字列は空白位置で分割されます。値の検証やエンジン引数としての妥当性確認もこのラッパーでは行いません。

## 有効になる条件

`VARGS` は `tools/qwen35/q36_venc.py` が実行される場合だけ参照されます。`tools/qwen35/q36_vision_cmp.py` は `--venc` の既定値を `q36_venc.py` にし、encoder 実行時には環境を複製して子プロセスへ渡すため、比較ツール経由でも環境変数は利用できます。別の `strata` / `strata-vision` 起動経路がこの変数を解釈する根拠は見つかりません。

## 実行時の詳細

ラッパーはまず `[exe, "--mmproj", mm, "--model", model]` を組み立て、その末尾に環境から選んだ追加引数を連結して `subprocess.Popen` で encoder を起動します。`Popen` に `env` を指定していないため、子プロセスは通常の Python subprocess の既定どおりラッパーの環境を継承します。追加引数は起動時に一度読み取られ、画像ごとではなく、起動した encoder プロセスに対する引数です。

追加引数が不正な場合のエラー文言や終了処理は `VARGS` 用には実装されていません。エンジン側が argv をどう扱うかは本変数の実装ではなく、ここでは追加引数を渡すところまでを確認しました。

## 根拠

- `tools/qwen35/q36_venc.py:1-5` — このラッパーの用途、`STRATA_VARGS` 優先の取得、`VARGS` へのフォールバック、空白分割、ベース argv への追加、子プロセス起動。
- `tools/qwen35/q36_vision_cmp.py:70-92` — `--venc` の既定値と、比較処理から encoder ラッパーを起動する箇所。
- `tools/qwen35/q36_vision_cmp.py:31-36` — 環境変数を複製して `subprocess.run` に渡す処理。
