# `WT_SESSION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の Python CLI が `WT_SESSION` を読む箇所は二つあります。`strata launch` では、stdin が TTY でなくても Windows Terminal などの入力可能な端末から起動された可能性を示す印として、対話式の確認へ進めるかを判定します。端末描画側では、Windows の従来型コンソールかどうかを見分け、従来型コンソール向けの glyph・フォント調整を避けるために使います。値の内容やセッション ID は利用しません。

## 値と判定

両方とも `os.environ.get("WT_SESSION")` の戻り値を Python の真偽値として使い、文字列の parse や変換はしません。

| `WT_SESSION` | 判定 |
|---|---|
| 未設定 | `None` となり偽 |
| 空文字 (`WT_SESSION=`) | `""` となり偽 |
| 1 文字以上の任意の値 | 真。数値、文字列、大文字小文字、前後の空白を検証しない |

## 有効になる条件

- **`strata launch` の入力確認**: `_can_ask()` は、stdin が存在して開いていることをまず要求し、`CI` または `STRATA_NO_PROMPT` が真なら `False` を返します。その後 `MSYSTEM`、`TERM_PROGRAM`、`TERM`、`WT_SESSION` のいずれかが空でない場合に `True` です。したがって `WT_SESSION` だけでは、stdin がない・閉じている場合や、`CI` / `STRATA_NO_PROMPT` が真の場合を覆しません。呼び出し側はさらに JSON 出力 (`machine`)、`--no-tui`、カタログ不在を先に拒否します。また `--preset` / `--model` など選択肢が指定されていない起動でのみ、この判定がエラー回避に使われます (`strata_cli/launch/cmd.py:511-518,686-697,756-778`)。
- **端末描画**: `legacy_console()` は `STRATA_GLYPHS` を先に調べます。空白除去・小文字化後の `ascii` / `legacy` / `solid` は従来型として `True`、`unicode` は `False` を返し、いずれも `WT_SESSION` の確認に進みません。それ以外では Windows (`os.name == "nt"` または `sys.platform == "win32"`) 以外は `False`。Windows の場合、空でない `WT_SESSION` または `TERM_PROGRAM` / `ConEmuANSI` / `ANSICON` の値、あるいは `TERM` が `xterm` / `screen` / `tmux` / `vt` で始まる場合に従来型コンソールではない (`False`) と判定します (`strata_cli/consoleinfo.py:24-35`)。
- `strata monitor --glyphs` に `unicode` / `braille` / `ascii` が明示された場合は自動判定を通らず、その指定を採用します。`auto` の場合でも `TERM=dumb` または出力 encoding がないと ASCII を選びます (`strata_cli/monitor_commands.py:50-59`, `strata_cli/monitor.py:26-45`)。

## 実行時の詳細

`strata launch` で選択肢がなく TUI も開けない状況では、`WT_SESSION` を含む `_can_ask()` の判定が真なら失敗終了を避け、plain questions の経路に進みます。通常の出力には画面が使えない旨の案内（stdout）を出し、`Start it now? Models can be tens of GB to download. [Y/n]` を表示します。EOF ならエラー文を stderr に出して終了コード 2、`y` / `yes` 以外の回答なら `Nothing was changed.` を stdout に表示して 0 で終了します。JSON 出力、`--no-tui`、カタログ不在、または判定偽の場合は、選択肢を指定するよう促す失敗を返します（終了コード 2。JSON モードでは JSON エラー） (`strata_cli/launch/cmd.py:766-778,842-849`)。この判定は `run_launch()` が到達した時点の環境を読み、値を cache しません。

Windows の monitor / launch ウィジェットでは、空でない `WT_SESSION` によって `legacy_console()` が偽になり、従来型コンソール用のフォント切替・solid 表示を選ばない経路になります。monitor の `auto` glyph 選択は `WT_SESSION` そのものではなく、この端末分類と stdout encoding に従い、Unicode を encode できれば `unicode`、できなければ `ascii` を選びます。従来型でない場合 `MonitorApp` は `classic` を設定せず、従来型用の余白調整も行いません (`strata_cli/monitor.py:26-45,108-145`; `strata_cli/launch/widgets.py:43-57`)。

`legacy_console()` 自体は呼び出しごとに環境を読み直します。一方、従来型と判定された場合に使われる `classic_style()` は最初の結果をモジュール変数 `_cached` に保存します。そのため、最初の `classic_style()` 呼び出し後に環境変数を変更しても、同プロセス内の同関数の結果は再評価されません (`strata_cli/consoleinfo.py:158-178`)。Strata が `WT_SESSION` を子プロセスへ設定・転送する処理は確認できません。

## 根拠

- `strata_cli/launch/cmd.py:511-518` — `_can_ask()` の `WT_SESSION` を含む環境値の真偽判定と、先行する stdin / `CI` / `STRATA_NO_PROMPT` 判定。
- `strata_cli/launch/cmd.py:756-778,842-849` — CLI 条件、質問経路、出力・終了経路。
- `strata_cli/consoleinfo.py:24-35` — `STRATA_GLYPHS` の優先、Windows 条件、および他の端末マーカーと合わせた `WT_SESSION` 判定。
- `strata_cli/consoleinfo.py:158-178` — `classic_style()` の一度だけの cache。
- `strata_cli/monitor.py:26-45,108-145`、`strata_cli/launch/widgets.py:43-57` — 端末分類から glyph 選択・表示設定への利用。
- `strata_cli/monitor_commands.py:50-59` — monitor の CLI glyph 選択肢。

`tests/terminal/test_monitor_classic.py:71-80` は Windows Terminal を模したテスト環境を用意していますが、本番動作の根拠は上記の実装箇所です。`docs/DETAILS.md` と `docs/TROUBLESHOOTING.md` には `WT_SESSION` の説明は見つかりませんでした。
