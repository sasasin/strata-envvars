# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `false` |

## 役割

レシピ作成結果を、人向けの短いメッセージではなく機械処理向け JSON で標準出力へ出します。作成処理そのものやレシピ内容は変更しません。

## 使い方

```sh
strata ops create weekly-check --profile default --kind components.verify --json
```

`--profile` と `--kind` は必須です。`--kind` は `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれかを指定します。`--json` は `strata ops create` の parser に登録されたフラグです。

## 値と既定値

値を取りません。parser 上の既定値は `false` で、指定すると `true` になります。共通の `--output {human,json}` も同じサブコマンドにあり、既定値は `human` です。`--json` を指定した場合、`--output human` を併記しても起動処理で `output` が `json` に設定されます。

`--kind` が未指定または選択肢外の場合、argparse が引数エラーとして usage を標準エラーへ表示し、終了コード 2 で終了します。これは `--json` による JSON エラー応答より前の parser 段階です。

## 実行時の動作

`--json` は one-shot parser 群に共通追加されます。起動時に `a.json` が真なら（`strata ops` を含む通常の one-shot コマンドでは）`a.output = "json"` となり、`_ops` は `machine=True` として作成処理を実行します。

成功時は標準出力に1行の JSON を出し、終了コード 0 を返します。応答には `schema_version: 1`、`ok: true`、`recipe`、`revision` が含まれます。`recipe` は保存されたレシピ、`revision` はその内容の revision です。

このフラグは表示形式を選ぶものですが、`create` はローカルファイルを新規作成します。レシピは profile 配下の `.ops/<profile>/<name>.json` に保存され、ファイルは排他的な新規作成で開かれるため、同名レシピを上書きしません。既定パラメーターは kind ごとに設定されます。`runtime.restart` は `startup_wait_s: 300`、`engine.calibrate.measure` は profile ディレクトリ内の `.reports` を指す `report_dir`、`components.verify` は空の `params` です。

## 適用条件と副作用

対象は `strata ops create` です。`--output json` も機械出力にできます。両方を指定しても別の処理にはなりません。`--quiet` は同じ parser に追加されますが、JSON 出力時は通常の `_run` 経路に進み、JSON 応答は出力されます。

指定した profile は既に有効な profile として読み込める必要があります。profile 名とレシピ名はいずれも小文字英字で始まり、小文字英字・数字・`_`・`-` を使う最大64文字です。作成先の `.ops` ディレクトリは必要に応じて作成され、POSIX では owner-only の権限が検査されます。レシピファイルは mode `0600` で排他的に作成・書き込みされます。

## 出力とエラー

`--json` が有効な実行時エラーは、`schema_version: 1`、`ok: false`、`error: {code, message}` の JSON を標準出力へ出します。存在しない profile、無効な profile/name、既存レシピ、保護条件を満たさないディレクトリなどは失敗経路です。既存レシピは拒否され、上書きされません。基礎処理の `ProfileError` は設定された終了コード（既定 2、保護・読取系では 5 など）で返ります。ファイルシステムの `OSError` は CLI の一般エラー処理で終了コード 6 として扱われます。

## 根拠

- parser と `--output` の既定値・`--kind` の必須選択肢、共通 `--json` 登録: `strata_cli/cli.py:255-272`, `strata_cli/cli.py:508-515`
- `--json` から JSON 出力への切替: `strata_cli/cli.py:2223-2237`
- `ops create` の呼び出しと成功ペイロード: `strata_cli/cli.py:1391-1415`
- JSON 成功・失敗の出力形式: `strata_cli/cli.py:527-542`
- recipe kind の既定値と validation: `strata_control/recipes.py:28-29`, `strata_control/recipes.py:93-127`
- profile/name 検証、保存先、ディレクトリ保護条件: `strata_control/recipes.py:32-64`
- 排他的な新規作成、権限、既存ファイル拒否、書込失敗時の後始末: `strata_control/recipes.py:130-150`
- recipe 読込時のファイル条件、既定 exit code と検証: `strata_control/recipes.py:180-196`
- `ProfileError` の終了コード規則: `strata_control/profiles.py:30-35`
