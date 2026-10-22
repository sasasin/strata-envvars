# `STRATA_NO_PROMPT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata launch` が、標準入出力は TTY ではないもののキーボード入力を受け取れる端末で、対話を続けてよいか判定するための抑止フラグです。設定されていると、この特殊な非 TTY 端末を「質問に答えられる」と扱わなくなります。通常の TTY で表示する画面や確認を一律に無効化する設定ではありません。

## 値と判定

Python の `os.environ.get("STRATA_NO_PROMPT")` を真偽値として評価します。値の文字列比較や数値変換はありません。

| 値 | `_can_ask()` での扱い |
|---|---|
| 未設定 | この変数による抑止なし |
| 空文字 | 偽として扱われ、この変数による抑止なし |
| 空でない任意の文字列 | 真として扱われ、質問不可になる。`0`, `false`, `no` も抑止する |

ただし `CI` が空でない場合も同じ判定で質問不可となります。`_can_ask()` は値を static cache せず、呼ばれるたびに現在の環境を読みます。

根拠: `strata_cli/launch/cmd.py:430-438`。

## 有効になる条件

この判定は `strata launch` の `run_launch()` にあり、次の条件に該当する際にだけ結果が使われます。

- 起動内容の選択肢（preset、model、model path、context、vision、parallel、access、tune）が指定されていない。
- TUI を使う対話実行ではなく、`--plan` でもない。
- `_can_ask()` のほか、機械出力モードでないこと、モデル catalog が使えることも満たす必要がある。

この経路で `STRATA_NO_PROMPT` が空でないと `_can_ask()` は偽になり、コマンドは終了コード 2 で「何を起動するか指定する」旨を返します。空で未指定かつ `MSYSTEM`、`TERM_PROGRAM`、`TERM`、`WT_SESSION` のいずれかが空でなければ、非 TTY でも入力可能な端末として扱い、画面を使わない説明の後に起動確認を出します。`stdin` が存在しないか閉じている場合は、環境変数の値にかかわらず質問不可です。

`STRATA_NO_PROMPT` は `_ask_yes()` からは参照されません。たとえば選択内容を指定して進む経路で、engine がなく大容量モデルのダウンロード前確認に達した場合、TTY の stdin/stdout があれば `_ask_yes()` が別途 `Go on? [Y/n]` を尋ねます。逆に TTY でない場合、`_ask_yes()` は確認を表示せず `True` を返します。この確認は `--yes` / machine モード等の `assume_yes` が立っている場合には Runner 側で呼ばれません。

根拠: `strata_cli/launch/cmd.py:430-451,556-560,611-635`; `strata_cli/launch/runner.py:366-380,510-526`。

## 実行時の詳細

`_can_ask()` は各 `run_launch()` の選択判定から呼ばれます。判定が偽で、利用者が何も指定していない場合に返されるエラーは `strata launch` に選択肢を指定するよう促し、`--plan` も案内します。判定が真なら `plain_questions` が有効になり、「画面を表示できない端末である」という案内に続けて `Start it now? Models can be tens of GB to download. [Y/n]` を尋ねます。ここでは Enter / `y` / `yes` が続行、それ以外は変更せず終了です。

本変数を確認する参照はこの `_can_ask()` の一箇所です。起動プロセスへの転送や、サーバー・engine における読み取りはありません。

根拠: `strata_cli/launch/cmd.py:430-438,614-624,688-695`。
