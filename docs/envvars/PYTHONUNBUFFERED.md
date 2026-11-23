# `PYTHONUNBUFFERED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この checkout では、Strata 自身がプロセス環境から `PYTHONUNBUFFERED` を読み取って動作を分岐する箇所は見つからなかった。代わりに、アプリ、CLI、MCP サーバー、チューニング処理などが Python 子プロセスを起動する際、子の環境に `PYTHONUNBUFFERED="1"` を設定する。Dockerfile もコンテナ環境の初期値として `1` を宣言する。したがって、Strata 側で確認できる役割は子プロセス環境への設定であり、この変数による Strata エンジンの計算・モデル選択・生成内容の変更は確認できない（例: `app/host/server/control-runtime.mjs:82-95`, `terminal/strata_cli/launch/runner.py:969-979`, `terminal/tools/strata_mcp.py:2741-2743`）。

## 値と判定

Strata は親プロセスから継承した値を真偽値や文字列として判定しない。以下の子プロセス起動経路では、既存値が unset、空文字、`0`、`false`、その他の文字列のいずれでも、環境辞書を組み立てるときに文字列 `"1"` で上書きされる。値の大文字小文字・空白・数値妥当性を Strata が検査することもない。

| 経路 | 親環境の値 | 子環境での結果 |
|---|---|---|
| アプリの source checkout 起動経路 | unset / 空 / 任意値 | `sourceServerEnvironment` が `"1"` を設定する（`app/host/server/control-runtime.mjs:82-85`）。 |
| アプリの Control 実行経路 | unset / 空 / 任意値 | `controlEnvironment` が `"1"` を設定する（`app/host/server/control-runtime.mjs:89-99`）。 |
| MCP の setup・server 起動、CLI launch、チューニング worker | unset / 空 / 任意値 | 子起動用辞書で `"1"` を設定する（`terminal/tools/strata_mcp.py:2741-2743,2804-2809,3151-3164`; `terminal/strata_cli/launch/runner.py:969-979`; `terminal/strata_control/tune_session.py:553-569`）。 |
| Docker イメージ | 実行環境からの値は読み取らない | Dockerfile の環境初期値を `1` とする（`tools/docker/Dockerfile:107-115`; `tools/docker/Dockerfile.src:147-153`）。 |
| `tools/check` の実行 | unset / 空 / 任意値 | `Scratch.env()` が `"1"` を設定し、その後 `extra` 引数に同名キーがあればその値で上書きする（`tools/check:79-85`）。 |

このリポジトリの Strata 所有コードには、対象変数の unset・空文字・無効値を判定する分岐はない。Docker 起動時にイメージ既定値がどう上書きされるかは Docker 実行側の設定であり、Strata の読み取り動作ではない。

## 有効になる条件

- 値を設定するのは、該当する Strata 経路が子プロセスを起動する場合。通常のホストプロセスでこのキーの有無を確認して有効化する機能はない。
- アプリでは source checkout のサーバー起動に `sourceServerEnvironment` が使われる。Control を同梱して動かす経路では `controlEnvironment` が、Control の Python CLI・MCP プロセス・installer 用環境に使われる（`app/host/server/native-control.mjs:689-692`; `app/host/server/control-runtime.mjs:82-119,141-146`; `app/host/server/native-control.mjs:197-205`）。
- MCP の install/start と setup job、CLI launch が各自の子プロセス環境を作る場合に設定される（`terminal/tools/strata_mcp.py:2741-2743,2792-2809,3151-3164`; `terminal/strata_cli/launch/runner.py:969-979,1045-1049`）。
- tuning worker は worker の起動ごとに設定する（`terminal/strata_control/tune_session.py:553-569`）。
- `tools/check` はチェック用の子プロセスに渡す環境を生成する。`extra` が同名キーを指定した場合だけ、初期値 `"1"` が後から置き換わる（`tools/check:79-85,93-106`）。
- `tools/docker/Dockerfile` と `Dockerfile.src` はイメージの `ENV` として設定する。Docker の実行時環境がこの既定値を置換し得ることを除き、Strata 側に OS・backend・GPU・build macro に応じた判定はない（`tools/docker/Dockerfile:107-115`; `tools/docker/Dockerfile.src:147-153`）。

## 実行時の詳細

この変数を読む Strata の関数・共通 env helper は見つからない。各経路が環境辞書を作るタイミングで固定値を代入し、その辞書を subprocess 起動 API に渡す。常駐プロセス内で値を cache したり、起動後に親環境の変更を再評価したりする処理ではない。子ごとに環境を作る経路では、その起動のたびに代入する。

- アプリは起動した server の stdout/stderr を読み、行を UI の job log に追加する。source checkout では `sourceServerEnvironment()` の結果を `spawnProcess` に渡す（`app/host/server/native-control.mjs:689-692`）。同アプリの native operation も環境に設定して起動し、stdout/stderr を job log に追記し、終了コードが 0 以外なら `Operation stopped (exit ${code}). Open diagnostics for details.` として失敗する（`app/host/server/native-control.mjs:735-741`）。Control 経路の共通 CLI 起動も `controlEnvironment()` を渡す（`app/host/server/control-runtime.mjs:141-146`）。
- MCP install/start は `os.environ` の複製に `PYTHONUNBUFFERED="1"` を指定して `spawn_detached()` へ渡す。子の stdout/stderr はログファイルにまとめられ、start が早期終了すると末尾の出力を含む `Strata stopped while starting (exit code ...). Its last output:` エラーになる（`terminal/tools/strata_mcp.py:395-408,2741-2743,2804-2809,2818-2827`）。install job は setup 子プロセスに同じ値を渡し、終了コードを記録する（`terminal/tools/strata_mcp.py:3151-3169`）。
- CLI launch runner は `_env()` で固定値を作り、`_spawn()` から子に渡す。engine 更新前の確認では `self.s.extra` の項目を後から環境へ反映するため、同名の `extra` が `off` / `unset` / `none` 以外なら固定値を上書きできる。他の launch 子プロセスでは `_env()` の環境を使う（`terminal/strata_cli/launch/runner.py:969-979,1045-1049,1661,1800-1805,2331`）。
- tuning worker は各実行の `spawn_env` に値を代入して `lifeline.popen()` に渡す。標準出力と標準エラーは worker log に記録され、起動失敗は `FAIL_BOOT`、規定秒数内に ready にならない場合は `TIMEOUT` の `StartFailed` になる（`terminal/strata_control/tune_session.py:553-569,575-593`）。
- `tools/check` の `Scratch.env()` はチェック対象コマンド用の環境辞書を返し、`run_cmd()` がそれを子へ渡す（`tools/check:79-85,93-106`）。

## ログと測定値

この変数専用の Strata ログ、警告、終了コード、測定値はない。上記のログ追記・失敗報告は各子プロセス起動経路の一般的な処理であり、`PYTHONUNBUFFERED` の値を読んだ結果として出るものではない。子プロセスの出力をアプリの job log、MCP のログファイル、CLI の worker log に集めるコードはある（`app/host/server/native-control.mjs:689-692,741`; `terminal/tools/strata_mcp.py:395-408,2822-2837`; `terminal/strata_control/tune_session.py:547-569`）。

## 根拠

- アプリが child env に固定値を設定する定義: `app/host/server/control-runtime.mjs:82-107`; installer 用環境の継承: `app/host/server/control-runtime.mjs:111-119`。
- アプリでの server、MCP client、native operation の起動: `app/host/server/native-control.mjs:142,197-205,689-692,735-741`。
- MCP の detached process と値の設定・setup 起動・start 失敗時の出力: `terminal/tools/strata_mcp.py:395-408,2741-2743,2804-2827,3151-3169`。
- CLI launch runner の環境生成・追加設定・子起動: `terminal/strata_cli/launch/runner.py:969-979,1045-1049,1661,1800-1805,2331`。
- tuning worker の値設定・起動・ready timeout: `terminal/strata_control/tune_session.py:553-593`。
- `tools/check` のチェック用環境: `tools/check:79-85,93-106`。
- Docker image の初期環境: `tools/docker/Dockerfile:107-115`; `tools/docker/Dockerfile.src:147-153`。
