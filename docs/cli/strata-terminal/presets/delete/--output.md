# `strata presets delete --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets delete` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

削除結果の表示形式を選びます。`delete` は指定した保存済みチューニング preset を削除する操作で、`--output json` は成功・失敗を機械可読な JSON にします。

## 使い方

```sh
# preset 名または ID を指定して、人向けの結果を表示
strata presets delete "My preset"

# 同じ削除を JSON 結果で受け取る
strata presets delete 01234567 --output json
```

## 値と既定値

- `human`: 既定値です。成功時は削除した preset 名を標準出力へ表示し、失敗時は `strata: <理由>` を標準エラーへ表示します。
- `json`: 成功時は `schema_version: 1`、`ok: true`、削除した preset の完全な ID を含む `deleted` を標準出力へ出します。失敗時は `schema_version: 1`、`ok: false`、`error.code` と `error.message` を含む JSON を標準出力へ出します。
- それ以外の値は parser の `choices` により受理されません。値を省略すると `human` です。

## 実行時の動作

`--output` は `presets` の各サブコマンドに共通登録されますが、この文書の対象スコープは `presets delete` です。削除処理はまず指定値から preset を解決し、その ID を結果用に保持してから削除関数を呼び出します。指定値には完全 ID、4 文字以上の ID prefix、または大文字小文字を区別しない完全な名前を使えます。名前が複数に一致する場合や見つからない場合は削除しません。

削除関数は `active.json` の履歴から対象 ID を取り除きます。削除対象が現在有効なら、履歴の直前の preset を有効に戻し、履歴がなければ active を `null` にします。その後、対象 preset の JSON ファイルを削除します。preset ファイルの unlink で `OSError` が起きても関数内で握りつぶすため、索引更新が済んでいればコマンドは成功結果を返す場合があります。`--output` は削除操作自体や削除対象を変更しません。

```sh
strata presets delete "My preset" --output json
```

成功時の JSON には、短縮形ではなく完全な preset ID が入ります。チューニング対象モデルの設定ファイルやモデルファイルを直接削除する処理は確認できません。

## 適用条件と副作用

- 実行時に preset store を参照します。`STRATA_PRESET_DIR` が設定されていればそのディレクトリ、そうでなければ profile ディレクトリの隣にある `presets/` が store です。
- 削除対象が active または undo 履歴にある場合、`active.json` を更新して active 状態・履歴を調整します。対象 preset の JSON ファイルも削除しようとします。
- preset ファイルの削除失敗は無視されます。一方、索引の保存など他の `OSError` は失敗経路になります。
- preset は Terminal と Desktop app で共有される保存領域にあります。削除により、その preset を共有する側からも参照できなくなります。

## 出力とエラー

- 成功: 終了コード `0`。`human` は `Deleted '<名前>'.`、`json` は `{"schema_version": 1, "ok": true, "deleted": "<完全なID>"}` 相当を標準出力へ出します。
- preset がない、または指定が曖昧: `PresetError` を `error.code: 5`（人向け出力時は終了コード `5`）として返します。
- 索引保存などで `OSError` が発生: 終了コード `2` で失敗応答を返します。人向けでは標準エラー、JSON では標準出力です。
- `--output` に `human` / `json` 以外を指定した場合は argparse の引数エラーとなり、コマンド処理には入りません。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-75`: `presets` の下に `delete` を登録し、共通 `--output` を `human` / `json`、既定値 `human` で定義。`delete` は位置引数 `preset` を取ります。
- `terminal/strata_cli/tune_commands.py:101-114`: 成功・失敗の JSON / 人向け出力形式と終了コード。
- `terminal/strata_cli/tune_commands.py:472-503`: `presets_command` の dispatch、対象の解決、削除呼び出し、成功 payload。
- `terminal/strata_cli/tune_commands.py:527-530`: preset エラーを終了コード `5`、その他の `OSError` / `ValueError` を既定終了コード `2` で返します。
- `terminal/strata_control/presets.py:45-50`: preset store の場所と `STRATA_PRESET_DIR` の適用。
- `terminal/strata_control/presets.py:243-256`: ID・prefix・名前による検索と、不在・曖昧時の失敗。
- `terminal/strata_control/presets.py:401-414`: active index と履歴の更新、preset ファイル削除、および unlink 失敗の握りつぶし。
- `terminal/strata_cli/cli.py:514-515,2229-2230`: parser 登録とトップレベル dispatcher から `presets_command` への接続。
