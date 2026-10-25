# `strata drafting plan --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

計画結果を人向けの文章か機械向け JSON で標準出力に出します。値は出力形式だけを選び、ダウンロード計画や drafter の選択内容は変えません。`strata drafting plan` 自体は取得計画を表示するコマンドです（`strata_cli/drafting_cmd.py:17-30,63-73`）。

## 使い方

```sh
strata drafting plan --output json
```

対象モデルの設定を指定して調べる場合は、たとえば次のように実行します。

```sh
strata drafting plan --config /path/to/run-config.json --output json
```

## 値と既定値

- 省略時は `human` です。
- `human` は通常、人向けの説明を出力します。
- `json` と `jsonl` はどちらも機械向け出力になります。`plan` の実装ではいずれも同じ JSON オブジェクトを一行で出し、JSONL のイベント列にはしません。
- 他の値は parser の `choices` により拒否されます。短縮 alias はありません（`strata_cli/drafting_cmd.py:20-30`）。

## 実行時の動作

`json` / `jsonl` の場合、標準出力には `schema_version: 1`、`ok: true` と計画情報を含む JSON オブジェクトが一行で出ます。計画情報には pack の有無、必要量、保存先、取得元と revision、選択された drafter、判断メモなどが含まれます。`human` の場合は通常、取得量・pack 後の容量などを含む説明文を出します。モデル設定を指定し、選択内容により取得不要で判断メモがある場合は、そのメモを含む短い行を出します（`strata_cli/drafting_cmd.py:63-73`; `strata_control/drafting_fetch.py:29-39`）。

表示する計画内容は `--config`、`--mode`、`--family`、`--data-dir` と現在の drafter pack の状態に基づきます。これらは `--output` の値とは別の入力です。設定ファイルを読めない、または JSON として解釈できない場合、`--config` の内容は空として扱われ、既定のデータフォルダー等を使って計画を続けます（`strata_cli/drafting_cmd.py:40-54`）。

## 適用条件と副作用

この option は `strata drafting plan` と `strata drafting fetch` の各 parser に登録されていますが、この文書の対象は `plan` 側です（`strata_cli/drafting_cmd.py:20-30`）。`plan` 経路では pack 状態を確認して結果を組み立てるだけで、ダウンロード・pack 作成は行いません。取得と pack 処理は `fetch` が `drafting_fetch.ensure()` を呼ぶ別経路です（`strata_cli/drafting_cmd.py:63-73,74-101`; `strata_control/drafting_fetch.py:54-101`）。

## 出力とエラー

有効な値なら計画成功時の終了コードは `0` です。無効な値は `argparse` の parser で拒否され、通常の usage エラーになります。処理中に CLI が捕捉する `ValueError`、`OSError`、`KeyboardInterrupt` などが起きた場合、machine output では `schema_version: 1` と `ok: false` を含む JSON を標準出力に出し、human output では `strata: ...` を標準エラーに出します。終了コードはエラーの種類に応じます（`strata_cli/cli.py:527-532,2119-2193,2217-2235`）。

## 根拠

- 索引上のコマンド階層と予定パス: `docs/cli/README.md:322-338`（調査対象リポジトリ外の文書）。
- parser の値、既定値、`plan` と `fetch` への登録: `strata_cli/drafting_cmd.py:17-30`。
- `plan` 時の JSON/human 分岐、計画結果の組み立て、戻り値: `strata_cli/drafting_cmd.py:57-73`。
- plan 情報と pack 状態の読み取り: `strata_control/drafting_fetch.py:29-39`; `strata_control/drafting.py:114-122`。
- fetch 側の取得・検証・pack 処理との区別: `strata_cli/drafting_cmd.py:74-101`; `strata_control/drafting_fetch.py:54-101`。
- CLI 共通の機械向けエラー形式と例外経路: `strata_cli/cli.py:527-532,2119-2193`。
