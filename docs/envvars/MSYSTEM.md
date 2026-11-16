# `MSYSTEM`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`strata launch` が、標準入力・標準出力が TTY ではなくても人が端末から入力している可能性を判定する手掛かりの一つ。`MSYSTEM` が空でないと `_can_ask()` は真になり、選択肢をコマンドラインで指定していない通常実行では、TUI の代わりにプレーンテキストで続行確認を行う経路を許可する。`MSYSTEM` 自体は TUI の有効化やモデル・サーバー設定を変更しない。実装は `strata_cli/launch/cmd.py` の `_can_ask()` と `run_launch()`（534-541、801-820 行）。

## 値と判定

Python の `os.environ.get("MSYSTEM")` の返り値を `or` 条件で評価する。文字列の解析、数値変換、大小文字の正規化は行わず、値が空文字列かどうかだけがこの項目単独の判定を左右する（`strata_cli/launch/cmd.py:541`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata launch` の `_can_ask()` | この項目は偽 | 空でない任意の文字列（例: `MINGW64`、`0`、`false`、空白のみ、大文字小文字を問わない文字列） | 空文字列 `""`。ただし他の端末環境変数が真なら関数全体は真になり得る |

`MSYSTEM` が空または未設定でも、`TERM_PROGRAM`、`TERM`、`WT_SESSION` のどれかが空でなければ同じ判定を通る。逆に、`CI` または `STRATA_NO_PROMPT` が空でない場合は `MSYSTEM` を含む端末環境の判定より先に `_can_ask()` が偽を返す（`strata_cli/launch/cmd.py:537-541`）。

## 有効になる条件

- `_can_ask()` が呼ばれるのは、`run_launch()` で選択肢がなく、通常の TUI 経路でもなく、`--plan` でもない場合の確認経路。`--preset`、`--model`、`--model-path` などの選択肢がある実行ではこの分岐に入らず、`MSYSTEM` はその実行に影響しない（`strata_cli/launch/cmd.py:803-820`）。
- 標準入力が `None` または閉じている場合は、環境変数判定より先に偽となる。`CI` または `STRATA_NO_PROMPT` が空でない場合も無効（`strata_cli/launch/cmd.py:537-541`）。
- `--output json`（`machine`）、`--no-tui`、カタログ取得失敗時も確認せず、エラー経路へ進む。`--plan` はこの確認分岐自体を迂回する（`strata_cli/launch/cmd.py:714-720, 812-820, 851-877`）。
- `_can_ask()` の条件には `--yes` が含まれない。したがって、この「選択肢なし」のプレーンテキスト確認は `--yes` だけでは省略されない（`strata_cli/launch/cmd.py:813-820, 889-896`）。
- OS や backend による `MSYSTEM` 判定の分岐はない。この判定が効くのは Strata の Python `strata launch` 経路であり、エンジンの C++/GPU 処理やサーバーの動作を切り替えるものではない（`strata_cli/launch/cmd.py:534-541, 710-720`）。

## 実行時の詳細

値は `_can_ask()` の呼び出し時に `os.environ.get()` で読み、静的キャッシュはしない。`run_launch()` の該当分岐から呼ばれるのは一度であり、その時点の `os.environ` が使われる（`strata_cli/launch/cmd.py:534-541, 812-820`）。

`MSYSTEM` などの環境判定を通ると `plain_questions` を真にし、TUI なしで処理を続ける。選択肢なしで TUI が開けないことを知らせ、モデル開始前に `Start it now? Models can be tens of GB to download. [Y/n] ` と入力を求める。空入力・`y`・`yes` は続行し、それ以外は「Nothing was changed.」を表示して終了コード 0。入力が EOF ならエラー文を出してコード 2 で終了する（`strata_cli/launch/cmd.py:816-820, 889-896`）。

## ログと測定値

この変数について測定値の記載はない。TTY ではない実行で判定を通ると、標準出力に次の案内を出してから質問する。

```text
This window cannot show Strata's screens (Git Bash and similar windows do not pass the keyboard through). For the screens, open Windows Terminal, PowerShell or cmd, or run `winpty strata launch`. Going on with plain questions.
```

回答できる入力が EOF になった場合は、`strata: There is nobody to answer. Name what to start: --preset NAME, or --model NAME (strata launch --help has examples).` を標準エラーに出し、コード 2 を返す。JSON 出力など `machine` の場合は同じ失敗を JSON で出力する（`strata_cli/launch/cmd.py:716-721, 816-820, 889-896`）。

## 根拠

- `strata_cli/launch/cmd.py:534-541` — `_can_ask()` の標準入力・抑止変数・端末環境変数の判定。
- `strata_cli/launch/cmd.py:801-820` — TTY による画面経路、選択肢なしの場合の分岐と案内。
- `strata_cli/launch/cmd.py:889-896` — プレーンテキスト確認、回答・EOF の処理。
- `strata_cli/launch/cmd.py:714-721, 851-877` — JSON モードとエラー出力、および `--plan` の終了経路。
