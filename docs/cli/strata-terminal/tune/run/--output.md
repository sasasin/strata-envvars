# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

チューニング実行結果を標準出力に人向け表示するか、機械処理向け JSON で出すかを選びます。結果ファイルの保存先を指定するオプションではありません。

## 使い方

```sh
strata tune run --engine /path/to/strata-engine --backend cuda --model example --output json
```

`--engine`、`--backend`、`--model` は必須です。この例は構文例であり、実行すると測定ジョブが開始します。

## 値と既定値

- `human`: 人向けの進捗・結果説明を標準出力へ表示します（既定値）。
- `json`: 結果オブジェクトを JSON で一度だけ標準出力へ表示します。
- 他の値は parser の `choices` により拒否されます。値を省略した場合は `human` です。短縮別名や複数回指定時の特別な処理は定義されていません。

## 実行時の動作

parser はこのオプションを `strata tune run` に登録し、`human` / `json` のみを受理して既定値を `human` にします（`strata_cli/cli.py:414-459`）。実行時には `json` 以外の場合に測定対象の次元、モード、上限などを表示し、ジョブ完了後にジョブ ID、測定結果、推薦の有無などを人向けに表示します（`strata_cli/cli.py:1788-1800`, `1808-1846`）。

`json` の場合、進捗・人向け説明を省略し、完了したジョブを `{ "schema_version": 1, "ok": true, "job": ... }` 形式で標準出力へ出します（`strata_cli/cli.py:1802-1806`, `527-542`）。JSON 表示のために `allow_nan=False` が使われるため、JSON 化できない値があれば通常の例外処理経路へ進みます（`strata_cli/cli.py:535-542`）。

この値はジョブの状態・レポート保存形式を選びません。ジョブは `Tuner` が state directory 内に `job.json` として保存し、標準の保存先は `--state-dir`、環境変数 `STRATA_TUNE_DIR`、または state base 配下の `tuning` の順で決まります（`strata_control/tuning.py:320-362`, `strata_cli/cli.py:1643-1650`）。

## 適用条件と副作用

このオプションは、API を通す `--mode api` とエンジン独自 serve protocol を使う既定の `--mode protocol` のどちらにも適用されます。測定方法自体は `--mode` が選び、`--output` は表示形式だけを切り替えます（`strata_cli/cli.py:431-445`, `1771-1786`, `1788-1806`）。

出力形式に関係なく、コマンドは測定ジョブを実行して状態を保存します。GPU/backend の排他 lease が必要な計画では lease ファイルを作成し、終了時に削除します。ジョブ状態はジョブ固有のディレクトリに保存されます（`strata_control/tuning.py:335-362`, `387-419`, `423-484`）。`--output json` 自体は設定プロファイルを変更しません。適用は別の `strata tune apply` 操作です（`strata_cli/cli.py:1840-1846`）。

## 出力とエラー

- `human` では通常の説明を stdout に、測定次元がない旨などの注意を stderr に出す場合があります（`strata_cli/cli.py:1788-1800`, `1808-1846`）。
- `json` では成功結果を stdout に JSON 1行で出力します。事前条件エラーも `--output json` に応じて `{ "schema_version": 1, "ok": false, "error": ... }` 形式になり、通常の人向けエラーは stderr に出ます（`strata_cli/cli.py:1761-1779`, `527-542`）。
- `--engine` の実行ファイルが存在しない、`--mode api` で `--config` または `--api-expect` がない場合は、ジョブ実行前にエラーとなり終了コード 2 を返します（`strata_cli/cli.py:1759-1779`）。
- `human` / `json` 以外の値は argparse の選択肢検証により拒否されます。argparse の不正引数経路では usage/error が stderr に出て終了コード 2 になります（`strata_cli/cli.py:459`, `2223-2235`）。
- チューニング中に例外が起きた場合、`Tuner.run()` はジョブを `failed` として保存し、結果オブジェクトを返します。CLI はその結果を指定形式で出力します（`strata_control/tuning.py:423-484`, `strata_cli/cli.py:1802-1806`）。

## 根拠

- parser、値の制約と既定値: `strata_cli/cli.py:414-459`
- コマンド dispatch と `--output` 分岐、モードごとの測定選択: `strata_cli/cli.py:1708-1709`, `1742-1806`
- 成功・エラー出力形式と終了コード: `strata_cli/cli.py:527-542`, `1761-1779`, `1805-1847`
- ジョブ永続化と失敗結果の保存: `strata_control/tuning.py:320-362`, `423-484`
- 保存先の既定値と優先順: `strata_cli/cli.py:1643-1650`
