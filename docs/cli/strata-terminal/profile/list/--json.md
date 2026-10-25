# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile list` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らないフラグ |

## 役割

保存済みプロファイルの一覧を JSON で出力します。`profile list` はプロファイルを保存する設定ディレクトリから項目を列挙し、各項目の ID、revision、参照元設定ファイルのパス（または読み込み時のエラー）を返します（`strata_cli/cli.py:964-967`、`strata_control/profiles.py:169-182`）。

## 使い方

```sh
strata profile list --json
```

同じ出力は次のようにも指定できます。

```sh
strata profile list --output json
```

このコマンドに `--output` を指定しない場合は `human` です（`strata_cli/cli.py:75-76`）。コマンド階層とオプションの掲載は[CLI 索引](../../../../README.md)を参照してください。

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、値を取りません。`profile list` 自身の parser には `--output`（選択肢 `human` / `json`、既定値 `human`）が定義され、後段で `profile_list` を含む one-shot parser 群へ `--json` が追加されます（`strata_cli/cli.py:75-76,508-514`）。未指定時は JSON ではありません。複数回指定しても真偽値が有効になるだけで、別の動作は定義されていません。

`--json` と `--output` の両方を指定した場合、`--json` が優先します。main 処理が JSON フラグを検出すると `a.output = "json"` に設定します（`strata_cli/cli.py:2232-2235`）。`--output` に `human` または `json` 以外を渡すと argparse の選択肢検証で拒否されます（`strata_cli/cli.py:76`）。

## 実行時の動作

成功時は標準出力に1行の JSON オブジェクトを出します。外側には `schema_version: 1`、`ok: true`、`profiles` 配列が含まれます（`strata_cli/cli.py:535-542,964-967`）。有効な配列要素は `id`、`revision`、`source_config` を持ちます。revision は profile ファイルの内容の SHA-256 の先頭16桁です（`strata_control/profiles.py:62-64,177-180`）。プロファイルがない場合は `profiles: []` です（`strata_control/profiles.py:169-172`）。

一覧対象は設定ディレクトリ直下の `*.json` のうち、ファイル名の stem が小文字英字で始まり、小文字英字・数字・`_`・`-` からなる1〜64文字の profile ID に一致するものです。ID に一致しないファイル名はスキップされます（`strata_control/profiles.py:25,174-176`）。各候補を読み込んで検証し、有効なものは `id`、`revision`、`source_config` を返します。個別ファイルの読み込みや検証で `ProfileError` が起きた場合、その項目は除外されず `id` と `error` を持つ要素として一覧に残ります（`strata_control/profiles.py:169-182`）。

設定ディレクトリは `STRATA_PROFILE_DIR` があればその値（`~` を展開）、なければ Windows では `%APPDATA%/Strata/profiles`（未設定時はホーム下の `AppData/Roaming/Strata/profiles`）、その他の OS では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` です（`strata_control/profiles.py:38-45`）。`--json` 自体はこの場所を変更しません。

## 適用条件と副作用

このオプションは `strata profile list` の parser にのみ属します。出力形式以外の profile 選択・検証規則は変更しません。`--quiet` も one-shot parser に共通追加されますが、JSON 出力時は main 処理が quiet による標準出力の抑制を行わないため、`--json --quiet` でも JSON は標準出力に出ます（`strata_cli/cli.py:508-515,2232-2243`）。

一覧はプロファイルファイルを読む処理です。Windows でファイルへのアクセスが拒否され、対象がユーザー所有の Strata データ領域にある場合、読み込み helper はアクセス権の修復を試みてから再読込します。この条件では `--json` を付けた一覧でも ACL が変更される可能性があります（`strata_control/profiles.py:150-166,177-180`、`strata_control/private_files.py:442-484`）。通常の成功経路でプロファイルを書き換える処理は一覧関数にはありません（`strata_control/profiles.py:169-182`）。

## 出力とエラー

- 空の一覧も成功で、`profiles` は空配列です（`strata_control/profiles.py:169-172`）。
- 個別プロファイルの `ProfileError` は一覧全体を失敗させず、該当要素の `error` 文字列になります（`strata_control/profiles.py:177-182`）。
- 一覧ディレクトリの走査など、個別 `ProfileError` 以外の `OSError` は共通例外処理に渡り、JSON 形式の `{"schema_version":1,"ok":false,"error":{"code":6,"message":"..."}}` を標準出力へ出して終了コード 6 を返します（`strata_cli/cli.py:527-532,2166-2183`）。
- 不正な `--output` 値や認識されない引数は argparse が拒否します。引数解析エラーは `main` の `_run` より前に処理されるため、このフラグがあるからといって共通 JSON エラー形式になるとは限りません（`strata_cli/cli.py:76,2223-2235`）。

## 根拠

- parser と `--output` 定義: `strata_cli/cli.py:69-76`
- `--json` の one-shot parser への追加: `strata_cli/cli.py:508-514`
- list の JSON / human 出力分岐: `strata_cli/cli.py:958-967`
- `--json` から `output=json` への反映と quiet の扱い: `strata_cli/cli.py:2232-2243`
- 成功・失敗 JSON 出力と例外処理: `strata_cli/cli.py:527-542,2166-2183`
- 設定場所、一覧候補、個別エラーの収集: `strata_control/profiles.py:25,38-45,169-182`
- profile 読み込み時のアクセス修復: `strata_control/profiles.py:150-166`、`strata_control/private_files.py:442-484`

