# `STRATA_RUNTIME_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバー内で起動した子プロセスの所有記録と、Linux の「前回の実行が正常終了しなかった」マーカーを profile ごとに識別する値です。モデル設定、推論結果、サーバーの CLI 設定は変えません。`serve.server` は実 engine を使う起動でこの値を前回実行マーカーに渡し、`serve.lifeline` は engine・vision reader・MCP 等の子プロセスを記録するときに `procs.write_record` へ渡します（`terminal/serve/server.py:9005`、`terminal/serve/lifeline.py:273-305`）。

runtime 管理下で起動したサーバーには runtime が選択中の profile 名を環境変数として設定します。この値は親プロセス環境の複製に設定され、サーバー起動時にその環境が渡されます（`terminal/strata_control/runtime.py:1056-1074`）。通常の直接起動では server は既存環境を読みます。

## 値と判定

| 読み取り箇所 | unset | 空文字 | 設定時の扱い |
|---|---|---|---|
| サーバーの前回実行マーカー | `None`。マーカー名の profile 部分は `serve` | `begin` には `""` が渡るが、マーカー名では `serve` にフォールバック | 文字列値を `begin` に渡し、マーカー名の生成時に英数字と `-_.` 以外を `_` に置換し、先頭 80 文字を使う。大文字小文字は保持される（`terminal/serve/server.py:9005`、`terminal/serve/lastrun.py:42-47, 87-108`） |
| lifeline の子プロセス記録 | `None` | `None` | 空でない文字列を変換せず `profile` 欄へ渡す。文字列比較・数値変換・長さ制限はこの読み取り箇所にない（`terminal/serve/lifeline.py:302`、`terminal/strata_control/procs.py:203-220`） |

いずれも真偽値や数値として parse しません。したがって `0`、`1`、`true`、`false`、空白を含む値は、unset や空文字でない限り通常の文字列です。`lastrun.marker_path` ではそれらを profile 名としてファイル名に反映し（許可外文字を `_` に置換して 80 文字に切り詰め）、lifeline では元の文字列のまま記録します。サーバー起動の前回実行マーカーを無効にする別設定は `STRATA_LASTRUN=0` で、文字列全体の完全一致だけが無効化条件です（`terminal/serve/lastrun.py:87-93`）。

## 有効になる条件

- 前回実行マーカーの読み書きは、`lastrun.wants(argv)` が実 engine を指定したと判定するサーバー起動に限られます。`--engine=strata`、または走査中に最初に見つかった `--engine` の次の引数が `strata` の場合です。それ以外（既定の mock を含む）はマーカー処理を呼びません（`terminal/serve/lastrun.py:31-39`、`terminal/serve/server.py:9005`）。
- 条件に合う起動でも Linux 以外、または `STRATA_LASTRUN` が文字列 `0` の場合はマーカーを作りません。unset・空文字・`00` などはこの無効化条件ではありません（`terminal/serve/lastrun.py:87-93`）。
- 過去の終了メッセージを出すのは、同じマーカーの記録先に前回の marker が残り、そこに記録された PID の開始 token が現在のプロセスと一致しないと判定された場合です。別の同一 profile サーバーが稼働中と判定されれば既存 marker を残し、新たな marker は作りません（`terminal/serve/lastrun.py:58-65, 95-108`）。
- lifeline の記録は server が `lifeline.popen` 経由で子プロセスを起動した場合に行われます。server は engine、vision reader のほか MCP や画像処理の子プロセスにもこの経路を使います（`terminal/serve/server.py:363-372, 833-835, 3219-3221`、`terminal/serve/mcp.py:150`、`terminal/serve/images.py:466-467`）。記録は best effort で、失敗しても子プロセスの起動を失敗させません（`terminal/serve/lifeline.py:298-305`、`terminal/strata_control/procs.py:203-223`）。
- 管理 runtime は `child_env["STRATA_RUNTIME_PROFILE"] = self.name` として server 起動環境に設定するため、親環境に同名値があっても選択 profile 名で上書きされます。runtime は起動前に同じ profile に属する残存プロセスを `end_leftovers(profile=name)` で調べます（`terminal/strata_control/runtime.py:697-702, 1056-1074`）。

## 実行時の詳細

サーバーの `main` は `_main` の実行前に `os.environ.get` で一度読み、値を `lastrun.begin` に渡します。読み取り後に環境変数を変更しても、この起動の marker には反映されません。`begin` は Linux で有効なら状態ディレクトリの `last-run-<profile>.json` を読み、前回の marker が残っている場合に終了状態を確認してメッセージを出し、現在の PID・開始 token・開始時刻・profile を記録します。正常な `main` 終了経路では `finally` から `lastrun.end` が呼ばれ、自分の PID の marker を削除します。強制終了等で残った marker は次回起動時に検査されます。marker の読み書き等で例外が起きても `begin` は `None` を返し、起動を止めません（`terminal/serve/server.py:8998-9017`、`terminal/serve/lastrun.py:87-122`）。

前回 marker の PID が消失・再利用されていた場合、`lastrun` は user journal を最大 5 秒で照会し、`systemd-oomd killed` の行があれば OOMD 用の説明、確認できなければ一般的な異常終了の説明を標準出力へ出します。journal を読めない場合も一般説明に進みます（`terminal/serve/lastrun.py:23-28, 58-74, 77-84, 101-108`）。

lifeline は子プロセスを起動した直後に親 server の現在の環境から同名値を読み、PID・role・profile を記録します。unset または空文字なら記録上の profile は `null` 相当です。runtime が後で同名 profile の残存記録を抽出・処理できるよう、この値が記録の区分として使われます（`terminal/serve/lifeline.py:273-305`、`terminal/strata_control/procs.py:203-220, 253-275`）。

## ログと測定値

この変数の設定自体を報告するログはありません。前回終了 marker が見つかった場合の出力は次のいずれかです（`terminal/serve/lastrun.py:23-28, 101-104`）。

- journal に該当記録がある場合: `[strata] Last time, this computer's memory guard (systemd-oomd) ended Strata: it stops a program when memory has been under strain for 20 seconds, and loading a large model can do that. Strata now frees memory before the load and pauses it for a few seconds when memory gets tight. If it happens again: close other programs (a web browser uses a lot of memory) and start again, or start Strata from a text console or over ssh, which the memory guard does not watch.`
- それ以外: `[strata] Last time, Strata did not end normally (the window was closed hard, the power went off, or the computer ran out of memory). Your files are fine and this start goes on as usual. If it stops again while loading, close other programs and start again.`

## 根拠

- `terminal/serve/server.py:8988-9017` — server 起動時の判定、読み取り、marker の終了処理。
- `terminal/serve/lastrun.py:31-47, 58-122` — argv 判定、profile による marker 名、Linux・`STRATA_LASTRUN` 条件、前回終了の確認と出力。
- `terminal/serve/lifeline.py:273-305`、`terminal/strata_control/procs.py:203-223, 253-275` — 子プロセス記録時の読み取りと profile による抽出。
- `terminal/strata_control/runtime.py:697-702, 1040-1074` — 管理起動時の profile 値上書きと profile 単位の残存記録処理。
