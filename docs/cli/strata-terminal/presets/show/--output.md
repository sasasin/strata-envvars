# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets show` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

取得した tuning preset 全体を表示する形式を選びます。`--output` は `strata presets` の各サブコマンドに共通して登録されていますが、この文書では索引上のスコープである `strata presets show` の動作を説明します。

## 使い方

```sh
strata presets show <preset名またはID> --output json
```

`<preset名またはID>` は `show` の位置引数です。`--output` を省略すると `human` です。

## 値と既定値

- `human`、`json` のいずれかを指定します。大文字小文字を変えた値や他の文字列は `argparse` の `choices` 検証で拒否されます。
- 既定値は `human` です。空文字列も選択肢にないため受理されません。
- 同じオプションを複数回指定した場合の個別処理は実装されていません。通常の `argparse` の単一値引数として解析され、後に現れる指定値が残ります。

## 実行時の動作

`human` と `json` の違いは JSON 表現の包み方です。`human` では preset の全データを整形した JSON（インデント付き）で stdout に出します。`json` では `schema_version: 1` と `ok: true` を含む一行 JSON オブジェクトの `preset` フィールドに同じデータを入れます。いずれも preset を検索して表示するだけで、設定の適用や保存は行いません。

検索は preset の完全な ID、4 文字以上の ID 接頭辞、または大文字小文字を区別しない完全一致の名前で行います。複数一致する名前・接頭辞は曖昧としてエラーになります。preset ディレクトリが存在しない場合、または保存ファイルが不正・別 schema の場合は一覧に含まれず、検索できません。

表示するレコードは保存された preset 全体です。内容には tuning 設定、計測結果、ユーザーが選んだ条件、ハードウェア・engine・model の識別情報などが含まれ得ます。JSON をログや他者と共有する場合は、含まれる情報を確認してください。

## 適用条件と副作用

このオプションは `strata presets show` の出力形式に適用されます。コマンドは preset store と active index を読み、一覧化時に保存レコードへ `active` 状態を付加します。ソース上、`show` の成功経路でファイルを書き換える処理、engine 起動、ネットワーク通信は確認できませんでした。

## 出力とエラー

- 成功時は終了コード `0` です。`human` は整形 JSON、`json` は機械処理向けの一行 JSON を stdout に出力します。
- preset が見つからない、または参照が複数 preset に一致する場合、`human` は `strata: <説明>` を stderr に出して終了コード `5`、`json` は `schema_version: 1`、`ok: false`、`error.code: 5` とメッセージを含む JSON を stdout に出して終了コード `5` です。
- 検索で `PresetError` 以外の `OSError` / `ValueError` が処理まで伝播した場合は、`presets_command` の例外処理で失敗出力に変換されます。通常の `OSError` は終了コード `2`（例外に `exit_code` があればその値）です。一方、保存 JSON の読み込み helper は `OSError` と JSON decode error を捕捉して既定値を返すため、読めない・壊れた preset ファイルは通常検索結果から除外され、preset 未検出のエラーになります。
- 値が `human` / `json` 以外ならコマンド本体より前の parser 検証に失敗し、argparse の usage/error 表示と終了コード `2` になります。

## 根拠

- `strata_cli/tune_commands.py:49-62` — `presets show` parser と `--output` の選択肢・既定値、preset 位置引数。
- `strata_cli/tune_commands.py:95-108` — 成功・失敗時の human / JSON 出力と終了コード。
- `strata_cli/tune_commands.py:289-309,344-348` — `--output` の分岐、`show` が `presets.find()` を呼び全レコードを表示する経路、例外処理。
- `strata_control/presets.py:202-215,218-231` — active index と保存レコードの読み込み、ID・接頭辞・名前の検索、未検出・曖昧時のエラー。
- `strata_control/presets.py:71-75,234-252` — JSON 読み込み失敗時の既定値、schema が一致する保存レコードの列挙、active 状態の付与。
- `strata_control/presets.py:1-17` — preset に格納される情報の種類と、この store が変更する範囲。
- `strata_cli/cli.py:487,2151-2152` — parser 登録と `presets_command` への dispatch。

調査範囲は上記 revision のソース checkout です。同一 revision の実行 CLI help や Release 配布物は補助資料として確認していません。
