# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops result` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ JSON 出力を選ぶ別のフラグ） |
| 値 | `human` または `json` |
| 既定値 | `human` |

## 役割

指定した operation ID の journal record を端末向けの整形 JSON、または機械処理向けの一行 JSON で標準出力へ出します。`human` は文章表示ではなく、record をインデント付き JSON として表示します。

## 使い方

```sh
strata ops result 0123456789abcdef0123456789abcdef --profile default --output json
```

`operation_id` は位置引数です。`--profile` は必須で、結果を検索するプロファイルを指定します。

## 値と既定値

- `human`: 既定値です。JSON payload を `indent=2` で表示します。外側の `schema_version` と `ok` は付けません。
- `json`: JSON を一行で出力し、`schema_version: 1` と `ok: true` を含む envelope の中に `record` を格納します。JSON は `ensure_ascii=False`、`allow_nan=False` で生成されます。
- 上記以外の値は `argparse` の `choices` 検証で拒否され、usage とエラーが標準エラーへ出て終了コード 2 になります。

## 実行時の動作

parser は `--output` を `human` / `json` に制限し、未指定時を `human` にします。`ops result` では必須の `operation_id` を受け取り、全 `ops` action 共通の必須 `--profile` と出力指定を登録します。さらに `--json` が `--output json` の alias として登録されます（`strata_cli/cli.py:255-268, 508-514`）。

実行時に `--output json` または `--json` が選ばれると `machine=True` となり、`journal.load(profile, operation_id)` の戻り値が `{"record": ...}` として `_success` に渡されます。`human` の場合も同じ record を取得しますが、`_success` は human 用文言が指定されていないため payload を整形 JSON で出します。`--json` は `output` を `json` に設定します。`--quiet` も登録されています。`--output human --quiet` では成功時の標準出力が抑制されますが、`--output json`（または `--json`）では quiet の捕捉処理を通らず JSON が出力されます（`strata_cli/cli.py:1391-1411, 527-542, 2217-2248`）。

## 適用条件と副作用

operation ID は小文字の16進数字32文字でなければなりません。record は指定 profile の `.ops/<profile>/.runs/<operation_id>.json` から読み込まれ、読み込み時に regular file であること、サイズが64 KiB以下であること、record schema・profile・ID・状態などが妥当であることを検証します。状態が `running` の record は削除・変更せず、返却値に `completion_unverified: true` を付けます（`strata_control/journal.py:25-27, 185-244, 247-251`; profile と journal のディレクトリ解決は `strata_control/recipes.py:38-56, strata_control/journal.py:47-63`）。

このオプション自体は出力形式だけを選びます。`result` action は journal record の読込のみを行い、結果ファイルの作成・更新はしません（`strata_cli/cli.py:1409-1411`）。ただし CLI の共通起動処理では parser 実行前に `private_files.adopt_user_defaults()` を呼びます（`strata_cli/cli.py:2217-2224`）。その関数が必要と判断した権限・所有者の調整は、この出力オプション固有の動作ではありません。

## 出力とエラー

- 成功時の終了コードは 0 です。`human` は整形 JSON、`json` は一行の envelope 形式を標準出力へ出します（`strata_cli/cli.py:527-542`）。
- operation ID の形式不正、record 不在、読込失敗、record 検証失敗などは `ProfileError`（`ValueError` 派生）になり、`--output json` の場合は `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` を標準出力へ出します。`human` の場合は `strata: <message>` を標準エラーへ出します。journal の不在・読込エラーのコードは 5、ID 形式不正時は既定の 2 です（`strata_control/profiles.py:30-35, strata_control/journal.py:60-63, 185-198`; 例外変換は `strata_cli/cli.py:2119-2124, 2166-2183, 527-532`）。
- parser が必須 `--profile` や位置引数を欠く場合、または `--output` に選択肢外の値を渡す場合は、アプリケーションの出力形式処理より前に argparse が拒否し、終了コード 2 と usage を標準エラーへ出します（parser 定義は `strata_cli/cli.py:255-268`）。

## 根拠

- `strata_cli/cli.py:255-268` — `ops result` parser、必須引数、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-514` — `ops` 系 parser への `--json` alias と `--quiet` 登録。
- `strata_cli/cli.py:1391-1411` — `--output` の判定、journal 読込、成功 payload。
- `strata_cli/cli.py:527-542, 2217-2237` — human / JSON 出力、失敗出力、共通起動処理。
- `strata_control/journal.py:47-63, 185-251` — 保存場所、ID・ファイル・record の検証、`running` record の返却。
- `strata_control/profiles.py:25, 30-45` — profile ID の形式、例外型、profile directory の解決。
- 調査対象 revision: `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`。作業状態は `main...origin/main`（`git status --short --branch`）で、追加の変更表示はありません。
