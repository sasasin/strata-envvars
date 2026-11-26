# `strata presets export --file`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets export` |
| オプション | `--file` |
| 別名 | なし |
| 値 | 出力先パスを取る。文字列として受け取り、Strata 側で形式検証しない |

## 役割

保存済み tuning preset を JSON ファイルへ書き出します。`--file` を省略した場合はファイルを書かず、preset JSON を標準出力へ表示します。これは `strata presets export` の保存先を選ぶオプションで、preset の有効化や起動時設定の変更は行いません（`terminal/strata_cli/tune_commands.py:79-81,514-520`）。

## 使い方

```sh
strata presets export "Office preset" --file ./office-preset.json
```

`preset` には名前、ID、または4文字以上の一意な ID prefix を指定できます。名前は大文字小文字を区別せず、同名の候補が複数ある場合は名前検索が優先されます（`terminal/strata_control/presets.py:243-256`）。

## 値と既定値

- `--file` は値を1つ取ります。parser は `type` や `choices` を指定せず、既定値は `None` です（`terminal/strata_cli/tune_commands.py:79-81`）。
- 未指定時は `None` のままなのでファイルには書かれません。空文字列を明示した場合も実行時の真偽判定を通らず、ファイル出力ではなく標準出力の経路になります（`terminal/strata_cli/tune_commands.py:516-520`）。
- Strata 側にパス形式の検証や独自の重複指定処理はありません。複数回指定時にどの値が残るかは parser の標準動作に委ねられています（`terminal/strata_cli/tune_commands.py:79-81`）。

## 実行時の動作

- まず `preset` を保存済み preset から解決します。完全 ID、名前、ID prefix の順で候補を調べ、見つからない場合や複数に一致する場合は失敗します（`terminal/strata_control/presets.py:243-256`）。一覧取得時に付加された `active` フィールドは export データから除かれます（`terminal/strata_control/presets.py:259-275,417-420`）。
- `--file PATH` が空でなければ、`Path(PATH).write_text(...)` で JSON を UTF-8、インデント2、非 ASCII 文字をエスケープしない形式で書き込みます。相対パスはプロセスの作業ディレクトリを基準に解決されます（`terminal/strata_cli/tune_commands.py:516-518`）。
- 書き込みは直接行われます。既存ファイルは置き換わり、親ディレクトリはこの処理では作成されません（`terminal/strata_cli/tune_commands.py:516-518`）。
- 共通の `--output` は `human`（既定）または `json` を受け取ります。ファイル指定時は、`human` なら `Wrote <path>`、`json` なら `{"schema_version":1,"ok":true,"file":"<path>"}` 形式の応答を標準出力へ出します。`--file` を省略または空文字にした場合は、`--output` の値に関係なく preset JSON 本文を標準出力へ出します（`terminal/strata_cli/tune_commands.py:59-61,101-106,514-520`）。

## 適用条件と副作用

`--file` を指定したときだけファイル書き込みが発生し、同名ファイルの内容を置き換えます。親ディレクトリがない、書き込み権限がないなどの `OSError` はエラー経路になります。export は preset の保存データや active index を更新せず、エンジンも起動しません（`terminal/strata_cli/tune_commands.py:514-530`、`terminal/strata_control/presets.py:417-420`）。

## 出力とエラー

- preset が見つからない場合は `PresetError` として扱われ、終了コード `5` になります。複数一致時も ID の指定を求めて同じエラー経路になります（`terminal/strata_control/presets.py:252-255`、`terminal/strata_cli/tune_commands.py:527-528`）。
- ファイル書き込みなどの `OSError` は、human 出力では `strata: <エラー>` を標準エラーへ、JSON 出力では `ok:false` の JSON を標準出力へ出します。終了コードは例外の `exit_code` があればその値、なければ `2` です（`terminal/strata_cli/tune_commands.py:109-114,527-530`）。
- 成功時、ファイルを指定しない場合は整形済み preset JSON を標準出力へ直接出し、終了コード `0` を返します。ファイル指定時も成功応答の後に終了コード `0` を返します（`terminal/strata_cli/tune_commands.py:516-520`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61,79-83` — `strata presets export` の parser、必須位置引数 `preset`、`--file` の既定値、および `--output` の選択肢。
- `terminal/strata_cli/tune_commands.py:101-114,472-477,514-530` — JSON/human 応答、標準出力・ファイルへの出力分岐、書き込み、失敗時の表示と終了コード。
- `terminal/strata_control/presets.py:243-256,259-275,417-420` — preset の検索、active 状態の付与と export 対象からの除外。
- `docs/cli/README.md:804-808` — 索引上のコマンド階層と `--file` のスコープ。
