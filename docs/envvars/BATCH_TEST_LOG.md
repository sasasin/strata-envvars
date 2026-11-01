# `BATCH_TEST_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、`git status --short --branch` に変更ファイルの表示はありませんでした。

## 役割

`BATCH_TEST_LOG` は Strata engine の設定ではなく、同梱ツール `tools/batch_test.py` が engine プロセスの stderr を保存するファイルを選ぶための環境変数です。Strata 本体のソースにはこの名前の読み取り箇所はなく、`tools/batch_test.py` が親プロセス側で読み取ります。ツールは engine を `--serve` 付きで起動し、その stderr を選んだファイルへリダイレクトします（`tools/batch_test.py:47-66`）。

## 値と判定

| 親プロセスの値 | ツールの選択 |
|---|---|
| 未設定 | `tempfile.gettempdir()` の `batch_test_engine.log` |
| 空文字 | 未設定と同じ既定パス |
| 非空の文字列 | その文字列をログパスとして使用 |

判定は `os.environ.get("BATCH_TEST_LOG") or ...` です。文字列を parse、trim、正規化せず、空文字だけが偽として既定値に置き換わります。したがって `0`、`false`、空白のみの値も非空ならパスとして使われます。選択したパスは `open(path, "w")` で開くため、同名ファイルがあれば切り詰められ、なければ作成されます。ディレクトリが存在しない、または書き込みできないなど `open` が失敗する場合、例外を処理するコードはこの箇所にありません（`tools/batch_test.py:59-60`）。

相対パスは `batch_test.py` を実行している親プロセスの作業ディレクトリ基準です。engine の `cwd=cfg.get("cwd")` は `Popen` に指定されますが、ログファイルはそれより前に親プロセス側で開かれます（`tools/batch_test.py:59-62`）。

## 有効になる条件

この変数は `tools/batch_test.py` の `Engine` 初期化時にのみ参照されます。通常の Strata engine 実行や Strata サーバー起動だけでは、この Python ツールのログパス選択は起きません。ツールを起動する `tools/par/co_bt.sh` と `tools/par/host_seq.sh` は各 arm ごとのログファイル名を指定しています（`tools/par/co_bt.sh:7-11`, `tools/par/host_seq.sh:8-11`）。

## 実行時の詳細

`Engine.__init__` は `BATCH_TEST_LOG` を親の `os.environ` から読み、選んだファイルを `w` モードで開きます。そのファイルオブジェクトを `subprocess.Popen` の `stderr` に渡し、engine の stdout は別の pipe から読みます。engine が `READY` 行を返す前に stdout が終了した場合、ツールは終了コード相当の `SystemExit` で `the engine ended before READY - see <path>` を表示します。engine の stderr 内容は指定ログファイル側で確認できます（`tools/batch_test.py:59-66`）。

`Popen` の子環境は親の `os.environ` をコピーし、`extra_env` を加えて作られます（`tools/batch_test.py:55-58`）。このため親に設定された `BATCH_TEST_LOG` は子にも継承されますが、調査対象 commit の Strata ソース内に同名の読み取りはありません。Strata がこの変数を解釈してログ先を決めるとは確認できず、確認できる効果は Python ツールによる stderr の転送です。

## 根拠

- `tools/batch_test.py:47-66` — `Engine` の初期化、環境変数の読み取り、fallback、ファイル open、engine 起動、stderr 転送と `READY` 前終了時の通知。
- `tools/par/co_bt.sh:7-11` — arm ごとに `BATCH_TEST_LOG` を設定して `batch_test.py` を起動。
- `tools/par/host_seq.sh:8-11` — arm ごとに `BATCH_TEST_LOG` を設定して `batch_test.py` を起動。
- 調査対象 Strata リポジトリで `rg -n --hidden --glob '!**/.git/**' 'BATCH_TEST_LOG'` を実施。実行コードでの読み取りは `tools/batch_test.py:59` のみでした。ほかの一致は上記シェルスクリプトによる設定と、ベンチマーク記録・説明でした。
