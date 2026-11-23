# `strata connect --if-unchanged`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--if-unchanged` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。指定時は有効 |

## 役割

`--write` でアプリ用設定ファイルを書き出すとき、既存ファイルが今回生成する最終内容と一致すれば、その内容を書き直したりバックアップを作ったりせず `unchanged` として扱います。`--dry-run` と併用した場合も同じ一致判定を行い、変更を加えずに `unchanged` と報告します。フラグ単独では書き込み処理を開始しません。

## 使い方

```sh
# 既存内容が生成内容と同じならそのファイルをそのままにし、異なる場合は確認して書く
strata connect opencode --write --if-unchanged

# 同じ判定で書き込み予定を表示する（ファイルは変更しない）
strata connect opencode --write --dry-run --if-unchanged
```

## 値と既定値

値や別名はありません。parser は `action="store_true"` で登録しており、省略時は無効、指定時は有効です（`terminal/strata_cli/launch/cmd.py:178-179`）。値を付ける形式ではなく、`=値` を付けるなど parser が知らない引数を渡すと、`strata connect` は未知の option として stderr に案内を出して終了コード 2 を返します（`terminal/strata_cli/cli.py:2327-2334`、`terminal/strata_cli/launch/cmd.py:186-201`）。

## 実行時の動作

`strata connect` は `--write` または `--dry-run` が指定されたときにファイル書き込み処理を呼び出し、`--if-unchanged` の値を各ファイルの書き込み関数へ渡します（`terminal/strata_cli/launch/cmd.py:1156-1157`、`terminal/strata_cli/launch/cmd.py:1039-1045`）。両方を指定しない場合、このフラグは生成内容の表示やその他の処理を変えません。

対象ファイルが存在すると、Strata はまず書き込み予定の内容を作ります。JSON merge 対象では既存 JSON のキーを取り込み、新しい値を優先して merge した後に比較します。ファイル末尾に改行がなければ追加し、現在のプラットフォームの改行コードにした UTF-8（BOM なし）のバイト列と、既存ファイルのバイト列が完全一致する場合に `unchanged` を返します（`terminal/strata_cli/launch/harness.py:361-378`）。したがって、内容が同じに見えても BOM や異なる改行コードがあれば一致扱いにならず、通常の置換・バックアップ経路へ進みます（`terminal/strata_cli/launch/harness.py:374-387`）。

一致した場合、書き込みとバックアップは行いません。ただし dry-run でない場合は、ファイルを秘密情報を含み得るファイルとして扱い、権限を `0600` に変更しようとします。権限変更に失敗しても無視されます（`terminal/strata_cli/launch/harness.py:378-384`）。

## 適用条件と副作用

- 対象は `strata connect` のみです。`--write` では確認を経た書き込み、`--dry-run` では書き込みなしの予定表示に適用されます（`terminal/strata_cli/launch/cmd.py:163-183`、`terminal/strata_cli/launch/cmd.py:1023-1050`）。
- `--if-unchanged` は確認を省略しません。`--write` で `--yes` も `--dry-run` もない場合、非対話入力では終了コード 2 で拒否され、対話時は確認します（`terminal/strata_cli/launch/cmd.py:1024-1038`）。
- `--check` と併用し、接続チェックに失敗すると、その後の書き込み処理は行われません（`terminal/strata_cli/launch/cmd.py:1087-1107`、`terminal/strata_cli/launch/cmd.py:1147-1157`）。
- 一致しない既存ファイルは通常経路で置換され、既定の `backup=True` により `.strata-bak-<時刻>` のバックアップが作られます。存在しないファイルは新規作成されます（`terminal/strata_cli/launch/harness.py:355-360`、`terminal/strata_cli/launch/harness.py:387-399`）。
- 既存ファイルを読み取れず一致を確認できない場合、比較時の `OSError` は無視され、通常の書き込みを試みます（`terminal/strata_cli/launch/harness.py:385-386`）。

## 出力とエラー

成功時は人間向け出力で `Unchanged <path>`、JSON 出力では `write.written` の該当要素に `"action": "unchanged"` と `"backup": null` が記録されます（`terminal/strata_cli/launch/cmd.py:1108-1118`、`terminal/strata_cli/launch/cmd.py:1156-1162`）。dry-run でも一致時の action は `unchanged` です。dry-run 以外では一致時に権限変更を試みます。

ファイル書き込み時に `OSError` が発生すると、そのファイルは `failed`、後続のファイルは `not_written` として記録され、終了コード 1 になります。人間向けでは `strata: Could not write ...` を stderr に出し、JSON 出力では `ok: false` とエラー情報を含めます（`terminal/strata_cli/launch/cmd.py:1039-1050`、`terminal/strata_cli/launch/cmd.py:1111-1115`、`terminal/strata_cli/launch/cmd.py:1162-1167`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser とフラグの定義。値なしの `store_true` で、`--write`・`--dry-run` とは独立して登録。
- `terminal/strata_cli/cli.py:2235-2237` — `connect` が `run_connect` に渡される CLI の実行経路。
- `terminal/strata_cli/launch/cmd.py:1019-1050` — 書き込み前の確認、dry-run 条件、フラグの転送、書き込み失敗と終了コード。
- `terminal/strata_cli/launch/cmd.py:1087-1119`、`terminal/strata_cli/launch/cmd.py:1147-1168` — チェック失敗時の書き込み抑止と、人間向け・JSON 出力。
- `terminal/strata_cli/launch/harness.py:355-399` — 最終内容の生成、merge 後のバイト比較、一致時の権限変更、バックアップ・置換・新規作成。
