# `strata connect --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。省略時は `human` |

## 役割

`strata connect` が対応アプリの一覧またはアプリ向け接続設定を表示するとき、出力を人間向け表示にするか、機械処理向け JSON にするか選びます。設定ファイルの書き込みやサーバー確認を有効にするオプションではなく、`--check`・`--write`・`--dry-run` の処理自体はこの値で切り替わりません（`terminal/strata_cli/launch/cmd.py:163-183,1052-1119,1120-1167`）。

## 使い方

```sh
# OpenCode 用設定を JSON として標準出力へ表示する
strata connect opencode --output json

# 対応アプリ一覧を JSON として取得する
strata connect --output json

# 確認処理の結果も JSON に含める
strata connect opencode --check --output json
```

## 値と既定値

値は `human` と `json` のいずれかで、既定値は `human` です。`argparse` の `choices` による検証で、他の値は受理されません。短縮別名、繰り返し指定のための特別な処理、`connect` における `--json` 別名は定義されていません（`terminal/strata_cli/launch/cmd.py:163-183`）。

## 実行時の動作

`human` では、アプリ一覧を表形式で表示し、個別アプリの場合は生成される設定ファイルの内容、環境変数、注意事項などを人間向けの文言で表示します。`json` では、一覧を `schema_version: 1` と `harnesses` を含む JSON オブジェクトとして返し、個別アプリでは設定情報と `files`、`vendor_tested` などを JSON オブジェクトとして標準出力に返します。JSON のファイル内容と文字列値は API キーが含まれていればマスクされます（`terminal/strata_cli/launch/cmd.py:1052-1066,1082-1086,1118`）。

`--check` を併用すると JSON に `checks`、`checked_server`、総合判定 `ok` が含まれ、失敗時は `error` も追加されます。失敗時の終了コードは `1` です。`--write` または `--dry-run` を併用すると JSON に書き込み結果が含まれます。`--write` の確認が必要な場合、確認プロンプトは標準エラーへ出し、JSON 本体は標準出力に保たれます（`terminal/strata_cli/launch/cmd.py:1087-1118,1019-1050`）。

## 適用条件と副作用

このオプションは `strata connect` の出力分岐に適用され、`strata launch` など別コマンドの同名オプションとは別スコープです（parser: `terminal/strata_cli/launch/cmd.py:73-80,163-183`）。`--output json` 単独ではファイルを書き換えず、書き込みは `--write`、プレビューは `--dry-run` によって行われます（`terminal/strata_cli/launch/cmd.py:1108-1118,1156-1167`）。

JSON 出力では `--show-key` を併用してもキーはマスクされます。`run_connect` は JSON 分岐で設定内容を `harness.mask` に通しており、`--show-key` の値を使うのは human 分岐だからです（`terminal/strata_cli/launch/cmd.py:1081-1086,1120-1127`）。

## 出力とエラー

不正な値は parser の選択肢検証で拒否されます。`strata` は `parse_known_args` の後に connect の未知引数を独自メッセージとして標準エラーに出し、終了コード `2` を返します（`terminal/strata_cli/launch/cmd.py:182`; `terminal/strata_cli/cli.py:2325-2334`）。不明なアプリ名も標準エラーに案内を出して `2` を返し、`--output json` で JSON 形式には変換されません（`terminal/strata_cli/launch/cmd.py:1067-1073`）。

JSON モードで `--check` が失敗した場合は、失敗結果を含む JSON を標準出力へ出して終了コード `1` を返します。書き込み時にファイル操作が失敗した場合も、失敗ファイルと後続の未書き込みファイルを示す JSON を出し、コード `1` で終了します（`terminal/strata_cli/launch/cmd.py:1093-1118,1039-1049`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser と `--output` の `choices=("human", "json")`、既定値 `human`。
- `terminal/strata_cli/cli.py:516-517,2235-2237` — `connect` parser の登録と `run_connect` への dispatch。
- `terminal/strata_cli/launch/cmd.py:1052-1066` — 一覧表示における human / JSON 分岐。
- `terminal/strata_cli/launch/cmd.py:1074-1086,1120-1136` — 個別 harness の JSON / human 出力とキーのマスク。
- `terminal/strata_cli/launch/cmd.py:1087-1119,1147-1167` — check と write / dry-run の出力・終了経路。
- `terminal/strata_cli/launch/cmd.py:1019-1050` — 書き込み時の確認、ファイルエラー、終了コード。
- `terminal/strata_cli/cli.py:2325-2334` — parser 後の未知引数のエラー処理。
