# `strata connect --yes`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らないフラグ（指定時 `True`、省略時 `False`） |

## 役割

`--write` が出力するアプリ設定ファイルを書き込む前の対話確認を省略します。このフラグ単独ではファイルを書き換えません。

## 使い方

```sh
# OpenCode 用の設定を確認なしで書き込む。既存ファイルは先にバックアップされる
strata connect opencode --write --yes
```

## 値と既定値

値は不要で、既定値は `False` です。parser は `store_true` として登録しており、短縮別名や値の validation はありません。同じフラグを複数回指定しても真偽値は `True` のままです（`terminal/strata_cli/launch/cmd.py:163-182`）。

## 実行時の動作

`strata connect` は parser が作った Namespace を `run_connect` に渡します（`terminal/strata_cli/cli.py:2235-2237`）。`run_connect` はアプリ向け出力を組み立て、`--write` または `--dry-run` が指定されたときに書き込み処理へ進みます（`terminal/strata_cli/launch/cmd.py:1052-1054,1074-1080,1108-1110,1156-1158`）。

書き込み処理に対象ファイルがあり、`--dry-run` でもない場合、`--yes` がなければ確認を求めます。`--yes` があればこの確認分岐だけを飛ばし、対象ファイルを順に書き込みます（`terminal/strata_cli/launch/cmd.py:1019-1044`）。既存ファイルは `.strata-bak-<時刻>` 名でコピーされてから書き換えられ、出力先ディレクトリも必要に応じて作成されます（`terminal/strata_cli/launch/harness.py:355-360,387-399`）。

他の関連フラグとの関係:

- `--yes` だけでは書き込み処理は始まりません。`--write`（または `--dry-run`）が必要です。
- `--dry-run` は確認を省いて書き込み内容をプレビューし、ディスク上のファイルを作成・変更しません。`--yes` の指定は不要です（`terminal/strata_cli/launch/cmd.py:1024-1027`, `terminal/strata_cli/launch/harness.py:355-360,387-390`）。
- `--check` と併用した場合、サーバーへの確認を先に実行します。確認が失敗すると終了コード 1 で戻り、`--yes` が指定されていても書き込みません（`terminal/strata_cli/launch/cmd.py:1087-1107,1147-1155`）。
- `--output json` でも同じ確認省略と書き込み経路を使います（`terminal/strata_cli/launch/cmd.py:1083-1118`）。

## 適用条件と副作用

この `--yes` は `connect` サブコマンドの parser に登録されたフラグで、`launch` 側の同名フラグとは別のスコープ・動作です（`terminal/strata_cli/launch/cmd.py:150-152,163-182`）。書き込みは `--write` が有効な場合に限られ、`--yes` 自体は設定ファイルを変更しません。書き込みによるファイル作成・置換・バックアップについては上記の通りです。

## 出力とエラー

- `--write` を対話端末なしで実行し、`--yes` も `--dry-run` もない場合は「端末で実行するか `--yes` を追加する」旨を返し、終了コード 2 になります（`terminal/strata_cli/launch/cmd.py:1025-1027`）。JSON 出力ではエラーを含む JSON オブジェクトを stdout に出します（同 `cmd.py:1108-1115`）。
- 対話確認に `y` または `yes` 以外を入力した場合（EOF を含む）は何も書かず、終了コード 0 です（`terminal/strata_cli/launch/cmd.py:1028-1038`）。
- 書き込み中の `OSError` は失敗として報告され、後続ファイルは `not_written` とされ、終了コード 1 になります（`terminal/strata_cli/launch/cmd.py:1039-1049`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-182` — `connect` parser と `--yes` の `store_true` 登録、および隣接オプション。
- `terminal/strata_cli/cli.py:2235-2237` — `connect` の処理関数への dispatch。
- `terminal/strata_cli/launch/cmd.py:1019-1050,1052-1080,1087-1118,1147-1168` — 確認省略、書き込み・dry-run 条件、`--check` の順序、出力と終了コード。
- `terminal/strata_cli/launch/harness.py:355-399` — 既存ファイルのバックアップ、dry-run、およびファイル書き込み。
