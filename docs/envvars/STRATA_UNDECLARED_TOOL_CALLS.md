# `STRATA_UNDECLARED_TOOL_CALLS`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Strata サーバーが、リクエストで宣言されていない名前の tool call をどう扱うかを選びます。既定の `text` では、未宣言 call はモデルが出力したテキストのまま返し、応答に `strata_rejected_tool_calls` を添えます。`call` では、パーサーが完全な tool call と認識した未宣言名も tool call としてクライアントへ返します。Strata がその未宣言 tool を実行する設定ではありません。

設定ファイルの `undeclared_tool_calls` と同じ選択肢です。これは `serve/server.py` の Python サーバー側の設定であり、C++ engine の設定ではありません（`serve/server.py:9853-9862,10364-10370`）。

## 値と判定

| 設定ファイル `undeclared_tool_calls` | 環境変数 | 結果 |
|---|---|---|
| `"text"` | 任意 | `text`。環境変数は読まれず、設定が優先される |
| `"call"` | 任意 | `call`。環境変数は読まれず、設定が優先される |
| キーなしまたは `null` | 未設定 | `text` |
| キーなしまたは `null` | `text` | `text` |
| キーなしまたは `null` | `call` | `call` |
| キーなしまたは `null` | 空文字 | `text`（`or "text"` による fallback） |
| キーなしまたは `null` | 上記以外 | サーバー起動を中止 |

値は文字列全体で比較され、大文字小文字の変換、空白除去、数値変換はありません。したがって `CALL`、` call`、`call ` は無効です。設定ファイル側も値が `"text"` / `"call"` 以外なら同じ検証で起動を中止します。設定ファイルに空文字が明示されている場合は環境変数へ fallback せず、無効値になります。エラーは `[strata] config "undeclared_tool_calls" must be "text" or "call", not ...` です（`serve/server.py:9857-9862`）。

## 有効になる条件

- サーバープロセスの設定初期化で評価されます。CLI にこの設定専用の引数はなく、設定ファイルの `undeclared_tool_calls` が環境変数より優先されます（`serve/server.py:9920-9955,10027,10364-10370`）。
- `text` は既定動作です。未宣言名の call は通常の完了テキストとして返されます。サーバーログには未読 `<tool_call>` block 数と、分かる場合は名前が出力され、応答に `strata_rejected_tool_calls` が付きます（`serve/server.py:6754-6774,7227-7231,7292-7295`）。
- `call` は各リクエストの parser に `deferred=True` を渡します。tool schema があると、パーサーは宣言外の名前も call として認めます。schema がない場合、`declared_only=True` の Chat Completions / Anthropic 経路では `_callable()` が未宣言 call を認めないため、この設定だけでは有効になりません。一方 `/v1/responses` は `declared_only` を指定せず既定の `false` を使うため、schema がないときも parser は名前を問わず call を認めます。この経路では、その条件に限り `call` と `text` の差はありません（`serve/server.py:6251-6253,6911,7185,7413,8751`; `serve/frontend.py:1177-1189,1277-1282`）。
- パーサーが call とするには、モデル出力が call の構文を満たして一連の call として読める必要があります。文章中の言及や不完全な call を一般的に tool call に変換するものではありません（`serve/frontend.py:1715-1727,1911-1933,1991-2018`）。
- OS、GPU backend、build macro による分岐は、この設定を読む箇所にはありません。機能はサーバーの出力パーサーに作用します。

## 実行時の詳細

設定ファイルはサーバー起動時に読み込まれ、`undeclared_tool_calls_setting(cfg)` が環境変数を参照して結果を `svc.undeclared_tool_calls` に格納します。各リクエストで parser を作る際、その保存値を `deferred` 判定に使います。リクエストごとに環境を読み直す処理や、この値を engine の子プロセスへ渡す処理は確認できません。したがって起動後に環境値を変更しても稼働中サーバーの選択は変わらず、サーバーを再起動して再評価する必要があります（`serve/server.py:9853-9862,10027,10364-10370,6251-6253`）。

`text` では、未宣言 call はモデルのテキストのまま返り、名前が分かる場合は最大5件を `strata_rejected_tool_calls` に記録します。非 streaming の Chat Completions 応答では最上位、streaming では最終 chunk に付きます。Anthropic `/v1/messages` では `message_delta` と集約後の message に付きます。ログには未宣言名（存在する場合）を含む診断が出て、`/metrics/prometheus` の `strata:tool_calls_unread_total` に block 数が加算されます（`serve/server.py:6754-6764,7227-7231,7292-7295,7465-7470,7498-7503,5750-5751`）。

`call` では受理された call が通常の `tool_call` parser event となり、Chat Completions の `tool_calls` や Anthropic の tool-use block として返ります。Strata はその call を自ら実行せず、クライアント側の方針に委ねます（`serve/frontend.py:1715-1727,1930-1934,2033-2038`; `serve/server.py:7202-7214`）。

## 根拠

- `serve/server.py:9853-9862` — config 優先、環境変数読み取り、既定値、値の検証と起動エラー。
- `serve/server.py:10027,10364-10370` — 起動時の config 読み込みとサービス設定への格納。
- `serve/server.py:6251-6253,8751`; `serve/frontend.py:1177-1189,1277-1282` — 保存値を parser に渡す箇所と、API route / tool schema の有無による callable 判定。
- `serve/frontend.py:1715-1727,1911-1933,1991-2018` — 完全な call の認識、未宣言 call のテキスト扱い、call 終了処理。
- `serve/server.py:6754-6774,7227-7231,7292-7295,7465-7470,7498-7503,5750-5751,7202-7214` — ログ、メトリクス、各 API 形式での返却。
- `docs/DETAILS.md:495,534-541` — サーバー設定の説明および既定 `text` 時の応答説明。上記の処理内容はソースコードで確認。
