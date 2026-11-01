# `STRATA_KEEP_LEFTOVERS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`strata serve` の Python サーバーが新しい engine プロセスを起動する直前に行う、前回の実行から残った engine の終了処理を抑止します。対象は、Strata が記録した起動元の終了済みプロセス配下の残存プロセスと、旧版 Strata が記録を残さず起動した同じ実行ファイルの orphan engine です。engine の通常終了処理を変える設定ではありません（`serve/server.py:134-148,1074-1079`、`strata_control/procs.py:342-353,358-407`）。

## 値と判定

値は `os.environ.get(...) == "1"` で文字列全体を比較します。数値変換や空白除去、大文字小文字変換はありません。

| サーバープロセスの環境値 | 動作 |
|---|---|
| 未設定 | 残存 engine の確認・終了処理を行う |
| 空文字 | 確認・終了処理を行う |
| `1` | 確認・終了処理を行わず、そのまま次の engine 起動へ進む |
| その他（例: `0`, `true`, `01`, ` 1`） | 確認・終了処理を行う |

根拠: `serve/server.py:142-148`。

## 有効になる条件

- `serve.server` が `--engine strata` で動き、実際に `StrataEngine` が engine プロセスを起動するときに評価されます。`--engine mock` はこの経路を通りません（`serve/server.py:9185-9199,9273-9289,1074-1079`）。
- `--lazy` または設定の `lazy_load: true` では、サーバー初期化時の `StrataEngine` 構築が先に戻ります。初回ロード時の engine 起動で判定されます（`serve/server.py:1017-1019,1043-1045,9199`）。
- 複数 engine を起動する構成でも、それぞれの `StrataEngine` 起動直前にこの関数が呼ばれます。自動再起動時にも `__init__` が再度実行され、判定し直します（`serve/server.py:1074-1079,1343-1351,8688-8711,8757-8778`）。
- 判定に使うのはサーバープロセス自身の `os.environ` です。engine に渡す `env` 辞書や CLI 引数との値の優先順位はなく、それらからこの判定値を上書きする処理はありません（`serve/server.py:1017-1019,1074-1079,9191-9194`）。サーバープロセス内で `os.environ` が変更された場合は、次の engine 起動時の判定に反映されます。

## 実行時の詳細

値が厳密に `1` でない場合、サーバーは記録済みの残存プロセスを `end_leftovers()` で調べ、さらに起動予定の実行ファイルに一致する orphan engine を `end_orphans()` で調べます。記録済みプロセスは PID、開始時刻、コマンドライン、起動元の生存状況を照合し、旧版由来の orphan は起動予定と同じ実行ファイルで `--serve` があり、生きた起動元がいないものを対象にします。PID・開始時刻・コマンドラインは signal の直前にも再確認されます（`strata_control/procs.py:269-291,294-303,342-353,358-405`）。

終了処理は Unix 系ではまず `SIGTERM` を送り、猶予時間後も同一プロセスなら `SIGKILL` を試みます。Windows では検証後に `taskkill /F` を実行します。サーバーは各確認処理に `settle=120` 秒を渡すため、終了待ちは最大120秒です。待機中はおよそ10秒ごとに進捗を出します（`serve/server.py:131,147-148`、`strata_control/procs.py:305-339`）。

120秒後も終了しない PID があれば `[strata] WARNING: the engine from an earlier run ...` と出力してから、新しい engine の起動を続けます。確認処理自体で例外が起きた場合も `[strata] could not check for engines left by an earlier run: <例外型>` を出し、起動を止めません（`serve/server.py:138-155`）。`STRATA_KEEP_LEFTOVERS=1` の場合は確認関数を呼ばず、これらの清掃時ログも出しません。

## 根拠

- `serve/server.py:131-155` — 待機時間、環境値の完全一致判定、二種類の確認、警告と例外時の継続。
- `serve/server.py:1017-1045,1074-1079,1343-1351` — lazy 起動、engine 起動直前の呼び出し、再起動での再評価。
- `serve/server.py:9185-9199,9273-9289` — Strata / mock の選択と lazy 設定。
- `strata_control/procs.py:269-303,305-353,358-407` — 残存・orphan の識別、終了方法、待機と結果。
- `docs/CLOSING.md:58-60` — 同じ設定についての既存説明。実装上の判定と一致。
