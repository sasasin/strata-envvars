# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

人向け出力モードで `strata update` が stdout に出す通常の案内・進捗・結果を抑制します。更新処理や `--check` の処理を省略するフラグではなく、Terminal CLI が表示を制御します。

## 使い方

```sh
strata update --check --quiet
```

これはフィードを確認して差分を表示するコマンドの出力を抑えます。実際の更新にも指定できます。

```sh
strata update --quiet
```

## 値と既定値

値は不要です。省略時は `quiet` が false として扱われ、明示すると true になります。短縮別名はありません。parser は `store_true` で登録します。

## 実行時の動作

`strata update` の parser は `strata_cli/update_cmd.py` で作られます。`strata_cli/cli.py` は `update_parsers` を含む one-shot parser 群へ `--quiet` を `action="store_true"`、`default=argparse.SUPPRESS` で追加します。実行時には未指定を `getattr(a, "quiet", False)` で false として扱います。

人向け出力（既定の `--output human`）で quiet が有効な場合、CLI は `_run()` 中の stdout を最大 64 KiB の捕捉先へリダイレクトします。成功時は捕捉した内容を表示しません。`strata update --check` の結果も、通常更新時の案内・進捗・結果もこの対象です。stderr は捕捉されません。

`--json` を併用すると、CLI は `--output json` に切り替え、quiet の捕捉分岐を通りません。`--output json` と `--output jsonl` も同様に quiet では抑制されません。更新コマンドは JSONL の進捗イベントを stdout に書き、JSON/JSONL の最終結果も stdout に出します。

## 適用条件と副作用

quiet は stdout の表示にだけ作用し、更新処理の選択・実行には影響しません。`strata update` は引き続き取得元の署名済みフィードを読み、既定では対象 PC の engine と Control の更新を試みます。必要に応じてネットワーク取得、検証、インストール、engine のテスト起動などが行われます。出力を隠す用途だけなら、実際の更新を行わない `--check` と組み合わせてください。

`--quiet` 自体に値の範囲 validation はありません。値を付けるなど parser が受理しない引数は通常の argparse 引数エラーになります。共通の登録処理は `strata components update` と `strata components rollback` にも quiet を追加しますが、この文書の対象スコープは `strata update` です。

捕捉する人向け stdout は最大 64 KiB です。これを超えた内容は末尾側が保持され、処理失敗時に捕捉内容を stderr に戻す際、先行出力を省略した通知も stderr に出ます。

## 出力とエラー

- 人向けモードで成功した場合、コマンド処理の stdout は抑制されます。quiet は stderr の警告やエラーを抑制しません。
- 人向けモードで失敗した場合、更新処理が直接 stderr に書いた診断に加え、捕捉済み stdout が stderr に再出力されます。捕捉内容が 64 KiB を超えた場合は省略通知も出ます。
- `--json`、`--output json`、`--output jsonl` の出力は quiet でも stdout に残ります。
- update の失敗終了コードは quiet によって変更されません。ソースの説明では usage error は 2、拒否（署名・hash・downgrade・鍵なし・取得禁止など）は 5、ネットワークまたはテスト起動の失敗は 6、実行中 engine による拒否は 7、停止は 130 です。

## 根拠

- parser と適用スコープ: `strata_cli/update_cmd.py:42-59` が `strata update` と関連 parser を作成し、`strata_cli/cli.py:508-515` が `update_parsers` を含む one-shot parser に `--quiet` を追加します。
- 既定の出力形式と update 処理: `strata_cli/update_cmd.py:30-40` が共通 `--output` を `human` 既定で定義し、`strata_cli/update_cmd.py:163-224` が feed 確認、`--check`、更新実行と結果表示を行います。quiet を更新処理へ渡す箇所はありません。
- update の stdout/stderr: `strata_cli/update_cmd.py:62-84` が human 進捗・phase・waiting と JSONL event の出力を定義し、`strata_cli/update_cmd.py:167-172` が失敗メッセージを stderr（machine mode では JSON stdout）へ出します。例外と停止の処理は `strata_cli/update_cmd.py:225-234` です。
- quiet の捕捉上限、成功時抑制、失敗時再出力、JSON/JSONL の相互作用: `strata_cli/cli.py:2196-2214` および `strata_cli/cli.py:2217-2248`。`--json` alias による出力形式変更は `strata_cli/cli.py:2232-2235` です。
- 終了コードの説明: `strata_cli/update_cmd.py:9-11`。
