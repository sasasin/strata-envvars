# `CI`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`CI` は `strata launch` の「選択肢がなく、対話画面も開けない」場合に、端末環境変数を見て質問可能と判断する plain-question 経路を抑止します。Strata のエンジンやサーバーの動作を変える設定ではありません。

## 値と判定

`_can_ask()` は `os.environ.get("CI")` の戻り値を Python の真偽値として判定します。文字列の内容は parse せず、数値変換・大文字小文字変換もしません。

| 環境値 | `_can_ask()` での扱い |
|---|---|
| 未設定 | `CI` 自体は質問を拒否しない。後続の条件を評価する |
| 空文字 | 未設定と同じく拒否条件にならない |
| 空でない文字列（`1`, `0`, `false` など） | 真として質問を拒否する |

値が空でも、標準入力が `None` または closed なら先に質問不可になります。`CI` の拒否判定より後には、`MSYSTEM`、`TERM_PROGRAM`、`TERM`、`WT_SESSION` のいずれかが空でないかを調べます。`CI` が空でない場合、これらの端末 marker があっても質問可には戻りません。`STRATA_NO_PROMPT` も同じ拒否条件です（`strata_cli/launch/cmd.py:611-618`）。

## 有効になる条件

`strata launch` で選択肢（preset、model など）がなく、対話画面を開けず、かつ `--plan` でもない場合にだけ、呼び出し側は `_can_ask()` の結果を使います。さらに `--output json`、`--no-tui`、カタログ不在のいずれかなら `CI` の値にかかわらず失敗分岐になります。通常の TTY で対話画面を開く場合や、モデル等を指定した起動では、この `_can_ask()` 判定は使われません（`strata_cli/launch/cmd.py:877-903`）。

このため、対象経路で `CI` が空でないと `_can_ask()` は false となり、plain-question で「今起動するか」を尋ねず、exit code `2` で終了します。`fail()` は通常出力ではなく stderr に次のエラーを出します（`strata_cli/launch/cmd.py:792-797`）。

```text
strata: `strata launch` with no choices opens screens, and this is not a terminal (or --no-tui was given). Name what to start: --preset NAME, or --model NAME (strata launch --help has examples; --plan shows what would happen without changing anything).
```

根拠: `strata_cli/launch/cmd.py:888-896`。`strata launch` は CLI から `run_launch()` に渡されます（`strata_cli/cli.py:2154-2156`）。

## 実行時の詳細

`CI` は `_can_ask()` が呼ばれるたびに `os.environ.get()` で読み取られ、値を cache しません。プロセス起動後に環境を書き換えた場合も、次回の判定時には新しい値を読みます（`strata_cli/launch/cmd.py:611-618`）。この変数を使った追加ログや warning はなく、観測できる結果は上記の失敗メッセージと exit code です。選択肢を指定した起動で別の確認が必要な経路は `_ask_yes()` を使いますが、そこでは `CI` を読みません（同 `:621-632,906-907`）。

## 根拠

- `strata_cli/launch/cmd.py:611-618` — `CI` の直接読み取り、空でない値の truthiness 判定、他の環境変数との関係。
- `strata_cli/launch/cmd.py:877-903` — 判定が使われる CLI 条件と、該当時のエラー経路。
- `strata_cli/launch/cmd.py:621-632,906-907` — 選択肢を指定した起動の別確認経路では `CI` を参照しないこと。
- `strata_cli/cli.py:2154-2156` — `strata launch` から `run_launch()` への呼び出し。
