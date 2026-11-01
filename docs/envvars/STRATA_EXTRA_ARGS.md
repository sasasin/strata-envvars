# `STRATA_EXTRA_ARGS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありません。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_EXTRA_ARGS` は Strata エンジン自身の設定環境変数ではなく、同梱の4つの診断・回帰試験スクリプトがエンジンの CLI 引数列へ追加するための値です。対象スクリプトは `tools/batch_groups_cache_test.py`、`tools/session_pressure_test.py`、`tools/cancel_park_test.py`、`metal/tests/serve_probe.py` です。候補名の全参照を検索した範囲で、これら以外に Strata ソースが値を読む箇所はありません。

これらのスクリプトを実行しない通常の Strata 起動経路では、この名前を Strata が読む実装は確認できません。スクリプトに渡した引数がエンジンの動作へどう作用するかは、追加された個々の CLI オプションによります。

## 値と判定

すべての読み取り箇所が `os.environ.get("STRATA_EXTRA_ARGS", "").split()` を使います。値の真偽値判定やオプションの検査はなく、分割結果をそのまま引数配列に追加します。

| 環境変数の状態 | スクリプトでの扱い |
|---|---|
| 未設定 | 既定値 `""` を空白分割し、追加引数は空配列 |
| 空文字 | 空文字を空白分割し、追加引数は空配列 |
| 空白だけ | 空白分割の結果は空配列 |
| 空白区切りの文字列 | 各空白区切りの部分文字列を1個ずつ追加引数にする |

分割は `str.split()` によるため、引用符をシェルのように解釈したり、引用符内の空白を一つの引数にまとめたりしません。たとえば `--label "two words"` は概ね `--label`, `"two`, `words"` の3要素になります。シェルはこの値を再解釈せず、スクリプトが作った argv の要素が `serve/server.py` の `subprocess.Popen` に渡されます。数値変換、許容値検証、範囲制限、無効値時の fallback はスクリプト側にはありません。

## 有効になる条件

- 対象の Python スクリプトが起動され、`STRATA_EXTRA_ARGS` の読み取り行まで実行されること。
- 引数は `StrataEngine` の起動引数へ追加されます。`tools/batch_groups_cache_test.py` では `engine_args(cfg)` の結果の後ろに追加されます。他の3件では設定 JSON の `args`（Metal probe は `list(cfg["args"])`）の後ろに追加されます。
- スクリプトが `StrataEngine` を生成してエンジンを起動すること。Python の実行環境や backend に応じた `STRATA_EXTRA_ARGS` 自体の分岐はありません。

したがって、これらのスクリプトで設定 JSON にある引数と同じ CLI オプションを重ねた場合、追加分が argv 上で後ろに並ぶことまでは確認できます。重複オプションのどちらをエンジンが採用するかはオプションごとの CLI 実装に依存し、この環境変数の読み取りコードだけから一律には決められません。

## 実行時の詳細

各スクリプトはトップレベルの初期化時に環境値を一度読み、追加引数を作ります。スクリプト実行中に親プロセスの環境を変更して再評価する処理や、値をキャッシュする共通 env helper はありません。追加した引数は `StrataEngine` が `[exe, "--serve", *args]` の形で起動する子プロセスに渡されます。`child_env(cfg)` は親の `os.environ` をコピーしてエンジン用環境を作りますが、`STRATA_EXTRA_ARGS` を特別に解釈・設定しません。値そのものが環境変数として Strata エンジンへ転送されるのではなく、分割済みの引数として渡ります。

エンジン起動時には、ログファイルがある場合、Strata server が `engine started: ... --serve` と引数列を記録します（`serve/server.py:1057-1062`）。起動失敗時の処理は通常の `StrataEngine` 起動経路に従い、`Popen` の `OSError` は再送出されます（`serve/server.py:1074-1084`）。追加引数に対する専用の警告、検証ログ、終了コード処理は各スクリプトにありません。後続のエンジン起動結果は、渡された CLI オプションの処理によります。

## 根拠

- 候補名の全参照: `tools/batch_groups_cache_test.py:31`、`tools/session_pressure_test.py:28`、`tools/cancel_park_test.py:29`、`metal/tests/serve_probe.py:48`。各箇所で未設定既定値・空白分割・引数配列への追加を確認。
- 追加引数より前に設定済み引数を作る処理: `serve/server.py:3245-3260`（`engine_args`）、および上記各スクリプトの該当行。
- 引数列を保存し、起動ログに記録し、`--serve` とともに子エンジンへ渡す処理: `serve/server.py:1017-1022,1057-1062,1074-1084,1077-1079`。
- 子プロセス環境は親環境のコピーから作られ、設定値や backend に応じて環境を調整する処理: `serve/server.py:3747-3790`。この関数に `STRATA_EXTRA_ARGS` 固有の扱いはありません。
