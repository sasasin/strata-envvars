# `--dry-run`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--dry-run` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。既定値は `false` |

## 役割

指定したアプリ用の設定ファイルを書き込む代わりに、作成・置換・マージされるファイルとバックアップ先をプレビューします。実装では `--dry-run` 自体がプレビュー処理を起動するため、`--write` を付けなくても使えます。`--check` も指定した場合は、先にサーバーへのチェックを行い、失敗するとプレビューを実行しません。

## 使い方

```sh
# OpenCode 用ファイルの書き込み予定を表示する（ファイルは変更しない）
strata connect opencode --dry-run

# JSON 形式でレンダリング結果と書き込み予定を表示する
strata connect opencode --dry-run --output json

# サーバーチェックに成功した場合だけ書き込み予定を表示する
strata connect opencode --check --dry-run
```

## 値と既定値

引数を取らず、指定すると `true`、省略時は `false` です。値を伴わせる形式や許容範囲の validation はありません。parser は `argparse` の `store_true` として登録しています（`terminal/strata_cli/launch/cmd.py:177`）。

## 実行時の動作

アプリ設定をレンダリングした後、`--dry-run` があると `run_connect` は書き込み処理へ進みます。これは parser の説明文「with `--write`」より広い挙動です。`--write` がなくてもプレビューされます（`terminal/strata_cli/launch/cmd.py:1108-1110`, `1156-1157`）。

書き込み処理は各出力ファイルについて、既存ファイルなら置換または JSON のマージを判定し、`would_create`、`would_replace`、`would_merge` などの予定を返します。`--if-unchanged` も指定され、最終内容が既存ファイルと一致する場合は `unchanged` になります（`terminal/strata_cli/launch/harness.py:363-390`）。`--yes` による確認省略は不要で、dry-run のときは確認プロンプト自体を通りません（`terminal/strata_cli/launch/cmd.py:1024-1038`）。

## 適用条件と副作用

このフラグは対象アプリのファイルがレンダリングされる場合に書き込み予定を表示します。対象アプリの指定がない場合はアプリ一覧を表示して終了するため、プレビュー対象のファイルはありません（`terminal/strata_cli/launch/cmd.py:1055-1066`）。

dry-run 中はディレクトリ作成、バックアップコピー、ファイル書き込みを行いません（`terminal/strata_cli/launch/harness.py:387-399`）。`--if-unchanged` と併用した一致判定でも、dry-run 中はファイル権限を変更しません（同 `:373-384`）。`--check` も併用した場合はサーバーへチェック要求を送信します。全チェック成功後にプレビューへ進み、ひとつでも失敗すれば終了コード `1` でそこで終了します（`terminal/strata_cli/launch/cmd.py:1087-1107`, `1147-1155`）。

## 出力とエラー

人間向け出力では、予定された操作とパス（既存ファイルを置き換える場合はバックアップ先も）を表示し、最後に `Dry run: nothing was written.` と表示します（`terminal/strata_cli/launch/cmd.py:1041-1050`, `1156-1167`）。

`--output json` では、各ファイルの予定を `write.written` に、プレビューであることを `write.dry_run: true` として出力します。JSON 形式でも設定内容は表示されますが、API キーは `--show-key` がない限りマスクされます（`terminal/strata_cli/launch/cmd.py:1082-1085`, `1108-1118`）。

ファイルがないアプリでは書き込み予定は空になり、終了コード `0` です（`terminal/strata_cli/launch/cmd.py:1022-1023`）。`--check` の失敗時はプレビュー結果を出さず終了コード `1` です（同 `:1097-1107`, `1151-1155`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser と同スコープのオプション登録。`--dry-run` は値なしの `store_true`。
- `terminal/strata_cli/launch/cmd.py:1019-1050` — 確認を省略する条件、ファイルごとの結果処理、失敗時の戻り値。
- `terminal/strata_cli/launch/cmd.py:1052-1119`, `1120-1167` — dry-run が `--write` なしでも実行される分岐、JSON／人間向けの出力、`--check` 失敗時の早期終了。
- `terminal/strata_cli/launch/harness.py:355-399` — dry-run での既存ファイル判定、予定アクション、ディスク変更を行わない分岐。
