# `strata engine calibrate --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--output` |
| 別名 | なし（`--json` は同コマンドに追加される別の真偽値オプション） |
| 値 | `human` または `json`。既定値は `human` |

## 役割

標準出力の表現形式を選ぶ。`json` は機械処理向けの JSON、`human` は人向けの出力を使う。較正レポートの保存先を指定するオプションではなく、`--measure` のレポートファイル名は別の `--out` が受け持つ。

## 使い方

```sh
# 読み取り専用の較正事前確認を JSON で表示
strata engine calibrate --profile four-gpu --plan --output json

# 較正結果の適用可否を JSON で確認
strata engine calibrate --profile four-gpu --review-result /absolute/path/calibration.json --output json
```

## 値と既定値

parser は `choices=("human", "json")` と `default="human"` を指定しているため、省略時は `human`、指定できる値はこの2つに限られる。同一オプションを複数回指定した場合の個別処理は実装されておらず、argparse の値設定に委ねられる。`jsonl` やファイルパスなど他の値は parser が拒否する。較正 action は `--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のいずれか1つが必須で、相互排他である（`terminal/strata_cli/cli.py:204-217`）。

## 実行時の動作

`--output human` の場合、事前確認は要約行を出力する。計測・適用・rollback は完了メッセージを出す一方、結果確認 (`--review-result` / `--review-rollback`) は整形済み JSON を出力する。したがって `human` は全 action をプレーンテキスト化する指定ではない（`terminal/strata_cli/cli.py:1121-1123`, `1124-1133`, `1144-1151`, `1159-1161`, `1162-1174`）。

`--output json` では標準出力に JSON を出す。成功形式は action ごとに `plan`、`report`、`review`、`rollback_review`、`application` または `rollback` を含む。結果確認時は `ok` が `applicable` に連動し、適用不可なら終了コード 6 となる。事前確認では component preflight の `ok` が結果と終了コードに反映され、失敗時は終了コード 5。計測・適用・rollback の人向け進捗出力は標準エラーへ振り分けられ、最終結果は指定形式で標準出力へ出る（`terminal/strata_cli/cli.py:1101-1102`, `1113-1123`, `1124-1161`, `1162-1174`）。

同コマンドでは `--json` も利用でき、parser 後の処理で `--output json` と同じ設定に変換される。これは `--output` の別名ではなく独立した alias オプションである（`terminal/strata_cli/cli.py:539-547`, `2335-2338`）。`--output` の値は較正の選択・計測・レポートファイルの生成や構成変更を切り替えず、出力表現だけを選ぶ。較正 action の処理では `a.output == "json"` を表示分岐に使う（`terminal/strata_cli/cli.py:1098-1102`, `1121-1174`）。

## 適用条件と副作用

このオプションは `strata engine calibrate` のみで有効。`--measure` のレポート保存先は `--out` で指定し、既存ファイルまたはシンボリックリンクがある場所には保存を拒否するため、`--output json` をファイル出力先として指定しても意味しない（`terminal/strata_cli/cli.py:215-217`, `strata_control/calibration.py:289-296`）。

## 出力とエラー

`--output` を省略すると人向け形式となり、`json` を指定すると JSON 形式になる。値が選択肢外の場合は argparse が拒否する。実行中の `ValueError`、`OSError`、`ClientError` などは、JSON 指定時には `{schema_version, ok: false, error: {code, message}}` 形式を標準出力に出し、人向け指定時には `strata: ...` を標準エラーに出す共通経路がある（`terminal/strata_cli/cli.py:558-563`, `2248-2275`）。action 固有の拒否条件や終了コードは出力形式にかかわらず適用される。

## 根拠

- `terminal/strata_cli/cli.py:202-217` — `engine calibrate` parser、action の相互排他、`--output` の値と既定値。
- `terminal/strata_cli/cli.py:539-547`, `2335-2338` — `--json` を追加し、`--output json` に変換する処理。
- `terminal/strata_cli/cli.py:558-573` — 共通の人向けエラー、JSON エラー、JSON 成功出力。
- `terminal/strata_cli/cli.py:1098-1174` — calibrate の各 action が形式ごとに出す内容、進捗の stderr 振り分け、終了コード。
- `terminal/strata_control/calibration.py:289-296` — 計測レポート出力先の既存ファイル・ディレクトリ検査。`--output` が保存先指定ではないことの関連根拠。
