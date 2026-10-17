# `FAKE_MCP_LOG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

これは通常の Strata サーバー設定ではなく、MCP のテスト用 fake server (`serve/mcp_fake_server.py`) が受け取ったイベントを JSON Lines 形式で記録するための環境変数です。Strata の MCP クライアントや本番サーバー自身がこの名前を読み取るコードは見つかりませんでした。fake server のモジュール説明は `serve/test_mcp.py` 用と明記しています。

## 値と判定

fake server の `log()` は呼び出しごとに `os.environ.get("FAKE_MCP_LOG")` を読みます。文字列の parse、trim、数値判定はありません。

| 値 | 動作 |
|---|---|
| 未設定 | `None` となり、ログを書きません。 |
| 空文字 | false と判定され、ログを書きません。 |
| 空でない文字列 | その文字列をファイルパスとして `open(path, "a", encoding="utf-8")` し、JSON 1行を追記します。 |

パスが不正、書き込み不可などで `open()` / `write()` が失敗した場合に例外を処理するコードはなく、その呼び出し元へ伝播します。値を読み取る時期は各イベントの記録時です。

## 有効になる条件

`serve/mcp_fake_server.py` が動作し、その `log()` が呼ばれる場合に限ります。`tools/call` を受けると、ツール名と引数を `{"call": ..., "arguments": ...}` として記録します。`notifications/cancelled` は `{"cancelled": ...}` を記録します。その他のリクエストはこの関数経由では記録しません。

リポジトリ全体での参照はこの fake server と `serve/test_mcp.py` に限られます。テストでは一時ファイル名を設定して fake server のイベントを記録し、テスト後に環境変数とファイルを削除します。通常の Strata MCP サーバー動作を有効化したり変更したりする設定ではありません。

## 実行時の詳細

ログはイベントが発生するたびに追記モードで開かれます。各イベントは `json.dumps(event) + "\n"` で UTF-8 の1行になります。値はプロセス環境から都度参照されるため、fake server のプロセス内で環境を変更すれば次回以降の呼び出しに反映されます。子プロセスとして起動する場合、起動元から環境変数が継承されていれば、その子プロセスで読み取られます。

この環境変数による stdout/stderr のログ、警告、終了コード変更はありません。書き込み例外は別です。記録しようとしたイベントの処理経路で例外になります。

## 根拠

- `serve/mcp_fake_server.py:1-9` — `serve/test_mcp.py` 用 fake server であること、およびログ機能の説明。
- `serve/mcp_fake_server.py:36-40` — 値の取得、空値判定、追記モード、UTF-8 JSON Lines の実装。
- `serve/mcp_fake_server.py:47-54,65-68` — cancellation と tool call の記録箇所。
- `serve/test_mcp.py:59-73,237-252` — MCP テストが一時ログファイルを指定し、後片付けで設定を消す箇所。
