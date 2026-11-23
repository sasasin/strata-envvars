# `--output`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models explain` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。既定値は `human` |

## 役割

モデルファイルの検索結果を、人が読む説明文か機械処理用 JSON のどちらで stdout に出すかを選びます。出力先ファイルの指定ではありません。検索対象やモデルフォルダーの選択は変えません。

## 使い方

```sh
strata models explain qwen/IQ3_S --output json
```

モデル名に family を含める形式を使い、結果を JSON で標準出力に表示します。既定の説明文を表示する場合は `--output` を省略するか、`--output human` を指定します。

## 値と既定値

parser は `choices=("human", "json")`、`default="human"` として定義しています。ほかの値は argparse の引数検証で拒否されます。`--output` 自体は `strata models explain` parser に登録されており、別の `models` サブコマンドの設定を共有するものではありません。また、この parser に `--json` は登録されていません。（`terminal/strata_cli/cli.py:178-182`）

## 実行時の動作

`human` の場合、検索結果を `models_explain.words()` で複数行の説明に整形して stdout に出します。`json` の場合、同じ検索結果の辞書を `{"schema_version": 1, "ok": true, ...}` の形で JSON 化して stdout に出します。結果のデータには family、model、検索したフォルダー、見つかった GGUF ファイルなどが含まれます。どちらの形式でも検索処理は `models_explain.explain()` を通ります。（`terminal/strata_cli/cli.py:581-589`、`terminal/strata_cli/cli.py:566-573`、`terminal/strata_cli/models_explain.py:23-61`）

エラー時も指定形式で違いがあります。認識できないモデル名、またはモデルに対応しない family の場合、`human` は `strata: <エラー>` を stderr に出し、`json` は `{"schema_version": 1, "ok": false, "error": {"code": 2, "message": ...}}` を stdout に出します。いずれも終了コードは 2 です。（`terminal/strata_cli/cli.py:558-563`、`terminal/strata_cli/cli.py:583-589`、`terminal/strata_cli/launch/catalog.py:550-572`）

## 適用条件と副作用

`--output` は結果の表示形式だけに作用します。モデル名の解決、インストール済み run config などに基づく data folder の選択、フォルダー候補の調査、および `.gguf` ファイルのサイズ取得は両形式で共通です。（`terminal/strata_cli/models_explain.py:28-61`、`terminal/strata_cli/launch/catalog.py:586-621`）

調査は読み取り専用です。コードはフォルダーを列挙し、ファイル名・サイズなどを読むだけで、ダウンロードや書き込みは行いません。フォルダー列挙・stat 時に `OSError` が発生した場合は、その箇所では例外を握りつぶして結果を組み立てます。（`terminal/strata_cli/models_explain.py:3-5`、`terminal/strata_cli/models_explain.py:40-55`）

## 出力とエラー

成功時は終了コード 0 で stdout に出力します。`human` は説明文、`json` は1行の JSON です。JSON の成功応答には `schema_version: 1` と `ok: true` が付きます。（`terminal/strata_cli/cli.py:566-573`、`terminal/strata_cli/cli.py:589`）

不正な format 値は argparse の choices 検証で拒否されます。モデルや family の解決に失敗した場合は終了コード 2 で、エラー出力先は上記のとおり `human` では stderr、`json` では stdout です。（`terminal/strata_cli/cli.py:182`、`terminal/strata_cli/cli.py:558-563`、`terminal/strata_cli/cli.py:583-589`）

## 根拠

- `terminal/strata_cli/cli.py:178-182` — `models explain` の parser と `--output` の選択肢・既定値。
- `terminal/strata_cli/cli.py:581-589` — オプション値による成功・失敗時の分岐。
- `terminal/strata_cli/cli.py:558-573` — エラー形式、成功応答の JSON wrapper、stdout/stderr、終了コード。
- `terminal/strata_cli/models_explain.py:23-61` — 検索結果の生成と JSON payload の項目、ファイル調査。
- `terminal/strata_cli/launch/catalog.py:550-572` — モデル名と family の解決・失敗条件。
- `terminal/strata_cli/launch/catalog.py:586-621` — launch と共通のモデルフォルダー検索規則。
