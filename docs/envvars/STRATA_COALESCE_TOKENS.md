# `STRATA_COALESCE_TOKENS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、表示された未コミット変更はありません。

## 役割

サーバーの batch admission で複数要求の prompt を同じ layer-major prefill pass にまとめるとき、先行要求と待機要求の prompt token 数の合計上限を指定します。この環境変数自体は coalescing を有効にしません。機能を試す上限要求数 `STRATA_COALESCE_PREFILL` などが別途有効で、適用条件を満たす場合にだけ使われます。

## 値と判定

`serve/server.py` のモジュール読み込み時に、`os.environ.get(...) or 16384` の値を `int()` に渡し、その結果に `max(256, ...)` を適用します（`serve/server.py:344-346`）。

| 設定値 | 判定結果 |
|---|---|
| 未設定または空文字 | 既定値 `16384` token |
| 整数として解釈される値が 256 未満 | `256` token（負値、0 を含む）|
| 256 以上の整数 | 指定値をそのまま上限にする。コード上の上限 clamp はない |
| `int()` で解釈できない文字列 | `ValueError`。この行に fallback や捕捉処理はなく、モジュール初期化が失敗する |

Python の `int()` による変換であり、真偽値文字列としての判定や `atoi` は使いません。CLI 引数・設定ファイルによる同値の上書きはこの読み取り箇所にはありません。

## 有効になる条件

- `StrataEngine.generate()` が batch slot を検出し、`generate_batched()` に入ること（`serve/server.py:2327-2336`）。この環境変数は単一要求の非 batch 経路では参照されません。
- `STRATA_COALESCE_PREFILL` の実効値が 2 以上であること。これを満たす場合だけ、待機要求の prompt を `_take_control()` の待ち行列に保持し、batch admission 時に `_coalesce()` を呼びます（`serve/server.py:344-346,1916-1917,2078-2079`）。
- `embeddings` 要求ではないこと（同上）。
- `_coalesce()` が `COALESCE_MIN_REQS` 以上の到着数を確認すること。件数が足りず `COALESCE_WAIT_MS` が正なら、まず 10 ms 待って再確認します。それでも不足なら coalescing せず通常の prompt 読み込みに戻ります（`serve/server.py:1823-1834`）。既定の最小件数は 3、既定の待機追加時間は 0 ms です（`serve/server.py:346,348-352`）。
- co-read 用に空き slot を確保でき、待機要求の prompt が 32 token 以上であること（`serve/server.py:1835-1854`）。さらに、その要求を加えた合計が `COALESCE_TOKENS` 以下でなければなりません（`serve/server.py:1843`）。
- native engine がサーバーの `BCO` / `BCOK` プロトコルと multi-prompt prefill を実装していること。サーバーのコメントもこのプロトコルを前提としており（`serve/server.py:340-343`）、Strata native engine 側にはコマンド処理と multi-prompt 実行があります（`src/program/generate.cpp:13530-13543,15178-15245`）。

環境変数の読み取り行自体に OS・backend・build macro 条件はありません。実際の対応範囲は、上記のサーバー batch 経路と、起動する native engine の対応状況によります。

## 実行時の詳細

設定値は `serve.server` の import 時にモジュール定数へ読み込まれます。サーバー稼働中にプロセス環境を書き換えても、この定数は再評価されません。Python サーバーは到着した prompt の token ID 数を合算し、先行 prompt に待機 prompt を加えた合計が上限を超える候補を飛ばします。上限は「各 prompt の個別上限」ではなく、co-read 一組の合計上限です。先行 prompt 自体が上限以上でも、待機 prompt を追加すれば上限を超えるため、追加候補は選ばれません（`serve/server.py:1821-1827,1835-1854`）。

選ばれた待機要求には空き batch slot を予約し、サーバーから `BCO <slot> <token IDs>` を送ります。その後 native engine は pending co-read を次の `BGEN` と同じ layer-major pass で処理します。成功時は `BCOK` を出し、stderr に `strata batch: co-read: ...` を出します（`serve/server.py:1845-1859`; `src/program/generate.cpp:13530-13543,15178-15237`）。サーバーは `BCOK` を読み捨てます（`serve/server.py:1594-1595`）。

候補が選ばれなければ co-read の成功ログは出ず、通常の admission に進みます。native engine が multi-prompt read を `prefill: multi-prompt read declined` として断った場合は、stderr に decline 理由を記録して、先行 prompt の通常の `sp.run()` に fallback します（`src/program/generate.cpp:15218-15224`）。この環境変数に固有の警告・エラー・終了経路はありません。無効な数値文字列だけは import 時の未捕捉 `ValueError` になります。

## 根拠

- 環境変数の読み取り、既定値、下限: `serve/server.py:340-352`
- batch 経路と embedding 除外: `serve/server.py:2327-2336,1916-1917,2078-2079`
- 到着数・待機・slot・prompt 長・合計 token 上限による選別: `serve/server.py:1817-1859`
- native engine の BCO 受付と共読み成功・fallback: `src/program/generate.cpp:13530-13543,15178-15245`
- サーバーによる BCOK の受信: `serve/server.py:1594-1595`
