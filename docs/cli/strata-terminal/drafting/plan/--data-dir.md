# `strata drafting plan --data-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--data-dir` |
| 別名 | なし |
| 値 | `DIR`。parser は文字列を受け取る。型・存在・書き込み可否の検証なし |

## 役割

DFlash2 drafter の取得計画を調べるときに、モデルデータフォルダーを明示します。指定フォルダーは drafter pack の所在確認や、計画に含まれる pack パス・VRAM 見積りの算出に使われます。`strata drafting plan` は計画を表示するコマンドであり、このオプションによってダウンロード先を作成したりファイルを移動したりはしません。

## 使い方

```sh
strata drafting plan --data-dir /mnt/models --family qwen --model IQ3_S
```

指定したデータフォルダーで、Qwen IQ3_S の drafter 計画を表示します。既存の run config を使う場合は `--config FILE` も指定できます。

## 値と既定値

`DIR` は任意の文字列です。parser は `metavar="DIR"` の引数を追加するだけで、ディレクトリの存在や形式を検証しません（`terminal/strata_cli/drafting_cmd.py:19-29`）。実行時には truthy な値が `Path` に変換されます。空文字列は明示パスとして使われず、既定の解決手順に進みます（同:101-116）。相対パスはプロセスの作業ディレクトリから解釈されます。

省略時は、まず `--config` がある場合に、その設定内の engine 引数 `--pack` または `--mtp` からデータフォルダーを推定します。どちらからも得られなければ `Catalog().data_dir()` が返す Strata のデータフォルダーを使います（`terminal/strata_control/drafting.py:1662-1671`、`terminal/strata_cli/drafting_cmd.py:101-117`、`terminal/strata_cli/launch/catalog.py:753-760`）。`--data-dir DIR` を指定した場合はこの解決結果より優先されます。

## 実行時の動作

`--data-dir` は `plan` と `fetch` の両方に登録されていますが、この文書の対象は索引上の `strata drafting plan` の scope です（`terminal/strata_cli/drafting_cmd.py:19-38`）。`plan` の処理は解決したフォルダーを使い、pack が既にあるか、モデル・backend・GPU 条件で DFlash2 が必要か、tuned drafter が適用されるかなどを確認して計画を組み立てます（同:240-265、`terminal/strata_control/drafting.py:1548-1587,1611-1623`、`terminal/strata_control/drafting_fetch.py:68-88`）。データフォルダーは pack の検査と出力先パスの算出に影響します。

`--config` の engine 引数に `--pack` または `--mtp` がある場合の自動推定より、明示した `--data-dir` が優先されます（`terminal/strata_cli/drafting_cmd.py:101-117`）。また、`--config` の `drafting` 設定は `--mode` が指定されない場合の選択として読まれます。同じ plan の他オプションとモデル状態により必要な drafter と表示内容が変わるため、フォルダーだけからダウンロード要否が決まるわけではありません（同:119-136,240-265）。

## 適用条件と副作用

`--data-dir` は `strata drafting plan` で明示した場合に使われます。指定先が存在しない、または pack を読み取れない場合、pack の存在確認は未準備として扱います（`terminal/strata_control/drafting.py:669-673,823-827,862-867`）。このオプション自体に、ディレクトリ作成、ファイル書き込み、ダウンロード、既存データの移動を行う処理はありません。`plan` 分岐は結果を出力して終了し、ダウンロード処理 `drafting_fetch.ensure_for` には進みません（`terminal/strata_cli/drafting_cmd.py:247-266,267-305`）。

## 出力とエラー

既定の `--output human` では、計画の文章を標準出力に表示します。`--output json` または `jsonl` では計画結果の JSON を表示します（parser の選択肢・既定値: `terminal/strata_cli/drafting_cmd.py:38`; 出力分岐: 同:262-266）。この plan 分岐は成功時に終了コード `0` を返します。

parser は `DIR` の妥当性を検査しないため、無効な場所は通常 pack 未準備として計画に反映されます。後続で `ValueError` / `OSError` が発生した場合、CLI 共通処理がそれぞれエラーコード（既定 `2` / `6`）と human または JSON 形式のエラーを返します（`terminal/strata_cli/cli.py:2248-2265`）。具体的なエラー文言は原因に依存します。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `drafting plan` / `fetch` の parser 登録、`--data-dir DIR` と `--output` の定義。
- `terminal/strata_cli/drafting_cmd.py:101-136` — 明示値と config/catalog 由来データフォルダーの優先順位、計画入力の組み立て。
- `terminal/strata_cli/drafting_cmd.py:240-266` — 必要性判定、plan の生成と human/JSON 出力、成功終了。
- `terminal/strata_control/drafting.py:1662-1671` — config の `--pack` / `--mtp` 引数からのデータフォルダー推定。
- `terminal/strata_control/drafting.py:669-673,823-827,862-867` — pack ファイル確認と読み取り失敗時の扱い。
- `terminal/strata_control/drafting_fetch.py:68-88` — 計画結果に含める準備状態・サイズ・パスの算出。
- `terminal/strata_cli/launch/catalog.py:753-760` — Strata の標準データフォルダー解決。
- `terminal/strata_cli/cli.py:2248-2265` — CLI 共通の `ValueError` / `OSError` エラー処理。
