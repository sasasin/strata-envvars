# `STRATA_DEBUG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のサーバーで診断ログを追加する。値は計算設定には使われず、API リクエストの要約、生成 token の内容と ID、stdio MCP 子プロセスの stderr 行を stdout に出す条件になる。生成処理や応答内容を変える分岐はない。実装は `terminal/serve/server.py` と `terminal/serve/mcp.py` にある。 (`terminal/serve/server.py:6155-6157,6265-6277`; `terminal/serve/mcp.py:170-176`)

## 値と判定

3 箇所とも `os.environ.get("STRATA_DEBUG")` の戻り値をそのまま真偽値判定する。未設定または空文字列は偽で無効。`"1"` に限らず、`"0"`、`"false"`、大文字の値、空白だけの値を含む、空でない文字列は真で有効になる。文字列の parse、大小文字変換、空白除去、数値変換、範囲検査はない。無効値時の fallback 処理もない。 (`terminal/serve/server.py:6265-6268,6155`; `terminal/serve/mcp.py:170-176`)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| サーバーのリクエスト診断・生成 token ダンプ | 無効 | `1`, `0`, `false`, ` ` | 空文字列 |
| MCP stdio 子プロセス stderr の転送 | 無効 | `1`, `0`, `false`, ` ` | 空文字列 |

## 有効になる条件

- リクエスト要約はサーバーが OpenAI、Responses、Anthropic の各 API リクエストを準備でき、`_debug_req` を呼ぶ場合に出る。リクエスト準備前の拒否や失敗ではこの呼び出しに到達しない。 (`terminal/serve/server.py:7857-7861,8097-8114,8151-8174`)
- 生成 token のダンプは `Service.run` の後処理に入り、状態が busy で timeout しておらず、`raw_ids` が空でない場合に限る。変数が有効でも、生成 token がなければダンプは出ない。 (`terminal/serve/server.py:6086-6091,6155-6157`)
- MCP の stderr 転送は `StdioTransport` が読み取る非空 stderr 行ごとに判定する。MCP 利用のリクエスト自体は OpenAI 経路で `strata_mcp: true` かつ `svc.mcp` がある場合に opt-in されるが、この環境変数は MCP の有効化条件ではない。 (`terminal/serve/server.py:7843-7851`; `terminal/serve/mcp.py:170-176`)
- OS、GPU backend、build macro、モデル状態、CLI 引数による判定差はこれらの読み取り箇所にはない。MCP 子プロセス用の環境は親環境をコピーした後、設定の `env` で上書きするが、ここで `STRATA_DEBUG` を調べるのは親プロセスの stderr reader である。 (`terminal/serve/mcp.py:138-152,170-176`)

## 実行時の詳細

- `_debug_req` は prompt 準備後、生成処理を始める前に呼ばれる。stdout に `[strata] req ...` の一行を flush して出力し、API 名、message/tool 数、要求時の token 上限、解決済み `max_new`、thinking / stream 状態、prompt token 数、最後の message の role と最大 80 文字の本文 preview を含める。 (`terminal/serve/server.py:6265-6277,7859-7861,8112-8114,8170-8174`)
- 生成後処理では蓄積した `raw_ids` を tokenizer で decode した repr と整数 ID のリストをそれぞれ `[strata] raw:`、`[strata] raw ids:` として stdout に flush する。`raw_ids` にはエンジンから受け取った token に加えて、停止 token とサーバーが生成列へ追加する token も追加される。 (`terminal/serve/server.py:5830-5834,5971-5975,6052-6057,6155-6157`)
- MCP の stderr reader は各行を UTF-8（不正 byte は置換）で decode し、末尾空白を除く。空でない行は保存し、環境変数が真なら親プロセスの stdout に `[mcp {name}] {line}` として flush する。判定値をキャッシュせず行ごとに読む。 (`terminal/serve/mcp.py:170-176`)
- 環境変数はモジュール初期化時の定数ではなく、各診断呼び出し・各 stderr 行・生成後処理で参照される。したがって実行中にプロセスの環境辞書が変更された場合、後続の判定に反映される。 (`terminal/serve/server.py:6155,6267`; `terminal/serve/mcp.py:175`)

## ログと測定値

有効時のリクエスト行は `[strata] req {api}: msgs=... tools=... max_tokens_raw=.../... max_new=... thinking=... stream=... prompt_tokens=... last=...` の形式。生成 token がある後処理では `[strata] raw: ...` と `[strata] raw ids: [...]`、MCP stderr では `[mcp {name}] {line}` が出る。いずれも `print(..., flush=True)` による stdout 出力で、無効時には該当する診断出力を行わない。測定値の出力や計測変更ではない。 (`terminal/serve/server.py:6155-6157,6265-6277`; `terminal/serve/mcp.py:170-176`)

## 根拠

- `terminal/serve/server.py:5661,5830-5834,5971-5975,6052-6057,6155-6157` — token ID の蓄積と生成後ダンプ。
- `terminal/serve/server.py:6265-6277,7857-7861,8097-8114,8151-8174` — 値判定、出力内容、各 API 経路。
- `terminal/serve/mcp.py:138-152,170-176` — MCP 起動時の環境構築と stderr の条件付き転送。
- `terminal/serve/test_server.py:238-250` はテスト内で値をセットする参照であり、本番動作の根拠にはしていない。`docs/bench-results/2026-10-07-community-arc-b65-v01402/environment.json:15` は記録データで読み取り実装ではない。
