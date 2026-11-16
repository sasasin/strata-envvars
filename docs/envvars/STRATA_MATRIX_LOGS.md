# `STRATA_MATRIX_LOGS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は Strata 本体やサーバーの設定ではなく、同梱の端末ライフサイクル試験 `tests/terminal/lifecycle_matrix.py` が、終了処理後のログを証拠として別ディレクトリに保存するためのテスト用フックです。通常の実行経路である Strata の CLI・サーバー・エンジンからこの名前を読む箇所は見つかりませんでした。試験スクリプトは `serve_case()` の `finally` で環境から値を読みます（`tests/terminal/lifecycle_matrix.py:349-353,371-390`）。

## 値と判定

Python の `os.environ.get()` で文字列を取得し、その文字列を `if keep:` で真偽判定します。文字列の内容は parse せず、空でない値はすべて出力ディレクトリのパスとして使われます。未設定は `None`、明示的な空文字は `""` となり、どちらも保存処理を行いません。`"0"`、`"false"`、空白だけの値も空文字ではないため有効で、パスとして扱われます。相対パスは試験プロセスの現在ディレクトリ基準です（`tests/terminal/lifecycle_matrix.py:384-389`）。

| 条件 | unset | 有効になる値（例） | 保存処理をしない値（例） |
|---|---|---|---|
| `serve_case()` の終了処理 | `None`。保存しない | `"/tmp/matrix-logs"`、`"0"`、`"false"`、`" "`。非空文字列をパスにする | `""`。空文字列は偽として扱われる |

文字列の形式・大文字小文字・数値範囲の検証や正規化はありません。ディレクトリ作成やファイル書き込みに失敗した場合を捕捉する処理もありません（同 `:384-390`）。

## 有効になる条件

- `tests/terminal/lifecycle_matrix.py` の `serve_case()` が実行され、その `finally` に到達すること。pytest wrapper はこの行列を fake engine で実行し、該当ケースは Windows 以外では通常実行、Windows ではコンソール依存ケースを除いて実行します（`tests/terminal/test_lifecycle_matrix.py:1-6,16-32`）。スクリプトは直接実行もできます（`tests/terminal/lifecycle_matrix.py:1-12,790-807`）。
- `STRATA_MATRIX_LOGS` が未設定または空文字列ならログ保存は行われません。非空ならその値のディレクトリを作成します（`tests/terminal/lifecycle_matrix.py:384-389`）。
- この名前を読む本番 Strata コード、CLI 引数との優先順位、backend・GPU・モデル状態による条件は確認できません。索引候補の根拠はテスト専用コードだけです。

## 実行時の詳細

値は `serve_case()` ごとの終了処理時に読み直され、関数内の cache はありません。その時点で値が非空なら `Path(keep).mkdir(parents=True, exist_ok=True)` を行い、試験用 root に存在する `serve.log` と `engine.log` をそれぞれ `{name}.serve.log`、`{name}.engine.log` として出力先へバイト列でコピーします。対象ログが存在しない場合、そのファイルは作りません。同名ファイルが既にあれば `write_bytes()` により置き換えます。その後 `serve.log` は常に空バイト列にされますが、コピーした `engine.log` はこの箇所では消去されません（`tests/terminal/lifecycle_matrix.py:371-390`）。

この変数の値を子プロセスへ渡す処理はありません。サーバー・エンジンのログの内容や終了判定自体を変えるものではなく、終了後の試験証拠を保存するだけです（同 `:349-390`）。

## ログと測定値

この変数が出力するログメッセージはありません。非空の出力先に、存在する試験ログファイルのコピーを作成します。コピーやディレクトリ作成に失敗すればその例外はこの箇所で処理されず、試験実行を失敗させ得ます（`tests/terminal/lifecycle_matrix.py:384-390`）。性能・測定値を変える機能ではありません。

## 根拠

- `tests/terminal/lifecycle_matrix.py:1-12` — ライフサイクル試験スクリプトの説明と起動例。
- `tests/terminal/lifecycle_matrix.py:349-390` — サーバー試験後の cleanup、環境値の読み取り、ログ保存。
- `tests/terminal/test_lifecycle_matrix.py:1-6,16-32` — pytest wrapper が fake engine の試験を登録する箇所。
