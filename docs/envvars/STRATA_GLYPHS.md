# `STRATA_GLYPHS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

terminal UI の glyph 表示を選ぶ補助設定である。`terminal/strata_cli/consoleinfo.py` が classic console の自動判定を上書きし、`monitor.py` と `launch/widgets.py` が Overview や launch 画面で ASCII・Unicode・solid の描画を選ぶ。GPU 計算、モデル選択、サーバー設定を変える読み取り経路は見つからなかった。環境変数を読む本番コードは `terminal/strata_cli/consoleinfo.py`、`monitor.py`、`launch/widgets.py` に限られる（`consoleinfo.py:24-35, 158-178`; `monitor.py:26-45`; `launch/widgets.py:43-57`）。

## 値と判定

各箇所は `os.environ.get("STRATA_GLYPHS", "").strip().lower()` で読み、前後の空白を除いて小文字化する。値全体を集合と比較し、数値変換や先頭文字判定はしない。未設定と空文字はどちらも `""` となり、認識済み指定ではなく自動判定へ進む。たとえば ` ASCII ` は `ascii` として認識され、`1`、`true`、`0anything`、`auto`、その他の未知値は指定としては無効で自動判定へ進む（`consoleinfo.py:26-35, 167`; `monitor.py:34-40`; `launch/widgets.py:48-50`）。

| 条件 | unset / 空文字 | 認識される値 | 未知値の例 |
|---|---|---|---|
| `consoleinfo.legacy_console()` | OS・端末情報で判定 | `ascii` / `legacy` / `solid` は classic 判定を強制、`unicode` は classic 判定を解除 | OS・端末情報で判定 |
| monitor の `--glyphs auto`（stdout が `dumb` でなく encoding あり） | classic 判定なら font/style に応じて `unicode` または `solid`、それ以外は encoding 検査後 `unicode` または `ascii` | classic 判定時 `ascii` / `legacy` は `ascii`、`solid` は `solid`。`unicode` は classic 判定を解除し、encoding 検査へ進む | 上記の自動判定 |
| launch の `Glyphs()` | 端末種別・style・stdout encoding で Unicode 可否を判定 | classic 判定時 `ascii` / `legacy` は ASCII、`solid` は `classic_style()` が full でないため ASCII、`unicode` は classic 判定を解除して encoding 検査へ進む | 上記の自動判定 |

monitor では `--glyphs` が `auto` 以外なら `choose_glyphs()` が最初にその引数を返すため、Overview 等の glyph 選択では環境変数より CLI が優先する。`--glyphs` の選択肢は `auto`、`unicode`、`braille`、`ascii`（`monitor_commands.py:56-60`; `monitor.py:26-29`）。ただし `MonitorApp` は別途 classic style を環境変数から判定し（`monitor.py:141-144`）、`LaunchMonitor` の Connect view 用 `Glyphs()` も環境変数を読む（`launch/monitor_ext.py:39-49`）。

## 有効になる条件

- monitor の環境変数による glyph 自動選択は、対話 TUI を起動する経路で使われる。`--once` や JSON 出力は `MonitorApp` / `LaunchMonitor` を起動せずに return するため、この変数による選択は行われない（`monitor_commands.py:203-224`）。
- `--glyphs` を明示した monitor では、Overview など共通 view の選択はその値が優先される。`--glyphs auto` のときだけ環境変数による自動判定が使われる（`monitor.py:26-45`）。
- `TERM=dumb` または stdout encoding が未設定なら、monitor の `choose_glyphs()` は `STRATA_GLYPHS` の指定を見る前に `ascii` を返す（`monitor.py:31-32`）。launch 側は `TERM=dumb` なら Unicode を不可とし、classic 判定でなければ stdout encoding で描画文字列を encode できるか確認する（`launch/widgets.py:43-57`）。
- `ascii` / `legacy` / `solid` は classic 判定を強制するため、Windows 以外でも legacy 分岐へ入る。Windows 以外では font 操作は行われず、classic style は Cascadia Mono 切替なしの solid になる（`consoleinfo.py:24-35, 161-178`; `consoleinfo.py:118-140`; `consoleinfo.py:150-155`）。
- unset、空文字、未知値の場合、Windows 以外は通常 legacy 判定にならない。Windows では `WT_SESSION`、`TERM_PROGRAM`、`ConEmuANSI`、`ANSICON`、および `TERM` の `xterm` / `screen` / `tmux` / `vt` 始まりの値が legacy 判定を解除する（`consoleinfo.py:31-35`）。
- `classic_style()` は classic 判定時、`ascii` / `legacy` / `solid` のいずれかが明示されていれば font 切替を試さない。それ以外の classic 判定では Windows に限り Cascadia Mono の既存 font を確認し、未導入なら導入状態を調べて切替を試す（`consoleinfo.py:161-178`）。

## 実行時の詳細

`legacy_console()` は呼び出しごとに環境変数と端末情報を読む。monitor は `MonitorApp` の初期化時に `choose_glyphs()` の結果を `glyph_choice` に保存し、以後 Overview と detail view の描画へ渡す。`solid` は Overview では固形ブロック表示、その他のテキスト view では ASCII に置き換わる（`monitor.py:108-144, 182-185, 201-230`; `overview.py:233-263, 342-353`）。

`classic_style()` はモジュール変数 `_cached` に初回結果を保存し、同一プロセス内の後続呼び出しでは環境変数を再評価しない。テスト用 `forget_style()` だけが cache を消す。本番コードからの呼び出し後に環境を変更しても、この cache を使う style 判定は更新されない。一方 `legacy_console()` と `launch/widgets.py` の個別判定自体には同様の cache はない。launch 画面は `Glyphs()` の生成時に判定し、得た glyph 文字を画面部品へ渡す（`consoleinfo.py:158-184`; `launch/widgets.py:43-72`; `launch/app.py:694-714`）。

## ログと測定値

この変数の値を理由として出す stdout / stderr のログ、警告、終了コード変更はない。観測できる結果は画面の glyph の違いである。classic style では UI に `For the full look, use Windows Terminal (built into Windows 11)` の案内が出るが、環境変数値の診断ログではない（`consoleinfo.py:21, 143-155`; `monitor.py:253-254`）。

## 根拠

- `terminal/strata_cli/consoleinfo.py:24-35, 158-184` — 環境値の正規化、classic console 判定、style cache。
- `terminal/strata_cli/monitor.py:26-45, 108-144, 182-230` — CLI 引数との優先順位、初期化時の選択、描画への伝播。
- `terminal/strata_cli/launch/widgets.py:43-72` — launch UI の Unicode 可否と glyph 対応表。
- `terminal/strata_cli/monitor_commands.py:49-60, 203-230` — CLI option と対話 monitor 起動条件。
- `terminal/strata_cli/overview.py:233-269, 342-353` — Overview の ASCII / Unicode / solid 描画。
- `terminal/strata_cli/launch/monitor_ext.py:39-49`; `terminal/strata_cli/launch/app.py:694-714` — launch 起動時と Connect view の `Glyphs()` 作成。
- `docs/TERMINAL_LAUNCH.md:171-173` は Windows Terminal・Linux・macOS は「never touched」と記すが、現行ソースでは `ascii` / `legacy` / `solid` が OS 判定より先に classic 判定を強制する。したがってこれらの値は Windows 以外でも表示を変えうる。挙動の根拠は文書ではなく上記のソース分岐とする。
