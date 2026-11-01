# `STRATA_DEBUG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

サーバーの診断情報を標準出力へ追加します。対象は API リクエストの概要、完了した生成の token 列、stdio MCP サーバーから届いた stderr 行です。モデル計算や API の選択を変える設定ではありません。

## 値と判定

3 つの読み取り箇所はいずれも Python の `os.environ.get("STRATA_DEBUG")` を条件式に使います。文字列を数値や真偽値として parse せず、Python の文字列 truthiness で判定します。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効（`None` は偽） |
| 空文字 `""` | 無効 |
| 空でない任意の文字列 | 有効。`"1"`、`"0"`、`"false"`、空白だけの値も含む |

大文字小文字、前後の空白、数値としての妥当性は検査されません。CLI 引数、設定ファイル、別の環境変数による既定値や優先順位はありません。

## 有効になる条件

- `serve/server.py` の OpenAI Chat Completions、Responses、Anthropic Messages の各リクエスト経路で、リクエスト準備が成功して `_debug_req()` が呼ばれると概要行を出します。生成 token の診断行は、生成完了時に `raw_ids` が空でない場合に限ります。
- MCP の stderr 中継は `serve/mcp.py` の stdio transport に限られます。HTTP MCP transport の stderr を読む経路ではありません。
- OS、GPU backend、build macro、モデル状態による分岐はありません。Python サーバーがこの環境変数を参照します。

## 実行時の詳細

設定値は各判定箇所で都度読み取られ、module-level 定数や `static` 値には保存されません。したがって、サーバープロセス内で値が変更された場合は、後続の判定に反映されます。

`_debug_req()` は準備済みの各リクエストについて、API 種別、message/tool 数、要求 token 上限、解決済みの `max_new`、thinking / stream の状態、prompt token 数、最後の message の role と本文 preview を `[strata] req ...` の行として標準出力へ flush します。本文 preview は文字列化後の先頭 80 文字で、改行を空白に置き換えます。content が部品の list の場合は text 部品だけを連結します。

生成処理の完了時には、`raw_ids` がある場合に token 列を decode した `[strata] raw: ...` と、整数 ID 一覧の `[strata] raw ids: ...` を標準出力へ flush します。`raw_ids` には生成中に受け取った token ID が追加されます。例外などで完了時のこの処理に到達しない場合は、これらの行は出ません。

stdio MCP transport は子プロセスの stderr の各非空行を内部の直近ログ用 deque に保存し、`STRATA_DEBUG` が有効なら `[mcp <name>] ...` としてサーバーの標準出力へも flush します。子プロセス起動時には親環境のコピーを渡し、MCP 設定の `env` がその値を上書きできます。ただし中継を有効にする判定は Strata サーバー自身の環境値です。

これらの診断出力には利用者の最後の入力本文、モデル出力、および MCP プロセスが stderr に書いた内容が含まれることがあります。

## 根拠

- `serve/server.py:7880-7882`, `8084-8087`, `8114-8118` — OpenAI Chat Completions、Responses、Anthropic Messages それぞれで準備後に診断 helper を呼び出す。
- `serve/server.py:6112-6124` — 真偽値判定、出力先・項目、本文 preview の整形。
- `serve/server.py:5542-5546`, `5686-5694`, `5828-5832`, `5858-5863`, `5944-5953` — request 内の token 収集と、完了時に raw text / ID を出す条件・形式。
- `serve/mcp.py:82-84`, `96-110`, `128-134` — stdio transport の範囲、子プロセス環境の継承と `env` 上書き、stderr の保存と条件付き中継。

