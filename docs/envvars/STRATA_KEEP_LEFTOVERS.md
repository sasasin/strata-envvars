# `STRATA_KEEP_LEFTOVERS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata サーバーが engine を起動する直前に行う、前回の実行から残ったプロセスの終了処理を抑止する。環境変数の値が文字列 `"1"` と一致すると、記録済みの残存プロセス確認と、旧版 Strata が残した同一 engine 実行ファイルの孤児確認をどちらも呼び出さない。engine の起動そのものを止める設定ではなく、後続の起動処理は続く（`terminal/serve/server.py:380-402, 823-829`）。

## 値と判定

`end_leftover_engines()` が呼ばれるたびに `os.environ.get("STRATA_KEEP_LEFTOVERS") == "1"` を評価する。値全体の大文字小文字を区別した文字列一致であり、数値変換や真偽値変換はしない。未設定、空文字、`0`、`true`、`True`、`01`、`1anything` などは一致せず、通常の残存プロセス確認へ進む。空白も取り除かれないため、`" 1"` や `"1 "` は一致しない。値 `"1"` の場合に限り確認処理をスキップする（`terminal/serve/server.py:388-394`）。

| 条件 | 未設定 | 確認をスキップする値 | 確認を行う値の例 |
| --- | --- | --- | --- |
| サーバーの実 engine 起動時 | 残存確認を行う | `1` | 空文字、`0`、`true`、`True`、`01`、` 1`、`1 ` |

## 有効になる条件

- `StrataEngine` が lazy ではない起動経路で初期化され、engine の `popen()` より前に `end_leftover_engines(exe)` に到達する必要がある（`terminal/serve/server.py:755-757, 792-794, 823-829`）。
- mock engine にはこの `StrataEngine` の初期化処理がなく、この設定による効果はない。
- `StrataEngine` の再起動も `__init__()` を再実行するため、再起動時にも現在の環境値で判定する（`terminal/serve/server.py:1202-1212`）。
- `terminal/strata_control/runtime.py` の runtime start / stop / cleanup が呼び出す `procs.end_leftovers()` はこの環境変数を参照しない。変数が抑止するのは `server.py` の engine 起動前チェックであり、Strata 全体の残存プロセス処理を一律に無効化するものではない（`terminal/strata_control/runtime.py:701, 844, 868`; `terminal/serve/server.py:388-394`）。
- OS や backend 別の値判定分岐はない。対象は Python サーバーの処理である。

## 実行時の詳細

`StrataEngine.__init__()` は lazy 起動でなければ、engine 子プロセスを起動する直前にこの関数を呼ぶ。値が `"1"` でない場合、まず `strata_control.procs.end_leftovers()` が、親プロセスが失われた記録済み子プロセスを検証して終了させ、次に `end_orphans(exe)` が、起動予定と同じ実行ファイルで `--serve` を実行中かつ親を失った engine を探して終了させる（`terminal/serve/server.py:380-394, 823-829`; `terminal/strata_control/procs.py:269-291, 342-353, 404-455`）。

この環境変数の値は関数呼び出しごとに読み直され、モジュール変数や `static` への保存はない。したがって、同一プロセス内で環境を変えた後の次の engine 起動では新しい値が判定に使われる。CLI 引数、設定ファイル、他の環境変数による優先順位や上書きは実装されていない（`terminal/serve/server.py:388-394`）。

確認を行う場合も、残存とみなした PID は記録された起動時刻・コマンドライン等を照合してからシグナルされる。旧版 engine の孤児判定も、起動予定の実行ファイルとの同一性、`--serve`、親プロセスの状態を確認する。検証できないプロセスは終了対象にしない。確認処理で例外が出た場合は例外型を標準出力へ警告し、engine 起動を続ける。確認後もプロセスが残る場合は警告し、やはり新しい engine の起動は続く（`terminal/strata_control/procs.py:269-291, 305-353, 404-455`; `terminal/serve/server.py:393-402, 823-829`）。

## ログと測定値

値が `"1"` のとき、この関数と二つの確認処理は何も出力せず戻る。通常確認で停止を指示したプロセスが `LEFTOVER_SETTLE_S` 秒後にも残ると、標準出力に次の警告を出す。確認処理自体が例外になった場合は `[strata] could not check for engines left by an earlier run: <例外型>` を出す。どちらの場合も engine start は続く（`terminal/serve/server.py:393-402`）。

> [strata] WARNING: the engine from an earlier run (process …) was told to stop but still holds its memory after … s. Starting the next one now can leave this PC short of RAM and very slow: wait until that process is gone (it is shown by `ps`/Task Manager), or restart the PC if it does not go.

## 根拠

- `terminal/serve/server.py:380-402` — 変数の完全一致判定、呼び出し先、停止中・例外時の出力。
- `terminal/serve/server.py:755-757, 792-829, 1202-1212` — lazy 分岐、engine 起動直前の呼び出し、再起動時の再初期化。
- `terminal/strata_control/procs.py:269-353, 404-455` — 残存プロセス・旧版 engine 孤児の照合と終了処理。
- `terminal/strata_control/runtime.py:701, 844, 868` — runtime 側からの直接呼び出しにはこの変数の判定がないこと。
- `docs/CLOSING.md:47-60` — 起動時の残存処理についての説明。`STRATA_KEEP_LEFTOVERS=1` で二つの engine 起動前チェックを止める点は `server.py` の実装と一致する。
