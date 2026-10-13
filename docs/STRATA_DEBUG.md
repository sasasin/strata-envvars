# `STRATA_DEBUG`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Python サーバー（`serve/`）だけの診断ログ用の環境変数。C++/CUDA/HIP エンジン（`src/`、`include/`、`sycl/`）は `STRATA_DEBUG` を読まない。リポジトリ全体を検索した結果、環境から値を読む実装は `serve/server.py` と `serve/mcp.py` にある 3 箇所だけで、いずれも stdout への追加ログを制御する。生成結果・トークン・API レスポンスの内容は変えず、ログ行が増えるだけである。

制御する出力は次の 3 種類。

1. API リクエスト受付時、エンドポイントごとに 1 行の要約（`_debug_req`）。
2. 生成終了時、モデルが生んだトークン系列の raw デコード（`[strata] raw: ...`）。
3. MCP サブプロセスの stderr 行をサーバー stdout へ写すエコー（`[mcp <name>] ...`）。

## 値と判定

判定は `os.environ.get("STRATA_DEBUG")` の**真偽値（truthiness）**だけで、文字列 parse・`"1"` との比較・数値変換・大文字小文字・空白の検査はない。

| 状態 | 判定 |
|---|---|
| 未設定（`None`） | 無効（falsy） |
| 空文字 `""` | 無効（falsy） |
| 非空文字列（`1`、`0`、`true`、`false`、`2` など） | 有効（truthy） |

したがって `STRATA_DEBUG=0` や `STRATA_DEBUG=false` でも**有効**になる。docstring は「Set `STRATA_DEBUG=1` to enable」と書くが、実装は値が非空かどうかだけを見る。既定は未設定＝無効。

根拠: `serve/server.py:4197`（`if not os.environ.get("STRATA_DEBUG"): return`）、`serve/server.py:4090`、`serve/mcp.py:131`。

## 評価時期と適用範囲

キャッシュ（static）はしない。各呼び出し・各行の判定で `os.environ.get` を実行するため、プロセス起動後に環境を書き換えると次のリクエスト／次の stderr 行から反映される。

- `_debug_req` はリクエスト受付直後（生成前）に呼ばれる。呼び出し箇所は openai / responses / anthropic の各ハンドラ（`serve/server.py:5367,5560,5589`）。
- raw デコードの print は生成ループの終了処理（`serve/server.py:4090-4091`）。
- MCP エコーは stderr 読取スレッドが 1 行読むたびに判定（`serve/mcp.py:126-132`）。

## 実際の挙動

### 1. リクエスト要約行

`_debug_req`（`serve/server.py:4195-4207`）は有効時のみ、次の形式で 1 行 print する。

```
[strata] req <api>: msgs=<件数> tools=<件数> max_tokens_raw=<max_tokens!r>/<max_completion_tokens!r> max_new=<解決値> thinking=<bool> stream=<bool> prompt_tokens=<token数> last=<role>:<本文80字preview>
```

本文 preview は最後の message の content（list なら text 要素を結合）の先頭 80 字で、改行はスペースに置換。無効時は `return` して何も出さない。

### 2. raw モデルテキスト

`raw_ids` は生成中に毎トークン append される（stop token も append 後 break。`serve/server.py:3837,3839,3972,4002`）。この収集自体は `STRATA_DEBUG` の有無に関係なく常に行われる。print は有効かつ `raw_ids` が非空のときだけ（`serve/server.py:4090-4091`）:

```
[strata] raw: <tokenizer デコード結果の repr>
```

空生成（`raw_ids` が空）では print しない。

### 3. MCP stderr エコー

`_read_stderr`（`serve/mcp.py:126-132`）は MCP サブプロセスの stderr を 1 行ずつ読み、非空行を `self.stderr`（直近 40 行の deque）へ保存する。加えて有効時はその行を stdout へ print する。

```
[mcp <name>] <line>
```

無効時は deque への保存だけ行い、stdout へは出さない。

## 子プロセスへの継承

MCP サブプロセス起動時、`env = dict(os.environ)` に MCP 設定の `env` を上書きして渡す（`serve/mcp.py:94-95,107`）。このコピーには `STRATA_DEBUG` が含まれるため、サブプロセスは現在の環境値を継承する。ただしサブプロセス（外部ツール）がその変数をどう扱うかは Strata の実装ではないので本文書の対象外。Strata 側の動作は「環境をそのまま渡す」ことと「stderr 行をエコーする」ことだけ。

## 有効になる条件

- Python サーバー（`serve/server.py` / `serve/mcp.py`）が動いていること。エンジン単体実行や `setup.py` のインストール経路では読まれない。
- MCP エコーは MCP サーブリクエストが実際に起動し stderr を出す経路でのみ効く。
- raw デコードは生成が 1 以上のトークンを生む経路でのみ効く。

診断ログであり、機能トグルや性能・正確性の変更ではない。`docs/DETAILS.md` には記載がない（開発・診断用フック）。

## 根拠

- 読み取り 3 箇所: `serve/server.py:4197`、`serve/server.py:4090`、`serve/mcp.py:131`。
- 呼び出し箇所: `serve/server.py:5367,5560,5589`。
- `raw_ids` 収集と print: `serve/server.py:3724,3837,3839,3972,4002,4090-4091`。
- MCP stderr エコーと環境継承: `serve/mcp.py:94-95,107,126-132`。
- C++/CUDA/HIP 側の読み取りなし: リポジトリ全体の `rg 'STRATA_DEBUG'` で Python 以外に実装箇所が見つからない。テスト（`serve/test_server.py:170,179`）は truthiness 判定と `max_new` 表示を確認する手掛かりだが、本番コードの挙動の根拠にはしていない。
