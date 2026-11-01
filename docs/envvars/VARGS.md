# `VARGS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更は表示されていません。

## 役割

`VARGS` は Strata 本体の共通設定ではなく、Qwen 3.6 の画像エンコーダー比較用補助スクリプト `tools/qwen35/q36_venc.py` が、起動する実行ファイルに追加コマンドライン引数を渡すために読む環境変数です。このスクリプトは `q36_vision_cmp.py` から既定の encoder helper として呼び出されます。`q36_venc.py` の引数仕様は `EXE MMPROJ MODEL IMG [IMG ...]` です（`tools/qwen35/q36_venc.py:1-5`, `tools/qwen35/q36_vision_cmp.py:70-92`）。

## 値と判定

| 状態 | スクリプトが使う値 |
|---|---|
| `STRATA_VARGS` が設定済み | `STRATA_VARGS` の値。空文字でも `VARGS` へはフォールバックしない |
| `STRATA_VARGS` が未設定で `VARGS` が設定済み | `VARGS` の値 |
| 両方とも未設定 | 空文字 |

選択した文字列に Python の `split()` を適用し、結果の各要素を追加 argv として渡します。したがって空文字や空白だけの値は追加引数なしになり、空白で区切られます。数値変換、許可値の検査、引用符を解釈するシェル形式の解析はこのコードにはありません。引用符も単なる文字として残ります（`tools/qwen35/q36_venc.py:4`）。

## 有効になる条件

- `q36_venc.py` が実行されたときに限り読み取られます。`q36_vision_cmp.py` は `--venc` の既定値をこのスクリプトにしていますが、別のスクリプトを `--venc` で指定できます（`tools/qwen35/q36_vision_cmp.py:70-92`）。
- `VARGS` 単独では `STRATA_VARGS` が設定済みの場合に使われません。
- この読み取り箇所には OS、GPU backend、build macro、モデル状態による条件分岐はありません。追加引数を解釈するのは起動対象の実行ファイルであり、ここではその個別オプションの効果を定めていません。
- 調査対象 commit 内で `VARGS` の完全一致参照はこの Python 行だけです。通常の `strata` / `strata-q36` の環境設定として読む箇所は確認できませんでした。

## 実行時の詳細

`q36_venc.py` の実行ごとに `os.environ.get("STRATA_VARGS", os.environ.get("VARGS", ""))` で値を選び、`split()` の結果を `[EXE, "--mmproj", MMPROJ, "--model", MODEL]` の後ろへ連結して `subprocess.Popen` に渡します。これはシェル文字列として再解釈されません。環境値の結果は Python 変数としてその起動で使われ、プロセス内キャッシュはありません（`tools/qwen35/q36_venc.py:3-5`）。

起動後、スクリプトは子プロセスの標準出力から最初の行を読み出して表示し、画像ごとに `ENC <画像> <画像>.sve` を標準入力へ送り、返答行を表示します。返答が `OK` で始まる場合は `.sve` を読み、ヘッダーと統計を表示します。最後に `QUIT` を送り `wait()` しますが、終了コードを検査する処理はありません。起動失敗やファイル読込・プロトコル処理時の例外を捕捉する処理もこのスクリプトにはありません（`tools/qwen35/q36_venc.py:5-18`）。`VARGS` 自体について専用の警告、終了コード、エラー処理はありません。

## 根拠

- 読み取り、`STRATA_VARGS` 優先、空文字既定、空白分割、argv 構築、子プロセス起動: `tools/qwen35/q36_venc.py:1-5`
- encoder helper の呼び出しと `--venc` 既定値: `tools/qwen35/q36_vision_cmp.py:70-92`
- 画像ごとのプロトコル処理、出力、終了待ち: `tools/qwen35/q36_venc.py:6-18`
- 候補名の由来: `docs/envvars/000_envvers.md:1695`（候補一覧への掲載だけでは利用者向け設定であることを示しません）。
