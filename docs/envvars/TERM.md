# `TERM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されなかった。

## 役割

Strata の Python CLI は `TERM` を端末表示の文字選択と、`strata launch` が対話を試みてよいかの補助判定に使います。GPU engine やサーバーの計算設定には使いません。

## 値と判定

| 読み取り経路 | unset / 空文字 | 特別扱いされる値 | その他の値 |
|---|---|---|---|
| `strata monitor` の自動 glyph 選択 | unset は `None`、空文字は `""`。どちらも `dumb` ではない | `dumb` と完全一致すると ASCII を選択 | glyph 選択だけでは値を parse せず、通常の encoding 判定へ進む |
| `strata launch` の画面 glyph 選択 | unset は `None`、空文字は `""`。どちらも `dumb` ではない | `dumb` と完全一致すると Unicode glyph を使わない | `consoleinfo.legacy_console()` の Windows 判定で、`xterm` / `screen` / `tmux` / `vt` のいずれかで始まる値は modern terminal の印とする |
| `strata launch` の `_can_ask()` における `TERM` の寄与 | どちらも偽 | 専用の特別値はない | 空でない値なら寄与は真。大文字小文字を変換せず、数値 parse もしない。ほかの marker でも全体判定は真になり得る |
文字列比較は大文字小文字を区別します。したがって `DUMB` は `dumb` と一致せず、空白付きの値も一致しません。`_can_ask()` は `os.environ.get("TERM")` の真偽を使うため、値が `"0"` や `"false"` でも非空なら真です。`consoleinfo` の prefix 判定も大小文字を区別します。

## 有効になる条件

- `strata monitor` では `MonitorApp` 作成時に `glyphs` が `auto` の場合だけ `TERM=dumb` が ASCII 選択に影響します。明示的な glyph 指定があれば `choose_glyphs()` は先にそれを返し、`TERM` を見ません。`dumb` 以外の値は `sys.stdout.encoding` が文字を encode できるかという判定に委ねられます。
- `strata launch` の初期画面は `Glyphs()` を既定で作り、`unicode_ok()` が `TERM=dumb` を見るため、完全一致時は ASCII glyph になります。さらに `consoleinfo.legacy_console()` の端末判定は Windows (`os.name == "nt"` または `sys.platform == "win32"`) の場合だけ働きます。Windows では `TERM` が上記 prefix で始まると legacy console 判定を避けますが、`WT_SESSION`、`TERM_PROGRAM`、`ConEmuANSI`、`ANSICON` が truthy でも同様です。非 Windows ではこの判定は常に legacy console ではありません。
- `_can_ask()` は `strata launch` の選択肢がまだなく、TTY画面を出せないときの plain-question 経路に関係します。`stdin` が存在し開いていることが必要で、`CI` または `STRATA_NO_PROMPT` が truthy なら `TERM` を含む端末 marker は無視されます。さらに呼び出し側で machine 出力、`--no-tui`、またはモデルカタログ不在なら質問経路へ進みません。通常の TUI 起動判定は `stdin` と `stdout` の両方が TTY かどうかを使い、`TERM` だけでは TUIを強制しません。

## 実行時の詳細

`strata monitor` は `MonitorApp.__init__()` で `os.environ.get("TERM")` を一度読み、`choose_glyphs()` の結果を `self.glyph_choice` に保持します。自動選択では `TERM=dumb` または encoding 未指定なら `ascii`、Windows の legacy console なら `STRATA_GLYPHS` と console style に応じて `ascii` / `solid` / `unicode`、それ以外では `▁█░` を指定 encoding で encode できるかに応じて `ascii` / `unicode` を選びます。環境の実行中変更を読み直すコードはこの選択経路にはありません。根拠: `strata_cli/monitor.py:26-45,138-143`。

`strata launch` の画面では `Glyphs` 生成時に `unicode_ok()` が呼ばれます。`TERM=dumb` なら直ちに `False` となり、カーソル・罫線・矢印・棒・チェック等に ASCII 表現を使います。その他では Windows legacy console の `STRATA_GLYPHS` / console style と stdout encoding の encode 可否が判定されます。`Glyphs` は作成時の結果を保持します。根拠: `strata_cli/launch/widgets.py:43-70`, `strata_cli/launch/app.py:35-44`。

`strata_cli.consoleinfo.legacy_console()` は `TERM` 以外の端末 marker と `STRATA_GLYPHS` の override を先に評価し、その後 Windows のみで `TERM` の prefix を調べます。monitor と launch の表示差を選ぶための判定で、`TERM` を変更する処理やログ出力はありません。根拠: `strata_cli/consoleinfo.py:24-35`。

`strata launch` で対話 screen を開けず、まだ preset / model などの選択もない場合、`_can_ask()` が真なら Strata は plain question 経路を選び、通常は `This window cannot show Strata's screens ... Going on with plain questions.` を表示します。偽なら exit code `2` のエラー `...this is not a terminal...` を返します。`TERM` はこの判断の一つの marker にすぎず、`stdin` の open 状態や `CI` / `STRATA_NO_PROMPT`、呼び出し元の machine / `--no-tui` 条件が優先します。根拠: `strata_cli/launch/cmd.py:511-518,753-778`。

## 根拠

- 全ての本番コード直接参照: `strata_cli/monitor.py:140`, `strata_cli/launch/cmd.py:518`, `strata_cli/launch/widgets.py:44`, `strata_cli/consoleinfo.py:34-35`。他のソース参照はテスト fixture、シグナル名 `TERM`、または文章中の “term” であり、環境値の追加読み取りではありません。
- monitor の TTY 要件・引数経路: `strata_cli/monitor_commands.py:192-221`。ここで非 TTY の interactive monitor はエラーになりますが、`TERM` は TTY 判定の代用ではありません。
