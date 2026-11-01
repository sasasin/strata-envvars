# STRATA_GLYPHS

調査対象: Strata main の HEAD c62d5e3a15b40ea51c96aae9e8d36928965f53ab（2026-11-01 時点）。

## 役割

Strata の端末 UI が使う文字セットと、コンソールを「classic」表示として扱うかを選ぶ補助設定です。読み取り箇所は strata_cli/consoleinfo.py、strata_cli/monitor.py、strata_cli/launch/widgets.py にあります。いずれも Python の端末表示コードで、モデル実行やサーバーの計算設定を変更しません。

モニターの自動 glyph 選択では ascii / legacy が ASCII 表示、solid が Overview の solid 表示を選びます。起動画面の widget は Unicode glyph の使用可否を判定します。legacy_console() はこれらの値により、実 OS や端末検出にかかわらず classic console と判定することがあります。

## 値と判定

値は os.environ.get(..., "").strip().lower() で前後の空白を除き、小文字化して比較します。数値変換はありません。未設定、空文字、または認識されない文字列に対するエラーや警告はなく、用途ごとの通常判定に進みます。

| 正規化後の値 | legacy_console() | モニターの --glyphs auto | 起動画面 widget |
|---|---|---|---|
| ascii, legacy | True（classic 扱いを強制） | ASCII | Unicode を使わない |
| solid | True（classic 扱いを強制） | solid（Overview。詳細ビューでは ASCII に置換） | classic_style() が full でなければ Unicode を使わない。通常、この値は font 切替を抑止して solid mode にする |
| unicode | False（classic 扱いを解除） | 以降は stdout encoding を検査し、glyph を encode できれば Unicode、できなければ ASCII | classic console 条件を通さず stdout encoding を検査 |
| 未設定、空文字、その他 | OS・端末環境による判定 | classic 判定と font 状態に基づく自動選択 | classic 判定、font 状態、stdout encoding による自動選択 |

大文字小文字と前後空白は区別されません（例: ASCII は ascii と同じ）。文字列全体を正規化してから比較するため、ascii! や unicode extra は認識値ではありません。空文字は「値が設定された特別なモード」ではなく、空の既定値と同様に扱われます。

モニターでは TERM=dumb または stdout encoding が falsy の場合、環境変数による glyph 判定より先に ASCII になります。--glyphs に auto 以外（CLI の選択肢は unicode, braille, ascii）を指定すると choose_glyphs() はその値をそのまま採用し、glyph の選択に STRATA_GLYPHS を使いません。ただし環境変数は別途 legacy_console() や classic_style() にも読まれ、classic 扱い、余白、bullet、font 判定には影響し得ます。

## 有効になる条件

- legacy_console() は ascii, legacy, solid を見つけると True、unicode を見つけると False を返します。その他の値では Windows（os.name == "nt" または sys.platform == "win32"）かを調べ、Windows の場合は WT_SESSION、TERM_PROGRAM、ConEmuANSI、ANSICON の truthy な値や TERM が xterm / screen / tmux / vt で始まることを classic console でない条件として判定します（strata_cli/consoleinfo.py:24-35）。このため ascii / legacy / solid は Windows 以外でも classic 扱いを強制できます。
- classic_style() は ascii, legacy, solid を「強制値」として扱い、強制値があると Cascadia Mono への切替を行いません。未設定・空・未知値、または unicode で classic 判定が true になった場合は、Windows 上で既に Cascadia Mono が使われているかを確認し、インストール済みなら切替を試します（strata_cli/consoleinfo.py:161-178）。
- 起動画面の Unicode widget は TERM=dumb なら常に ASCII 系 glyph です。それ以外では classic 判定時に ascii / legacy を拒否し、さらに classic_style()["mode"] != "full" なら Unicode を使いません。最後に stdout encoding が必要文字を encode できるか確認します（strata_cli/launch/widgets.py:43-57）。
- 環境変数に関連するログ、警告、エラー終了経路は見つかりません。ここでの効果は端末への表示文字と classic console 用の表示調整です。

## 実行時の詳細

strata monitor の TUI は MonitorApp の初期化時に choose_glyphs() を呼び、結果を self.glyph_choice に保持します。Overview にはこの値を渡し、他のビューでは solid を ASCII に変換してから renderer に渡します（strata_cli/monitor.py:26-45,138-143,181-184,198-228）。起動引数 --glyphs の既定値は auto です（strata_cli/monitor_commands.py:49-60,214-229）。--once / status はこの TUI 初期化を通らず、snapshot を通常の render_view() で表示する経路です（同 monitor_commands.py:203-213）。

strata launch の対話画面は run_tui() で Glyphs() を生成します。引数なしの Glyphs() は unicode_ok() を実行し、結果を cursor、rule、矢印、bar、check mark などの表示文字へ展開します（strata_cli/launch/app.py:442-461、strata_cli/launch/widgets.py:43-72）。起動後に LaunchMonitor も MonitorApp の初期化を経てから別の Glyphs() を生成します（strata_cli/launch/monitor_ext.py:39-49）。

legacy_console() の環境値判定自体は関数呼び出し時に行われます。一方 classic_style() は初回の結果をモジュール変数 _cached に保存し、以後の呼び出しでは再判定しません（strata_cli/consoleinfo.py:158-178）。Monitor の glyph 選択および起動画面の Glyphs も生成時に保持されます。そのため、プロセス実行中に環境値を変更しても、すでに選択・cache された表示状態は自動更新されません。子プロセスへの明示的な転送箇所は見つかりません。

## 根拠

- 直接読み取りと正規化、classic 判定: strata_cli/consoleinfo.py:24-35,161-178。
- Monitor TUI の選択、CLI 引数、描画への伝播: strata_cli/monitor.py:26-45,138-143,181-228; strata_cli/monitor_commands.py:49-60,203-229。
- 起動画面 widget の選択と表示文字: strata_cli/launch/widgets.py:43-72; 生成元 strata_cli/launch/app.py:442-461。
- strata launch 後の monitor: strata_cli/launch/monitor_ext.py:39-49。
- docs/TERMINAL_LAUNCH.md:166-168 は STRATA_GLYPHS=unicode|ascii|solid が見た目を強制すると説明しています。実装では legacy も認識し、ascii / legacy / solid と unicode で classic 判定や font 切替への影響が異なります。また環境値より TERM=dumb・encoding 判定や明示 --glyphs が優先される経路があります。現行コードでは環境変数だけで全 UI の glyph を一律に強制するわけではありません。
