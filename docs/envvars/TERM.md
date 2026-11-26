# `TERM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata の Python ターミナル UI が表示色・図形文字を選ぶ際の手掛かり、および `strata launch` が入力可能な端末らしい環境かを判断する手掛かりとして読む。値をエンジンやサーバーへ渡す処理は確認できない。使う場所はセットアップのモデル選択表示、`strata monitor` / launch monitor、`strata launch` の非 TUI 経路である（`terminal/setup.py:1007-1018,11993-12018`; `terminal/strata_cli/monitor.py:26-45,139-144`; `terminal/strata_cli/launch/cmd.py:570-584`）。

## 値と判定

| 読み取り箇所 | unset・空文字 | 有効になる値（例） | 判定に合わない値（例） |
|---|---|---|---|
| `terminal/setup.py` の `menu_colour` | 未設定は `""` を既定にし、`dumb` ではない。空文字も色を止めない。 | 大文字小文字を無視して `dumb` と一致すると ANSI 色を止める（`DUMB` も一致）。 | `xterm`、`DUMB ` は `dumb` 判定にならない。前後空白は除去しない。 |
| `monitor.py` の glyph 選択 | `None` / 空文字は `term == "dumb"` に一致しない。空文字はこの判定だけでは特別扱いしない。 | `--glyphs auto` のとき、値が小文字の `dumb` と完全一致すると ASCII を選ぶ。 | `DUMB`、`dumb ` は一致しない。`--glyphs` が `auto` 以外なら `TERM` 判定より CLI 指定が優先される。 |
| `consoleinfo.py` の Windows classic console 判定 | 未設定・空文字は他の条件がなければ classic 判定を妨げない。 | Windows 上で `xterm`、`screen`、`tmux`、`vt` のいずれかで始まる文字列は classic 判定を抑止する。比較は大文字小文字を区別する。 | `DUMB`、`dumb`、`ansi` は prefix に一致しない。Linux/macOS ではこの TERM 判定に到達する前に `False` を返す。 |
| `launch.cmd._can_ask` | unset / 空文字は偽。 | **任意の非空文字列**（`dumb`、`0`、空白のみを含む値も含む）は `bool(...)` を真にする。 | TERM 単独では未設定・空文字が真にならない。これは環境検出の一要素で、ほかのゲートも必要。 |

これらは設定値の数値変換ではなく、文字列比較・prefix 比較・Python の真偽判定である。したがって `0` や `false` を共通の無効値として扱う規則はない（`terminal/setup.py:1012`; `terminal/strata_cli/monitor.py:26-45`; `terminal/strata_cli/consoleinfo.py:31-35`; `terminal/strata_cli/launch/cmd.py:580,583`）。

## 有効になる条件

- セットアップの `menu_colour` は stdout が TTY で、`NO_COLOR` が**設定されておらず**、TERM が case-insensitive な `dumb` でなく、Windows なら仮想端末エスケープが有効な場合だけ色コードを返す。`NO_COLOR` は空文字でも色を止める。Windows の VT 設定に失敗した場合も色なしになる（`terminal/setup.py:1007-1018,1024-1036`）。この関数はモデル選択画面の family / model 名に使われる（`terminal/setup.py:11993-12018,12055-12073`）。
- Monitor の `TERM=dumb` による ASCII 選択は `--glyphs auto` のときだけ。`--glyphs unicode|braille|ascii` の明示指定が先に返る（`terminal/strata_cli/monitor_commands.py:49-60`; `terminal/strata_cli/monitor.py:26-45`）。`dumb` でなくても、出力 encoding が空または Unicode 図形を encode できなければ ASCII になる。Windows classic console では `STRATA_GLYPHS` やコンソールの表示モードによる分岐もある（`terminal/strata_cli/monitor.py:31-45`; `terminal/strata_cli/consoleinfo.py:24-35`）。
- launch 画面の `unicode_ok()` は TERM が小文字の `dumb` と完全一致すれば Unicode を不許可にし、ASCII 記号を選ぶ。TERM がそれ以外でも、Windows classic console の判定・`STRATA_GLYPHS`・encoding 判定で ASCII に fallback し得る（`terminal/strata_cli/launch/widgets.py:43-57`; `terminal/strata_cli/consoleinfo.py:24-35`）。
- `strata launch` では TERM の非空値が質問可能性のサインの一つになるが、`sys.stdin` が閉じている、`CI` または `STRATA_NO_PROMPT` が真、あるいは stdin が null device の場合には質問しない。`MSYSTEM` / `TERM_PROGRAM` / `WT_SESSION` も同じ OR 条件の候補であり、TERM が空でも他のいずれかで条件を満たせる（`terminal/strata_cli/launch/cmd.py:570-584`; `terminal/strata_cli/noinput.py:16-24`）。
- この質問判定が使われるのは、選択肢が指定されず、TUI に入れず、`--plan` でもない場合。`machine` 実行、`--no-tui`、カタログ不在も先に質問不可として扱う。質問可能なら画面を開かず平文の質問へ進み、「画面を表示できない」案内を出す（`terminal/strata_cli/launch/cmd.py:849-871`）。

## 実行時の詳細

環境から読むのは各 Python 関数の呼び出し時で、TERM 用の static cache はない。セットアップは `menu_colour` を表示行ごとに呼び、monitor は `MonitorApp` の初期化時に `TERM` を渡して `glyph_choice` に保存するため、その monitor インスタンスでは後から環境を変えても glyph 選択は再計算されない。launch の `unicode_ok`, `legacy_console`, `_can_ask` は呼び出し時に環境を参照する（`terminal/setup.py:1007-1018,11997,12069`; `terminal/strata_cli/monitor.py:26-45,108-143`; `terminal/strata_cli/launch/widgets.py:43-57`; `terminal/strata_cli/launch/cmd.py:570-584`）。

monitor の `--once` / status 出力は TUI の `MonitorApp` を作らないため、この `TERM` による glyph 判定は通らない。通常の monitor TUI は `--glyphs` を引数から `MonitorApp` または `LaunchMonitor` に渡す（`terminal/strata_cli/monitor_commands.py:52-60,209-229`）。TERM の子プロセスへの転送や値の書き換えは、これらの読み取り経路では行わない。

## ログと測定値

TERM に関する専用ログ、警告、エラー、終了コードの分岐はない。観測できる差は、セットアップ表示に ANSI 色コードを含めるか、画面内で Unicode または ASCII の glyph を使うかである。`strata launch` の非 TUI 経路で他の質問可否条件を満たさない場合は既存の失敗文 `\`strata launch\` with no choices opens screens, and this is not a terminal (or --no-tui was given). Name what to start: ...` を出し、終了コード 2 を返す。TERM が非空でも `CI` 等のゲートが優先される（`terminal/strata_cli/launch/cmd.py:575-584,859-866`）。

## 根拠

- `terminal/setup.py:1007-1018,1024-1036,11993-12018,12055-12073` — 色判定、Windows VT 条件、呼び出し箇所。
- `terminal/strata_cli/monitor.py:26-45,108-143` — monitor の TERM 判定と初期化時の保存。
- `terminal/strata_cli/monitor_commands.py:49-60,209-229` — CLI glyph 指定と monitor 起動経路。
- `terminal/strata_cli/consoleinfo.py:24-35` — Windows classic console の TERM prefix 判定。
- `terminal/strata_cli/launch/widgets.py:43-57` — launch 画面の `dumb` 判定と文字種 fallback。
- `terminal/strata_cli/launch/cmd.py:559-584,849-871` — launch の環境ヒューリスティックと利用条件・結果。
- `terminal/strata_cli/noinput.py:16-24` — stdin が null device かどうかの追加判定。
