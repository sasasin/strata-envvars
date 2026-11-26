# `strata tune auto --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

自動チューニングの進捗・結果・エラーを、人向け表示または JSON で出力します。省略時は `human` です。チューニング対象や試行内容、プリセット保存の判断は別の引数と実行結果で決まり、このオプションは出力形式を選びます。

## 使い方

```sh
# 進捗と結果を人向けに表示する（既定値）
strata tune auto IQ3_S

# 結果を JSON として標準出力へ出す
strata tune auto IQ3_S --output json

# 実行せず、予定を JSON で確認する
strata tune auto IQ3_S --plan --output json
```

`target` にはインストール済みモデル名、保存済みプロファイル名、または実行設定 JSON を指定できます。 (parser: `terminal/strata_cli/tune_commands.py:27`)

## 値と既定値

- `human` と `json` のみ受理され、既定値は `human` です。短縮別名はありません。 (`terminal/strata_cli/tune_commands.py:21-50`)
- `human` では結果を人向けテキストにし、実行中の進捗メッセージは標準エラーへ出します。 (`terminal/strata_cli/tune_commands.py:358-369,421-424`)
- `json` では進捗メッセージを `say` から出さず、最終結果を標準出力に1行の JSON として出します。 (`terminal/strata_cli/tune_commands.py:314,358-360,421-424`)
- `--plan` の場合も選択した形式が使われます。JSON は `_print` の `schema_version: 1`, `ok: true`, `plan` を含むオブジェクトです。 (`terminal/strata_cli/tune_commands.py:349-353,101-106`)

## 実行時の動作

コマンド登録時に `--output` は `choices=("human", "json")`、既定値 `human` として追加されます。`strata tune auto` の処理は `a.output == "json"` を機械可読モードとして使い、通常のチューニング処理へ進みます。 (`terminal/strata_cli/tune_commands.py:21-50,309-315`; `terminal/strata_cli/cli.py:514-515,1722-1723`)

JSON 成功時は `schema_version: 1`, `ok: true`, `result` を含むオブジェクトを標準出力へ出します。人向け成功時は `_human_result` の要約を出力します。どちらの形式でも、チューニングが改善または既定設定の確認に至り `--no-save` が指定されていなければプリセット保存を試みます。したがって `--output` の値は保存動作を切り替えません。 (`terminal/strata_cli/tune_commands.py:408-425`)

エラー経路では `json` は `schema_version: 1`, `ok: false`, `error`（`code`, `message`）を標準出力へ出し、人向け形式は `strata: ...` を標準エラーへ出します。両方とも `_fail` が返す終了コードは同じです。 (`terminal/strata_cli/tune_commands.py:109-114,314-338`)

## 適用条件と副作用

`--output` 自体は形式選択で、チューニングの測定やプリセットの保存条件を変更しません。`--status-file` が指定されている場合の進捗 JSON ファイル更新は別経路で、`--output` の値にかかわらず進捗時と完了時に行われます。書き込みは一時ファイルから置換し、`OSError` は無視します。 (`terminal/strata_cli/tune_commands.py:240-248,362-369,419-420`)

対象の読み込みや適用可否など、処理前の失敗も選択された形式で報告されます。無効な値は parser の `choices` に合わず、コマンド処理に入る前に拒否されます。 (`terminal/strata_cli/tune_commands.py:21-50,314-338`)

## 出力とエラー

- `human` の進捗は標準エラー、最終結果は標準出力に出ます。成功時には保存済みチューニング記録への案内が付く場合があります。 (`terminal/strata_cli/tune_commands.py:358-369,417-425`)
- `json` は進捗行を出さず、最終結果または `_fail` のエラーオブジェクトを標準出力に出します。 (`terminal/strata_cli/tune_commands.py:358-360,421-424,109-114`)
- `_fail` を通るエラーはその箇所のコードを終了コードにします。チューニング完了後は `improved`、`default_confirmed` が `0`、`cancelled` が `130`、それ以外の結果が `6` です。 (`terminal/strata_cli/tune_commands.py:109-114,425`)

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` の parser と `--output` の選択肢・既定値。
- `terminal/strata_cli/cli.py:514-515,1722-1723` — tune サブコマンドへの parser 登録と `auto` 処理のディスパッチ。
- `terminal/strata_cli/tune_commands.py:101-114,309-338` — JSON/人向けの成功・失敗出力選択と、処理前エラーの経路。
- `terminal/strata_cli/tune_commands.py:349-353,358-369,408-425` — plan、進捗、チューニング後の保存・結果出力・終了コード。
- `terminal/strata_cli/tune_commands.py:240-248,362-369,419-420` — `--status-file` の独立した進捗書き込み処理。

調査範囲: 同一 revision の Strata ソースにある parser、dispatch、出力処理を確認しました。CLI `--help` は補助資料として実行していません。
