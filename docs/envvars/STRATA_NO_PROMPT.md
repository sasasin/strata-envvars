# `STRATA_NO_PROMPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata launch` で選択肢がなく、TUI を開けない場合に、プレーンテキストの確認質問へ進んでよいかを抑止する変数です。`_can_ask()` は `CI` とこの変数のどちらかが真なら質問不可と判定します。その結果 `run_launch()` は「今起動するか」を尋ねず、選択肢を指定するよう stderr に案内して終了コード `2` を返します（`terminal/strata_cli/launch/cmd.py:570-584, 859-866, 937-944`）。

これは全ての質問を無効にするスイッチではありません。選択肢のある起動ではこの変数を調べず、TUI を使わない起動の別確認は `_ask_yes()` が扱います。通常の TTY で `_ask_yes()` が質問できるかは `STRATA_NO_PROMPT` を参照しません（同 `:586-598, 876-877`）。

## 値と判定

`os.environ.get("STRATA_NO_PROMPT")` の戻り値を Python の真偽値として判定します。文字列の parse はしません。未設定と空文字 `""` は偽、空でない文字列は真です。したがって `"0"`、`"false"`、`"no"`、空白だけの値も抑止になります。大文字小文字、数値としての妥当性、前後空白は検査されません。判定は `CI` と OR で結合され、どちらかが空でない値なら質問不可です（`terminal/strata_cli/launch/cmd.py:573-576`）。

| 条件 | 未設定 | 質問を抑止する値 | 抑止しない値 |
|---|---|---|---|
| `_can_ask()` が評価される場合 | 偽（この変数だけでは抑止しない） | 空でない文字列全て。例: `1`、`0`、`true`、`false`、`no`、` ` | 空文字 `""` |

## 有効になる条件

- `run_launch()` に選択肢（preset、model、model path 等）がなく、通常の TUI 経路ではなく、`--plan` でもない場合にだけ、質問可否の分岐へ進みます（`terminal/strata_cli/launch/cmd.py:849-864`）。通常の TTY で画面を開く実行ではこの変数は評価されません。
- `--output json`、`--no-tui`、モデルカタログ不在の場合は `_can_ask()` より前に同じ失敗経路へ入ります。その場合、変数の設定有無は結果を変えません（同 `:859-862`）。
- 上記に該当しない場合でも、標準入力が `None` または closed なら質問不可です。`CI` または `STRATA_NO_PROMPT` が空でない場合も、後続の端末識別変数判定より先に質問不可になります（同 `:570-576`）。
- `noinput` を import できた場合、抑止変数が空または未設定でも、標準入力が null device なら `noinput.stdin_is_no_keyboard()` が真を返します。標準入力が pipe、通常ファイル、端末、または種別を読めない場合はこの関数は偽です（`terminal/strata_cli/noinput.py:16-24`）。このモジュールを import できない場合は null device 判定を行わず、端末 marker の有無で判定します（`terminal/strata_cli/launch/cmd.py:578-583`）。
- さらに `_can_ask()` は `MSYSTEM`、`TERM_PROGRAM`、`TERM`、`WT_SESSION` のいずれかが空でないことを求めます。全て空または未設定なら質問不可です。`terminal/strata_cli/noinput` を import できない場合も、同じ4変数の有無で判定します（`terminal/strata_cli/launch/cmd.py:578-583`）。
- `--yes` はこの選択肢なしの質問可否判定には使われません。選択肢を指定した起動のエンジン更新・モデル取得などの runner 確認では、`--yes` または JSON 出力が `assume_yes` を決めますが、`STRATA_NO_PROMPT` はその判定に渡されません（同 `:876-877`; `terminal/strata_cli/launch/runner.py:1184-1188, 1278-1287`）。

## 実行時の詳細

環境変数は `_can_ask()` の実行時に `os.environ.get()` で読み取られ、static cache や設定値への保存はありません。`run_launch()` の該当分岐は一度だけ `_can_ask()` を呼びます。`CI` または `STRATA_NO_PROMPT` が真なら、端末環境の marker を確認せず false となり、プレーン質問への移行 (`plain_questions = True`) を行いません（`terminal/strata_cli/launch/cmd.py:570-584, 859-866`）。

抑止されず、他の `_can_ask()` 条件も満たす場合、画面を表示できない理由を案内してから `Start it now? Models can be tens of GB to download. [Y/n]` と尋ねます。EOF なら stderr に選択肢を指定する案内を出してコード `2` で終了し、回答が空・`y`・`yes` 以外なら `Nothing was changed.` と出して `0` で終了します（同 `:863-866, 937-944`）。抑止された場合は確認文を表示せず、stderr に次の文を出して `2` で終了します（同 `:759-764, 859-862`）。

> strata: `strata launch` with no choices opens screens, and this is not a terminal (or --no-tui was given). Name what to start: --preset NAME, or --model NAME (strata launch --help has examples; --plan shows what would happen without changing anything).

`os.environ` をこの判定後に変更しても、その実行では再判定されません。次に `_can_ask()` が呼ばれる実行では、その呼び出し時点の値が読まれます。

## ログと測定値

この変数専用のログや warning はありません。抑止時に観測できる結果は `run_launch()` の上記 stderr 文と終了コード `2` です。抑止されない場合の案内文・質問文、および EOF 時の文言は `terminal/strata_cli/launch/cmd.py:563-567, 937-944` にあります。性能測定値は該当しません。

## 根拠

- `terminal/strata_cli/launch/cmd.py:570-584` — `CI` と `STRATA_NO_PROMPT` の読み取り、stdin・null device・端末 marker の判定。
- `terminal/strata_cli/launch/cmd.py:759-764, 849-866, 937-944` — 呼び出し条件、質問経路、stderr・終了コード。
- `terminal/strata_cli/launch/cmd.py:586-598, 876-877` — runner の確認関数と `--yes` / JSON の受け渡し。
- `terminal/strata_cli/noinput.py:16-24` — stdin が null device かどうかの判定。
- `terminal/strata_cli/launch/runner.py:1184-1188, 1278-1287` — runner 側の確認に `STRATA_NO_PROMPT` が関与しないことと、別途 `assume_yes` が使われる箇所。
