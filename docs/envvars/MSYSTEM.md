# `MSYSTEM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`strata launch` が通常の画面（TUI）を開けない場合に、Git Bash / mintty などの端末では人が入力できる可能性を示します。該当する場合、選択肢なしの起動をエラーにせず、プレーンテキストで起動確認を尋ねます。Strata は `MSYSTEM` の値を Git Bash の種類などとして解釈しません。

## 値と判定

`os.environ.get("MSYSTEM")` の結果を他の端末環境変数と論理 OR し、最後に `bool(...)` を適用します。値の parse、trim、大小文字変換はありません。

| `MSYSTEM` | `_can_ask()` への寄与 |
|---|---|
| 未設定 | 偽 |
| 空文字 | 偽 |
| 空でない文字列（例: `MINGW64`, `0`, `false`） | 真 |

この判定より先に stdin が `None` または closed なら偽を返します。また `CI` または `STRATA_NO_PROMPT` が空でない場合も偽を返し、`MSYSTEM` が設定されていても打ち消します。空文字の `CI` / `STRATA_NO_PROMPT` はこの拒否条件になりません。別の `TERM_PROGRAM`、`TERM`、`WT_SESSION` のいずれかが空でなくても同じく真になります。

根拠: `strata_cli/launch/cmd.py:511-518`。

## 有効になる条件

`MSYSTEM` が非空でも、常に起動確認が出るわけではありません。`run_launch()` で、選択肢（preset / model など）がなく、TUI を使わず、plan 実行でもない場合に限って `_can_ask()` が呼ばれます。さらに `machine`（`--output json`）、`--no-tui`、モデルカタログを利用できない状態のいずれかなら、`_can_ask()` の結果にかかわらず確認へ進みません。

したがって、明示的な起動選択がある場合、通常の TUI が開く場合、`--plan` の場合には、この環境変数による分岐は起きません。OS を調べる条件もなく、どの OS でも同じ Python 判定です。

根拠: `strata_cli/launch/cmd.py:686-697,753-778`。

## 実行時の詳細

stdin が非 TTY でも、`MSYSTEM`（または他の許可側環境変数）が非空で、拒否条件や上記の CLI 条件に該当しなければ、`plain_questions` を有効にして「This window cannot show Strata's screens (Git Bash and similar windows do not pass the keyboard through). For the screens, open Windows Terminal, PowerShell or cmd, or run `winpty strata launch`. Going on with plain questions.」を表示し、その後 `Start it now? Models can be tens of GB to download. [Y/n]` を尋ねます。空入力、`y`、`yes` は続行し、それ以外の返答では「Nothing was changed.」を表示して終了コード 0 になります。入力時に `EOFError` になると「There is nobody to answer. Name what to start: --preset NAME, or --model NAME (strata launch --help has examples).」を stderr に出して終了コード 2 です。確認を通過した後の起動処理は `Runner.run()` に進みます。

許可条件を満たさないと、選択肢を指定するよう促すエラー（既定の終了コード 2）になります。`--output json` では同じ失敗が JSON の `ok: false` / `error` として stdout に出ます。`MSYSTEM` は `_can_ask()` 呼び出し時に都度読み取られ、static cache 等への保存はありません。Strata がこの値を子プロセスへ転送または書き換える処理は、この参照箇所にはありません。

根拠: `strata_cli/launch/cmd.py:511-518,766-773,842-849,692-697`。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:460`。
- 本番コードの唯一の `MSYSTEM` 参照・読み取り: `strata_cli/launch/cmd.py:518`。
- 起動選択がないときの判定と plain-question への分岐: `strata_cli/launch/cmd.py:753-778`。
- plain-question の継続・拒否・EOF 経路: `strata_cli/launch/cmd.py:842-849`。
- `MSYSTEM` をセットするテストもありますが、挙動の説明根拠は上記本番コードです: `tests/terminal/test_launch.py:952-971`。
