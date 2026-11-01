# `STRATA_COALESCE_PREFILL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`serve/server.py` の `--batch`（並列 slot）経路で、control line を取得したリクエストが、control line 待ちの別リクエストの prompt を空き slot に先行して割り当て、engine に `BCO` 行で送ります。engine は次の `BGEN` の prompt と follower の prompt を同じ multi-prompt prefill pass で読みます。値 `N` は leader を含む coalesce 数の上限で、最大 `N-1` 件を follower にできます。

これは server 側が読む設定です。engine は環境変数を直接読みません。engine は server から届く `BCO` / `BGEN` protocol を処理します。通常の非 batch 経路、batch 中でも単独リクエストを `GEN` で読む経路、embedding 入力にはこの coalesce 処理は適用されません。

## 値と判定

server は `serve/server.py` の import 時に `int(os.environ.get("STRATA_COALESCE_PREFILL") or 0)` を評価し、その後 `max(0, ...)` で下限を 0 にします。文字列全体を Python の `int()` で変換します。

| 環境値 | 判定 |
|---|---|
| 未設定 | `0`。無効 |
| 空文字 | `or 0` により `0`。無効 |
| `0` または負の整数 | `max(0, value)` により `0`。無効 |
| 正の整数 `1` | 値は 1 だが、実行箇所の `COALESCE_PREFILL > 1` 条件を満たさず無効 |
| 整数 `N >= 2` | coalesce を試行。leader 以外は最大 `N-1` 件 |
| 整数でない文字列 | `int()` の `ValueError` が server module の import 時に発生する。ここでは例外を捕捉せず、server 起動を妨げる |

正の値にコード上の上限 clamp はありません。実際の follower 数は、待ち行列にある適格リクエスト数、空き slot 数、prompt 合計 token 上限、および engine 側の受理条件でさらに制限されます。CLI 引数や設定ファイルからこの値を上書きする処理は確認できません。

## 有効になる条件

- Python server が `--batch` 等で batch slot を持ち、リクエストが `generate_batched()` に入ること。値が 2 以上でも、batch がなければ `generate_batched()` は呼ばれません。
- 対象リクエストが embedding 入力でないこと。leader に対して `_coalesce()` を呼ぶ条件にも、待機 prompt を `_take_control()` に登録する条件にも `not embeddings` があります。
- `COALESCE_MIN_REQS` 以上の最近到着リクエストがあること。既定値は 3 です。足りない場合、`COALESCE_WAIT_MS > 0` なら一度 10 ms 待って再確認し、それでも足りなければ通常読み込みに戻ります。十分なら設定された `COALESCE_WAIT_MS` だけ待ってから follower を選びます。
- 待機 follower は同じ coalesce に重複参加しておらず、prompt が 32 token 以上で、leader と選択済み follower の合計が `COALESCE_TOKENS` 以下であること。`COALESCE_TOKENS` の既定値は 16384 です。さらに空き slot が必要です。
- engine が `BCO` を有効 slot と 3 token 以上の ID 列として受け取り、次の `BGEN` と同じ batch admission の co-read に使うこと。engine は最初の prompt run で、画像 request がない場合にだけ multi-prompt run を試します。`run_multi()` が `prefill: multi-prompt read declined` で断った場合は leader の通常 `run()` に fallback します。

## 実行時の詳細

設定値は server module の import 時に一度だけ読み取られ、module global に保持されます。稼働中にプロセス環境を変更しても再評価されません。値は engine 子プロセスへ環境変数として転送されず、server が `BCO <slot> <ids>` と次の `BGEN` を送って機能を依頼します。

`_take_control()` は到着時刻、tokenized prompt、request cancel object を待ち行列に登録します。batch の admission が slot を取得すると、`_coalesce()` は最近の到着数を確認し、候補 follower ごとに prompt 長と合計 token 数を検査して空き slot を予約します。選択した follower の prompt ID を `BCO` 行として送ってから leader の `BGEN` を送ります。server は follower に予約 slot を持たせ、その後 follower 自身の admission 時には prompt を再読込しない経路に接続します。

engine は `BCO` 行を次の `BGEN` まで保留し、prompt 条件が許せば `Prefill::run_multi()` を実行します。成功時は follower slot に prompt state を置き、stdout に `BCOK <slot> <tokens>`、stderr に `strata batch: co-read: ...` を出します。server の `_control()` は `BCOK` を認識して処理を継続します（行を受け取っただけで追加処理はしません）。server 側では follower を選んだ場合に stdout へ `[strata] coalesce: ...` を出します。

候補選択の結果 follower がなければ server 側の coalesce ログは出ません。engine が multi-prompt read を decline した場合は stderr に `strata batch: co-read of ... declined (...)` を出し、leader の通常読み込みを行います。その他の `run_multi()` 失敗は co-read lambda から失敗として返され、通常の request error 経路に進みます。`BCO` を protocol として受け付けても、slot 範囲外や ID が 3 token 未満なら engine は保留リストに加えず、その行自体について警告は出しません。

## 根拠

- `serve/server.py:340-346` — 環境変数の値変換、既定値、関連する token/wait 設定。
- `serve/server.py:1747-1755,1796-1804` — prompt と到着時刻の待ち行列登録、control line 待ちの管理。
- `serve/server.py:1817-1859` — burst 条件、follower の選択・予約、`BCO` 送信とログ。
- `serve/server.py:1916-1926,2078-2086,2327-2336` — prompt の登録条件、batch admission から coalesce を呼ぶ条件、batch 以外との分岐。
- `src/program/generate.cpp:12570-12575,13530-13543,13565-13583` — engine の `BCO` parse、slot/ID 条件、次の `BGEN` への保留。
- `src/program/generate.cpp:15178-15238,15240-15248` — multi-prompt 実行条件、decline fallback、成功時の `BCOK` と stderr ログ。

`docs/DETAILS.md` にはこの変数名または co-read の説明が見つからず、性能値や測定条件は記載していません。
