# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの作業状態は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench report` |
| オプション | `--json` |
| 別名 | なし（`--output json` でも JSON 出力を選択できる） |
| 値 | 値を取らないフラグ |

## 役割

ベンチマーク結果の要約を、機械処理しやすい JSON として標準出力へ出します。このオプションは `strata bench report` の parser に登録されています。共通 parser 設定により `--json` は `--output json` の別表記として処理されます（`strata_cli/cli.py:339-342`, `strata_cli/cli.py:508-514`, `strata_cli/cli.py:2232-2235`）。

## 使い方

```sh
strata bench report ./bench/results/run-id --json
```

位置引数 `path` は結果 JSON ファイル、またはそのファイルを含むディレクトリです。ディレクトリを指定すると `results.json` が対象になります（`strata_cli/cli.py:339-342`, `strata_cli/bench.py:891-896`, `strata_cli/bench_standard.py:1241-1247`）。

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、引数値は不要です。省略時は `--output` の既定値 `human` が使われます。出力形式の選択肢は `human`、`json`、`markdown` です（`strata_cli/cli.py:339-342`, `strata_cli/cli.py:508-514`）。

`--json` を指定すると、CLI 共通処理が出力形式を `json` に設定します。したがって `--json --output markdown` のように両方を指定しても `--json` が後段で `json` を選びます。Markdown ファイル出力用の `--out` は `--output markdown` が必要なため、この組み合わせで `--out` も指定するとエラーになります（`strata_cli/cli.py:2232-2235`, `strata_cli/cli.py:1132-1133`）。

## 実行時の動作

report コマンドはまず標準ベンチマーク形式を判別し、該当すればその結果を検証して要約します。標準形式でなければ serving benchmark 形式として読み込み、こちらも検証して要約します。`--json` 自体は読み取り・要約の経路を変えず、選択した要約を JSON で出力します（`strata_cli/cli.py:1134-1162`, `strata_cli/bench_standard.py:1256-1265`, `strata_cli/bench_standard.py:1241-1253`, `strata_cli/bench.py:891-949`）。

成功時の外側の JSON は `schema_version: 1` と `ok: true` を含み、要約は `summary` キーに入ります。標準ベンチマーク形式では `format`、`run_id`、`status`、`quality`、`summaries` を含む要約、serving benchmark 形式では run ID、suite、condition、成否、phase ごとの集計値などの要約が格納されます。入力レポート全体をそのまま出力するものではありません（`strata_cli/cli.py:1146-1150`, `strata_cli/cli.py:1161-1162`, `strata_cli/bench.py:952-975`, `strata_cli/cli.py:535-542`）。

## 適用条件と副作用

既存レポートを読み込む `report` 経路に適用され、ベンチマークの実行やサーバー起動は行いません。`--json` による主な副作用は標準出力への JSON 出力です。`--out` は Markdown 出力時だけ有効で、Markdown ファイルを新規作成しますが、`--json` の出力経路では使えません（`strata_cli/cli.py:1132-1162`）。

JSON 出力時は共通の `--quiet` による人間向け stdout の取り込み処理を通らず、結果を直接出力します（`strata_cli/cli.py:2236-2247`）。

## 出力とエラー

成功時は1つの JSON オブジェクトを標準出力へ1行で出し、終了コード `0` です（`strata_cli/cli.py:535-542`, `strata_cli/cli.py:1146-1162`）。

`--out` を `--output markdown` なしで使うと、`--json` 指定時は JSON 形式のエラーオブジェクトを標準出力へ出し、終了コード `2` になります（`strata_cli/cli.py:1131-1133`, `strata_cli/cli.py:527-532`）。レポートを読み取れない、形式・schema が不正または未対応の場合はエラー経路となります。serving report は通常ファイルかつ4 MiB未満であることなどを確認し、不正形式は `ProfileError` として拒否します。標準形式は64 MiBを超えるファイルや検証に失敗する内容を拒否します（`strata_cli/bench.py:891-900`, `strata_cli/bench.py:901-949`, `strata_cli/bench_standard.py:1241-1253`）。共通例外処理は `ValueError`（`ProfileError` を含む）を JSON エラーとして返します。ファイル読み込み等の `OSError` はファイル操作エラーとして JSON で返します（`strata_control/profiles.py:30-34`, `strata_cli/cli.py:2166-2183`）。個々のエラー終了コードは例外の `exit_code` に従い、全ケースが同一コードとは限りません。

## 根拠

- `strata_cli/cli.py:339-342` — `bench report` と `--output` の parser 定義。
- `strata_cli/cli.py:508-514`, `strata_cli/cli.py:2223-2235` — 共通 `--json` 登録と `--output json` への変換。
- `strata_cli/cli.py:1129-1162` — `report` の実行分岐、JSON 要約の選択、`--out` 制約。
- `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2188` — JSON 成功・失敗出力と例外経路。
- `strata_cli/bench.py:891-975` — serving benchmark 結果の読み込み、検証、要約。
- `strata_cli/bench_standard.py:1241-1265` — 標準形式結果の読み込み、検証、形式判別。
