# `TERM_PROGRAM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はなかった。

## 役割

Strata の Python CLI が端末環境を推定するために参照する。`strata launch` では、通常の対話画面を表示できない実行でも人が入力できる可能性を判定し、質問を伴うプレーンな起動経路を選ぶ材料になる。Windows のクラシックコンソール判定では、Windows Terminal や VS Code など別の端末であることを示す条件の一つとなり、古いコンソール向け描画を避ける。

この変数を読む本番コードは `strata_cli/launch/cmd.py` と `strata_cli/consoleinfo.py` の2か所。候補一覧に名前があることに加え、どちらも実際に `os.environ` から値を参照している。`tests/terminal/test_monitor_classic.py:75` にもテスト用環境辞書から除外する参照があるが、挙動の根拠にはしていない。候補一覧の記載は `docs/envvars/000_envvers.md:1670`。

## 値と判定

どちらの読み取り箇所も値を parse せず、文字列の truthiness（空でないか）だけを使う。値が `1` か、端末名が何か、大文字小文字がどうかは検査しない。

| 値 | `strata launch` の `_can_ask()` | `legacy_console()`（Windows のみ） |
|---|---|---|
| 未設定 | この条件では false | この条件では false（よって他の拒否条件がなければクラシックコンソール扱い） |
| 空文字 | false | false（他の拒否条件がなければクラシックコンソール扱い） |
| 任意の非空文字列（例: `vscode`, `Apple_Terminal`, `0`, `false`） | true | true（クラシックコンソールではないと判定） |

`_can_ask()` では `CI` または `STRATA_NO_PROMPT` が非空なら先に false を返し、`TERM_PROGRAM` は `MSYSTEM`, `TERM`, `WT_SESSION` と並ぶ OR 条件の一つである。ほかのいずれかが非空なら `TERM_PROGRAM` の値を個別に区別しない。標準入力が `None` または閉じている場合も先に false になる（`strata_cli/launch/cmd.py:511-518`）。

## 有効になる条件

- **`strata launch`**: 標準入力が開いており、`CI` と `STRATA_NO_PROMPT` が空または未設定であることが必要。さらに実際に `_can_ask()` の結果が使われるのは、選択肢の指定がなく、対話画面も使えない場合である。`--output json` 等の machine 実行、`--no-tui`、カタログ不在はこのフォールバックより優先して失敗経路になる。通常の TTY 上で選択肢がある場合の TUI 選択を `TERM_PROGRAM` は変えない（`strata_cli/launch/cmd.py:753-778`）。
- **Windows の描画判定**: `legacy_console()` は `STRATA_GLYPHS` が `ascii` / `legacy` / `solid` なら先にクラシック描画を強制し、`unicode` なら先にクラシック描画を無効化する。どちらにも該当しない場合、Windows 以外では直ちに false を返す。Windows では `WT_SESSION`, `TERM_PROGRAM`, `ConEmuANSI`, `ANSICON` のいずれかが非空、または `TERM` が `xterm` / `screen` / `tmux` / `vt` のいずれかで始まる場合にクラシックコンソールではないと判定する（`strata_cli/consoleinfo.py:24-35`）。したがって `STRATA_GLYPHS` の明示値が `TERM_PROGRAM` より優先する。
- 描画判定の結果はモニターの glyph 選択と classic style 適用、起動画面の glyph 選択に使われる（`strata_cli/monitor.py:26-45,138-143`; `strata_cli/launch/widgets.py:43-57`）。`classic_style()` は最初の計算結果をモジュール内 `_cached` に保持するため、その後 `TERM_PROGRAM` を変更してもこの style 結果は再計算されない。一方 `legacy_console()` 自体は環境を呼び出しごとに参照する（`strata_cli/consoleinfo.py:158-178`）。

## 実行時の詳細

`strata launch` が選択肢なしで TUI も使えないとき、`_can_ask()` が true なら `plain_questions` 経路に入り、「This window cannot show Strata's screens ... Going on with plain questions.」を表示する（画面用パッケージがない場合はその説明を優先）。続けるかを標準入力で尋ね、空入力、`y`、`yes` は続行、それ以外は「Nothing was changed.」を出して終了コード 0 になる。EOF は `fail(...)` により「There is nobody to answer. ...」を表示して終了コード 2。`TERM_PROGRAM` 単独では質問を開始せず、上記の他条件と CLI 状態も満たす必要がある（`strata_cli/launch/cmd.py:765-778,842-849`）。

Windows の自動描画判定では、非空の `TERM_PROGRAM` によって `legacy_console()` が false になり、`classic_style()` は `{"mode": "none", ...}` を返す。モニターはクラシック専用の glyph/style を使わず、起動画面の `unicode_ok()` もクラシックコンソール専用の制限を適用しない。ただし文字コードや `TERM=dumb` など別条件は独立して評価される。`STRATA_GLYPHS` の強制設定がある場合はその分岐が先に適用される（`strata_cli/consoleinfo.py:24-35,143-178`; `strata_cli/monitor.py:26-45`; `strata_cli/launch/widgets.py:43-57`）。

この変数を理由にした専用の警告・ログ・終了経路はない。起動時に値を保存する共通 cache はなく、`_can_ask()` と `legacy_console()` は呼ばれた時点で環境を読む。例外は前述の `classic_style()` の計算結果 cache である。Strata の資料でこの環境変数固有の追加挙動や測定値は確認できなかった。

## 根拠

- `strata_cli/launch/cmd.py:511-518` — 開いた標準入力、`CI` / `STRATA_NO_PROMPT` の拒否、`TERM_PROGRAM` を含む端末環境の truthiness 判定。
- `strata_cli/launch/cmd.py:753-778,842-849` — CLI/TUI 条件、plain question 経路、入力結果と観測できる出力・終了コード。
- `strata_cli/consoleinfo.py:24-35` — `STRATA_GLYPHS` と OS 判定の優先順、`TERM_PROGRAM` を含むクラシックコンソール判定。
- `strata_cli/consoleinfo.py:143-178` — 描画 style の結果と `classic_style()` の cache。
- `strata_cli/monitor.py:26-45,138-143`; `strata_cli/launch/widgets.py:43-57` — 判定結果が反映される描画経路。
