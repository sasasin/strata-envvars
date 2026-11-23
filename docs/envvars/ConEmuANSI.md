# `ConEmuANSI`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の terminal CLI は `ConEmuANSI` を ANSI 機能の切替値として扱わず、Windows の「classic console」かどうかを推定するための環境マーカーとして参照する。`legacy_console()` の除外条件の一つであり、環境から取得した値が空でなければ classic console と判定しない。その判定は monitor TUI と launch UI の glyph 選択や classic console 用スタイル適用に影響する。エンジンの生成・モデル選択・GPU backend の設定を変える処理ではない（`terminal/strata_cli/consoleinfo.py:24-35`, `terminal/strata_cli/monitor.py:26-45,141-145`, `terminal/strata_cli/launch/widgets.py:43-57`）。

## 値と判定

Python の `os.environ.get("ConEmuANSI")` の戻り値を他の端末マーカーと `or` で評価する。値を parse したり、特定の文字列と比較したりはしない。空文字列は falsy なので classic console の除外にならず、空でない任意の値（`0` を含む）は除外になる。大文字小文字、空白、数値としての妥当性は検査しない（`terminal/strata_cli/consoleinfo.py:33-35`）。

| 条件 | 未設定 | 有効になる値（classic console の除外） | 除外にならない値 |
|---|---|---|---|
| `legacy_console()` が `STRATA_GLYPHS` によって先に return しない Windows 実行 | `ConEmuANSI` 単独では除外しない | 空でない値。例: `1`, `0`, `true`, `false`, `anything`, 空白だけ | 未設定、空文字 |

この判定は他の条件より後に評価される。`STRATA_GLYPHS` を trim・小文字化した値が `ascii` / `legacy` / `solid` なら先に `True`、`unicode` なら先に `False` を返す。また Windows 以外では環境マーカー評価前に `False` を返す（`terminal/strata_cli/consoleinfo.py:24-35`）。

## 有効になる条件

- 対象は Strata の Python terminal CLI UI（`monitor` TUI と `launch` UI）の端末種別推定。エンジン側の環境変数ではない（`terminal/strata_cli/monitor_commands.py:49-60,214-230`）。
- `os.name == "nt"` または `sys.platform == "win32"` のときだけ `legacy_console()` は端末 marker を評価する。それ以外の OS では classic console 判定は `False`（`terminal/strata_cli/consoleinfo.py:31-35`）。
- `STRATA_GLYPHS=ascii|legacy|solid` は `ConEmuANSI` より先に classic console 判定を強制し、`STRATA_GLYPHS=unicode` は先に classic 判定を無効にする。大文字小文字と前後空白を正規化する（`terminal/strata_cli/consoleinfo.py:26-30`）。
- monitor の自動 glyph 選択では `--glyphs` が `auto` 以外なら `choose_glyphs()` は `ConEmuANSI` を含む端末判定をせず、その値を返す。ただし monitor 初期化時の classic style 判定は別に `legacy_console()` を呼び出す。`--glyphs auto` の glyph 選択では `TERM=dumb` または出力 encoding 不明なら ASCII を先に選ぶ（`terminal/strata_cli/monitor.py:26-45,139-145`; CLI 引数は `terminal/strata_cli/monitor_commands.py:56-60`）。
- `WT_SESSION`、`TERM_PROGRAM`、`ANSICON` のいずれかに空でない値があれば同じ `or` 条件で classic console を除外する。`TERM` が `xterm` / `screen` / `tmux` / `vt` で始まる場合も除外する（`terminal/strata_cli/consoleinfo.py:33-35`）。

## 実行時の詳細

`legacy_console()` は呼び出すたびに `STRATA_GLYPHS` と端末 marker を参照する。monitor の初期化では glyph 選択と classic style 判定を一度行い、glyph choice と margin をインスタンスに保持する（`terminal/strata_cli/monitor.py:139-145`）。classic style は `consoleinfo._cached` が未設定の初回に判定結果を保存し、以後は同じプロセス内で再利用する。したがって初回 style 判定後に `ConEmuANSI` を変更しても、既に構築された monitor の glyph/style は更新されない（`terminal/strata_cli/consoleinfo.py:158-178`）。

classic console と判定された場合、`classic_style()` は Windows 上で Cascadia Mono が利用可能か確認し、必要なら現在の console window のフォント変更を試みる。切替成功時は full Unicode style、できない場合は solid style を返す。`monitor.py` は glyph choice、bullet、console 幅用 margin と classic console 向け tip にこの結果を使う（`terminal/strata_cli/consoleinfo.py:161-178`, `terminal/strata_cli/monitor.py:143-145,201-208,251-254`）。`launch/widgets.py` では classic 判定かつ full style でない場合に glyphs を ASCII とする（`terminal/strata_cli/launch/widgets.py:43-57`）。

## ログと測定値

`ConEmuANSI` の値に対する専用ログ、警告、エラー、終了経路はない。影響は UI の端末判定と描画用 glyph/style に限られる（`terminal/strata_cli/consoleinfo.py:24-35`, `terminal/strata_cli/monitor.py:201-208,251-254`）。

## 根拠

- `terminal/strata_cli/consoleinfo.py:24-35` — `STRATA_GLYPHS` による先行上書き、OS 条件、`ConEmuANSI` を含む marker 判定。
- `terminal/strata_cli/consoleinfo.py:158-184` — classic style の process-local cache。
- `terminal/strata_cli/monitor.py:26-45,139-145,201-208,251-254` — `--glyphs` 自動選択、初期化時の判定、描画への反映。
- `terminal/strata_cli/launch/widgets.py:43-57` — launch UI の Unicode glyph 条件。
- `terminal/strata_cli/monitor_commands.py:49-60,214-230` — monitor CLI の引数と UI 起動経路。

