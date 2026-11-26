# `STRATA_STREAM_WRITE_TIMEOUT_S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の Python サーバーが Server-Sent Events (SSE) を書き込むソケットに設定する timeout の一方の上限を秒で指定する。`STREAM_WRITE_TIMEOUT_S` は `terminal/serve/server.py` のモジュール読込時に環境から読み取られ、`Handler._sse()` が HTTP 応答ヘッダーを送った後に、接続 timeout を `STRATA_STREAM_WRITE_TIMEOUT_S` と `STRATA_PEER_STALL_S` のうち 0 でない値の最小値に設定する。既定では前者が 60 秒、後者が 120 秒なので、SSE ソケットには 60 秒が設定される（`terminal/serve/server.py:430-433,464-465,7016-7019,8129-8144`）。

この設定が使われるのはストリーミング応答であり、非ストリーミング応答には `_sse()` が呼ばれない。OpenAI Chat Completions、Responses、Anthropic の SSE 経路、および Responses の準備済みイベント経路が `_sse()` を呼ぶ（`terminal/serve/server.py:8246-8249,8307-8317,8387-8393,8556-8559`）。生成内容やモデル選択を変える設定ではない。

## 値と判定

値は `os.environ.get(name, "60") or 0` の結果を Python の `float()` に渡す。文字列全体を数値として変換し、先頭文字だけの判定ではない。未設定時は `60.0`、設定値が空文字のときは `0.0` になる。`"0"` や `"0.0"` も 0 である。空白を含む有効な数値表記は `float()` の規則で変換されるが、後ろに数値以外が付いた文字列（例 `"0anything"`）や空白だけの文字列は変換に失敗する。大文字小文字を問わない `nan` / `inf` など Python `float()` が受け付ける表記も、このコードでは追加検証されない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| サーバーモジュールの読込 | `60.0` 秒 | `"1"` → `1.0` 秒、`"0"` / 空文字 → `0.0`（この変数による上限なし） | `"true"`、`"0anything"`、空白だけ → `float()` の `ValueError`。代替値への fallback はない |

変換に失敗するとモジュール初期化中に `ValueError` が送出されます。数値として変換できても負数や非有限値の範囲検証・clamp はありません。後述の `settimeout()` 呼出しに渡されるため、ソケット実装が受け付けない値ではそこで例外になり得ます。`_sse()` は `OSError` だけを捕捉しており、そのような値のエラーをここで処理する分岐はありません（`terminal/serve/server.py:433,8139-8144`）。

## 有効になる条件

- `terminal/serve` の Python サーバーで SSE 応答を開始し、`Handler._sse()` が実行されること。非ストリーミング応答では適用されない（`terminal/serve/server.py:8129-8144,8246-8249,8311,8388,8558`）。
- `0` はこの変数の timeout を候補から外す値。`STRATA_PEER_STALL_S` が非 0 ならそちらが残り、接続にはその値が使われる。両方が 0 の場合は `settimeout()` 自体を呼ばず、ここでは socket timeout を設定しない（`terminal/serve/server.py:464-465,8137-8144`）。
- `STRATA_PEER_STALL_S` が非 0 の場合は、2 つの timeout の小さい方が接続に適用される。CLI 引数や設定ファイルによる上書き箇所はこの環境変数の読み取り・適用経路にはない（`terminal/serve/server.py:433,8139-8144`）。
- OS、GPU backend、モデル状態による分岐はこの設定箇所にない。値はサーバーの SSE ソケット設定に使われる。

## 実行時の詳細

環境変数は `server.py` のモジュールトップレベルで一度読み取られ、`STREAM_WRITE_TIMEOUT_S` に保存される。したがって、同一プロセスの実行中に環境変数を変更しても、この値は再読込されない（`terminal/serve/server.py:430-433`）。

SSE 開始時に Strata は 200 応答のヘッダーを書き終えてから、非 0 の timeout 値のリストを作り、その最小値を `self.connection.settimeout()` に渡す。`settimeout()` が `OSError` を送出した場合だけ無視する（`terminal/serve/server.py:8129-8144`）。これは SSE の socket I/O に適用される接続 timeout であり、モデル生成時間やリクエスト全体の長さを制限する設定ではない。ストリームの各書込みと `flush()` はこの後に行われる（`terminal/serve/server.py:8257-8269,8313-8318,8391-8408,8560-8568`）。

ストリーム書込みで `OSError` が発生すると、各配信経路はリクエストを切断として記録する。OpenAI と Anthropic、および Responses の生成経路はさらに `svc.note_client_disconnect(cancel)` を呼び、チャンクまたはイベント列を閉じる。Responses の準備済みイベント経路は切断を記録する（`terminal/serve/server.py:8270-8273,8317-8318,8409-8412,8568-8571`）。ヘッダー送信後のため、HTTP ステータスを別の応答に差し替える経路ではない。

## ログと測定値

この timeout の設定・切れたこと自体を示す専用のログ文言は該当経路にない。書込みエラーはリクエストの `outcome="disconnected"` として記録され、生成を伴う経路では切断通知処理に進む（`terminal/serve/server.py:8270-8273,8317-8318,8409-8412,8568-8571`）。Strata の資料にこの設定の測定値は見当たらない。

## 根拠

- `terminal/serve/server.py:430-433` — 設定の説明と環境変数の読み取り・既定値。
- `terminal/serve/server.py:464-465,7016-7019` — `STRATA_PEER_STALL_S` の既定値と Handler の timeout。
- `terminal/serve/server.py:8129-8144` — SSE 応答後の最小 timeout 選択と接続への適用。
- `terminal/serve/server.py:8246-8269,8270-8273,8307-8318,8387-8412,8556-8571` — SSE 呼出し箇所、書込み、切断時の処理。
