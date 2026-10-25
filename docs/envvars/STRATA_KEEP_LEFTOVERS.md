# `STRATA_KEEP_LEFTOVERS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

サーバーが推論エンジンを起動する直前に行う、前回の異常終了で残った engine の終了処理を止めます。対象処理は、Strata が記録した孤児プロセスの確認と、旧バージョンが記録を残さず起動した孤児 engine の確認です。`serve/server.py` がこの環境変数を読む箇所は一つです。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 残存 engine の確認・終了を行う |
| 文字列が厳密に `1` | 両方の確認をスキップする |
| 空文字、`0`、`true`、`01`、その他 | 未設定時と同じく確認・終了を行う |

数値変換や trim、大文字小文字変換はありません。Python の `os.environ.get(...) == "1"` による完全一致です（`serve/server.py:125-135`）。

## 有効になる条件

この分岐があるのは `StrataEngine` が engine プロセスを起動する経路です。engine の通常起動と再起動で `StrataEngine` が作られるたび、engine の `popen` の直前に確認関数が呼ばれます（`serve/server.py:966-968,1023-1028`）。リクエスト処理ごとの設定ではありません。

環境変数はサーバープロセスの `os.environ` から読みます。`StrataEngine` に渡された `env` は後続の engine 起動に渡されますが、この判定には使われません（同 `1023-1028`）。したがって `env` 引数だけに `STRATA_KEEP_LEFTOVERS=1` を入れても、このチェックの停止条件にはなりません。

## 実行時の詳細

値が厳密に `1` でなければ `end_leftover_engines()` は `strata_control.procs.end_leftovers()` と `end_orphans(exe)` を順に呼びます。最初の関数は全プロファイルの記録を見て、記録された起動元が既に同じプロセスでなく、PID の開始時刻とコマンドラインも記録と一致するプロセスだけを残存対象にします。Windows 以外では終了要求を送り最大8秒待ち、なお同一プロセスなら強制終了します。Windows では対象を再確認した後 `taskkill /F` を呼びます。PIDだけで対象を決めず、識別できないプロセスは終了せず報告します（`strata_control/procs.py:245-267,281-304,307-318`）。

次の `end_orphans(exe)` は、旧バージョン由来の記録のないプロセスを対象にします。コマンドラインに `--serve` があり、実行ファイルが今回起動する `exe` と同じで、親が生存していないと確認できるものを探します。`psutil` がない場合または `exe` が空の場合、この検索は対象なしで終わります（`strata_control/procs.py:323-360,363-372`）。

終了処理では、終了した・停止中などの結果に応じて `[strata] leftover ...` または `[strata] an engine left behind by an earlier run ...` を標準出力へ出します。確認処理で例外が発生した場合は engine 起動を中止せず、`[strata] could not check for engines left by an earlier run: <例外型>` を標準出力に出します（`serve/server.py:131-137`, `strata_control/procs.py:311-318,363-372`）。

この変数は `strata_control.runtime` の明示的な `runtime stop` / `runtime cleanup` にある `end_leftovers()` 呼び出しを変更しません。それらは `serve/server.py` のガードを通らず呼ばれます（`strata_control/runtime.py:515,610,628`）。

## 根拠

- `serve/server.py:125-137` — 値の完全一致判定、呼び出す二つの確認処理、例外時のログ。
- `serve/server.py:966-968,1023-1028` — 起動・再起動時の呼び出し位置と、別途保持される子 engine 用 `env`。
- `strata_control/procs.py:245-318` — 記録済み残存プロセスの識別、終了、出力。
- `strata_control/procs.py:323-372` — 旧形式の孤児 engine の識別、終了、出力。
- `strata_control/runtime.py:515,610,628` — この環境変数ガードを経由しない runtime の明示的な終了・cleanup 処理。
- `docs/CLOSING.md:45-60` — 残存プロセスを検出する設計説明。挙動の根拠は上記実装を優先した。
