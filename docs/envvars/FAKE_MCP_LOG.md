# `FAKE_MCP_LOG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

これは `serve/mcp_fake_server.py` が受け取った MCP の tool call と cancellation を JSON Lines 形式で記録するための環境変数です。fake server 専用の fixture に実装されており、Strata の通常サーバーや engine の動作を設定する変数ではありません。`serve/test_mcp.py` は一時ファイル名を設定して fixture の記録をテストします。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | ログを書かない |
| 空文字 | `os.environ.get()` が空文字を返し、偽として扱われるためログを書かない |
| 空でない値 | 値をそのままファイルパスとして `open(path, "a", encoding="utf-8")` に渡し、JSON 1行を追記する |

値の trim、パス検証、別の既定パスへの fallback はありません。文字列の内容や数値としての妥当性も検査しません。値はログ関数の呼び出しごとに環境から読み直され、static cache されません。

## 有効になる条件

fixture が `log()` を呼び出す処理に到達し、かつ環境変数が空でない場合にファイル出力します。stdio モードと fixture の HTTP モードはいずれも同じ `handle()` を使うため、両方で tool call と cancellation が対象です。通常の Strata MCP client 自体は `FAKE_MCP_LOG` を読みません。

## 実行時の詳細

`tools/call` を受けると、tool の実行結果を作る前に `{"call": name, "arguments": args}` を追記します。したがって `die` のように fixture が途中終了する tool も、呼び出し記録は先に残ります。`notifications/cancelled` は cancellation ID を `cancelled` set に追加し、`{"cancelled": requestId}` を追記します。initialize、tools/list、通常の request response はこのファイルに記録されません。

テストは一時 JSONL ファイルを作り、MCP child process の起動前に `os.environ["FAKE_MCP_LOG"]` を設定します。`serve/mcp.py` は起動環境を `dict(os.environ)` で複製し、設定の `env` 項目があればその値で上書きして child に渡すため、テスト fixture はこの変数を継承します。テスト終了時は child を閉じた後、親プロセスの変数を削除し、一時ファイルを消します。

## 根拠

- `serve/mcp_fake_server.py:1-9` はこのファイルを `serve/test_mcp.py` 用 fake MCP server と説明し、環境変数の目的を示します。
- `serve/mcp_fake_server.py:36-40,47-54,65-68,162-172` は値の読み取り、追記形式、記録対象、stdio/HTTP 起動経路を示します。
- `serve/test_mcp.py:1-4,25-32,59-73,237-252` は fixture のテスト用途、一時ファイル設定と cleanup を示します。
- `serve/mcp.py:93-107` は親環境の複製、config `env` による上書き、child process への受け渡しを示します。
- `docs/DETAILS.md` に `FAKE_MCP_LOG` の製品向け仕様や測定値の記載はありません。
