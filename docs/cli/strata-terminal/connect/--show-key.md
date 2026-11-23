# `--show-key`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--show-key` |
| 別名 | なし |
| 値 | 値を取らないフラグ（指定すると有効） |

## 役割

指定したアプリ向け接続設定を表示するとき、通常は伏せられる API キーを人間向け出力にそのまま表示します。`strata connect` は、起動中の `strata launch`、指定したプリセット、または引数から接続先情報を組み立て、アプリ用の設定内容と環境変数を表示します。キーの選択は `--key`、`--key-env`、`--preset` などで行い、このフラグは表示方法だけを切り替えます（`terminal/strata_cli/launch/cmd.py:163-182, 1074-1085`）。

## 使い方

```sh
# OpenCode向け設定を表示し、APIキーも表示する
strata connect opencode --show-key
```

## 値と既定値

- `argparse` の `store_true` フラグで、値・別名・追加の値検証はありません。省略時は無効です（`terminal/strata_cli/launch/cmd.py:181`）。
- コマンドはキーを `--key`、指定環境変数の値、選択された起動情報のキー、空文字列の順で選びます。したがって、環境変数が未設定または空なら起動情報のキーへ進みます。キーがない場合、設定生成では `strata-local` というプレースホルダーが使われます（`terminal/strata_cli/launch/cmd.py:1074-1080`, `terminal/strata_cli/launch/harness.py:21, 339-347`）。
- harness（例: `opencode`）を指定しない呼び出しはアプリ一覧を返して早期終了するため、その場合 `--show-key` はキーを表示しません（`terminal/strata_cli/launch/cmd.py:1055-1065`）。

## 実行時の動作

- 人間向け出力（既定の `--output human`）では、フラグなしの場合、生成したファイル内容と環境変数に含まれる実キーをマスクし、キーが含まれているときは `--show-key` を追加する案内を出します。マスクはキー文字列全体を「先頭10文字＋8個の伏字」に置換します（`terminal/strata_cli/launch/cmd.py:1123-1136`, `terminal/strata_cli/launch/harness.py:432-433`）。フラグを付けると、ファイル内容と環境変数の値に実キーを含めて表示します（`terminal/strata_cli/launch/cmd.py:1081, 1123-1133`）。
- `--output json` では、`--show-key` の有無にかかわらず、JSON内の生成設定文字列を実キーでマスクします。したがって、このフラグはJSON出力の秘匿状態を解除しません（`terminal/strata_cli/launch/cmd.py:1082-1086`）。
- `--write` と併用した場合、フラグの有無にかかわらず生成設定の内容が書き込まれます。人間向け出力では書き込み処理より前に設定内容を表示するため、`--show-key --write` はファイルへの保存に加えて標準出力にも実キーを出します。実行前確認、既存ファイルのバックアップ、`--dry-run` 等の書き込み規則は `--show-key` では変わりません（`terminal/strata_cli/launch/cmd.py:1123-1127, 1156-1167, 1019-1050`; `terminal/strata_cli/launch/harness.py:343-347, 355-399`）。

## 適用条件と副作用

- 対象アプリ名が解決できた場合の人間向け接続設定表示に作用します。キーを実表示すると、端末の画面・標準出力の保存先などから秘密情報が見える状態になります。安全な保管先か確認してから実行してください。
- `--check` を併用すると、設定表示の後にサーバーへプロンプトとツール呼び出しを送ります。人間向け経路では接続チェックが失敗しても、それより前に表示された実キーは取り消されません（`terminal/strata_cli/launch/cmd.py:1123-1155`）。
- harness 名が無効なら候補付きエラーを標準エラーへ出し、終了コード `2` で終了します。未知オプションも parser 後の検査で標準エラーに案内を出して終了コード `2` になります（`terminal/strata_cli/launch/cmd.py:1067-1073`, `terminal/strata_cli/cli.py:2327-2334`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser と `--show-key` の宣言。
- `terminal/strata_cli/launch/cmd.py:1052-1085` — harness 解決、キー・接続情報の選択、出力形式別のマスキング。
- `terminal/strata_cli/launch/cmd.py:1120-1168` — 人間向けのキー表示、チェック、書き込みの順序と失敗時の終了コード。
- `terminal/strata_cli/launch/harness.py:21, 339-347, 355-399, 432-433` — キープレースホルダー、設定生成、ファイル書き込みとマスク処理。
- `terminal/strata_cli/cli.py:2327-2334` — parser が認識しないオプションのエラー経路。
