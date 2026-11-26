# `TERM_PROGRAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata 同梱の Python CLI で、ターミナル種別の目印として設定有無を参照する。Windows のクラシックコンソール向け表示を選ぶ判定と、`strata launch` が画面を開けない端末でも質問を続けられるかの判定に使う。値の内容からアプリ名を判別する処理ではない。実行時の読み取りは `terminal/strata_cli/consoleinfo.py:24-35` と `terminal/strata_cli/launch/cmd.py:570-584`。

## 値と判定

両方の実行箇所とも `os.environ.get("TERM_PROGRAM")` の返り値を Python の真偽値として使う。未設定なら `None`、空文字なら偽、空でない文字列なら真として扱う。文字列の比較、大小文字変換、空白除去、値の妥当性検査はしないため、例えば `vscode` 以外の任意の非空値や空白だけの値も「設定あり」になる。数値変換や数値境界はない。`terminal/strata_cli/consoleinfo.py:33-35`、`terminal/strata_cli/launch/cmd.py:580,583`。

| 実行箇所・条件 | unset / 空文字 | 非空値 | 優先・併用条件 |
|---|---|---|---|
| `consoleinfo.legacy_console()`（Windows 判定まで到達） | この変数ではクラシック判定を妨げない | クラシックコンソールではないと判定 | 先に `STRATA_GLYPHS=ascii|legacy|solid` ならクラシックを強制し、`STRATA_GLYPHS=unicode` ならクラシックでないと強制する。これら以外は Windows 以外で常にクラシックでない。Windows では `WT_SESSION`、`ConEmuANSI`、`ANSICON`、指定接頭辞で始まる `TERM` もクラシック判定を妨げる。 |
| `launch.cmd._can_ask()` | この変数単独では端末の目印にならない | 端末の目印の一つになる | `MSYSTEM`、`TERM`、`WT_SESSION` のいずれかが非空でも同じ判定になる。先に標準入力・`CI`・`STRATA_NO_PROMPT` を検査し、利用可能な `strata_cli.noinput` がある場合はキーボード不在も検査する。 |

根拠: `terminal/strata_cli/consoleinfo.py:26-35`、`terminal/strata_cli/launch/cmd.py:570-584`。

## 有効になる条件

- 表示判定では Windows（`os.name == "nt"` または `sys.platform == "win32"`）で、かつ `STRATA_GLYPHS` による早期の強制指定がない場合だけ `TERM_PROGRAM` が `legacy_console()` の結果に影響する。非 Windows ではこの関数は `False` を返す。`terminal/strata_cli/consoleinfo.py:24-35`。
- `legacy_console()` が偽になると、CLI モニターはクラシックコンソール専用のスタイル情報を使わず、通常の Unicode 描画選択を行う。ウィジェットもクラシック向けフォント条件で Unicode を抑制しない。`terminal/strata_cli/monitor.py:26-45,141-144`、`terminal/strata_cli/launch/widgets.py:43-57`。
- 質問可否の判定では `strata launch` に開始選択がなく、対話 TUI を使えない状態で、`--plan` でもない場合に `_can_ask()` が呼ばれる。`--no-tui`、`--output json`、カタログ不在は環境変数に関係なく質問経路を止める。`CI` または `STRATA_NO_PROMPT` が非空、標準入力がない／閉じている、もしくは利用可能な `strata_cli.noinput.stdin_is_no_keyboard()` が真の場合も `_can_ask()` は偽になる。`terminal/strata_cli/launch/cmd.py:570-584,849-866`。
- stdin と stdout がともに TTY で `--no-tui`、JSON 出力、plan 実行でない場合は通常の対話経路になるため、この変数による `_can_ask()` 判定は使われない。開始選択（例: `--model` / `--preset`）を明示した場合も、開始選択がない場合の質問可否分岐の対象外。`terminal/strata_cli/launch/cmd.py:849-862`。

## 実行時の詳細

`consoleinfo.legacy_console()` は呼び出すたびに環境を読み直し、`TERM_PROGRAM` 自体をキャッシュしない。一方 `classic_style()` は最初の呼び出しで得た `legacy_console()` の結果を含むスタイル辞書をモジュール変数 `_cached` に保存し、その後は返り値を再利用する。したがって、プロセス内で環境を変更した場合でも、`legacy_console()` の直接結果には反映されるが、既に `classic_style()` が初期化されていればそのスタイル結果は更新されない。`terminal/strata_cli/consoleinfo.py:24-35,158-178`。

`launch.cmd._can_ask()` は対象分岐で都度呼ばれ、その呼び出し時点の `os.environ` を参照する。プロセス起動後に値を変えた場合も、呼び出し前なら判定に反映される。子プロセスへの設定転送・書換えはこの読み取り箇所にはない。環境変数は通常の TTY 対話経路、明示的な開始選択、`--plan` には適用されない。`terminal/strata_cli/launch/cmd.py:570-584,849-866`。

## ログと測定値

`TERM_PROGRAM` の値そのものを出力するログはない。表示判定は描画スタイルに反映される。`strata launch` で開始選択がなく質問可能な非 TTY 端末と判定されると、画面パッケージがないケースを除き `no_screens_words()` の案内を表示して通常行で続行し、`Start it now? Models can be tens of GB to download. [Y/n] ` を尋ねる。質問可の判定に失敗すると stderr に ``strata: `strata launch` with no choices opens screens, and this is not a terminal (or --no-tui was given). Name what to start: --preset NAME, or --model NAME (strata launch --help has examples; --plan shows what would happen without changing anything).`` を出し、終了コード `2` を返す。`--output json` では同じ失敗を JSON の `error` として stdout に出す。回答入力で EOF になった場合は別メッセージを返して終了コード `2` となる。`terminal/strata_cli/launch/cmd.py:759-764,854-866,937-944`。

性能測定値は該当しない。

## 根拠

- `terminal/strata_cli/consoleinfo.py:24-35` — Windows のクラシックコンソール判定と環境変数の優先条件。
- `terminal/strata_cli/consoleinfo.py:158-178` — クラシックスタイルの初回計算とキャッシュ。
- `terminal/strata_cli/monitor.py:26-45,141-144`、`terminal/strata_cli/launch/widgets.py:43-57` — 端末判定後の描画選択。
- `terminal/strata_cli/launch/cmd.py:570-584,849-866,937-944` — 質問可能な環境の判定、通常行での確認、および失敗時の分岐。
- `terminal/tests/terminal/conftest.py:11-16` と `terminal/tests/terminal/test_monitor_classic.py:71-83`、`terminal/tests/terminal/test_monitor_classic.py:75-79` — テスト環境の表示モード調整と端末判定テスト用に環境を組み替える箇所。本番動作の根拠にはしていない。
