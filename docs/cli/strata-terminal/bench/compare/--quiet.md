# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench compare` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

成功時の人間向け標準出力を抑制します。比較計算やレポート出力を無効にするオプションではありません。`strata bench compare` は2つの保存済みベンチマークを読み込み、比較結果を表示するコマンドです。

## 使い方

```sh
strata bench compare ./bench-results/baseline ./bench-results/candidate --quiet
```

位置引数 `baseline` と `candidate` には各 run のディレクトリ、または `results.json` ファイルを指定できます。

## 値と既定値

`--quiet` は `store_true` のフラグで、値は不要です。指定すると真になります。省略時は parser がこの属性を Namespace に追加しない設定であり、実行時の `getattr(a, "quiet", False)` により無効として扱われます。値の範囲や追加の validation はありません。

## 実行時の動作

このオプションは one-shot コマンド群に共通追加されるフラグで、`bench_compare` parser もその対象です。`strata bench compare` の固有 parser は `baseline`、`candidate`、`--output`、`--out` を定義します。

CLI は `--quiet` が有効で、かつ `--output` が `json` / `jsonl` でないとき、コマンドの標準出力を最大64 KiBの捕捉領域へ一時的に送ります。終了コードが0なら捕捉内容を出さず、比較処理の結果自体は変わりません。比較結果は通常どおり生成されます。

`--output json`（または alias の `--json`）を指定すると quiet の捕捉経路に入らず、JSON の比較結果を標準出力に出します。`--output markdown` では Markdown 比較結果を標準出力に出す通常経路が quiet によって抑制されます。`--out NEW_FILE` は `--output markdown` と併用でき、比較結果を新規ファイルに書き込みます。成功時の「Markdown comparison: ...」という確認表示は標準出力なので、quiet 使用時は表示されません。

## 適用条件と副作用

`--quiet` は `strata bench compare` にのみ適用されるフラグです。比較対象の読み込み・検証、比較条件の照合、Markdown 出力ファイルの作成を省略したり変更したりしません。`--out` の出力先が既存ファイルまたは symlink の場合、上書きせずエラーになります。

比較は保存済みレポートだけを読み、2つの run が成功していること、run ID が異なること、suite・model ID・phase 数・request workload/concurrency が一致することを検査します。設定 digest や報告された環境の差も拒否される場合があり、情報が欠ける場合は警告付きの provisional comparison になります。quiet はこの比較条件に影響しません。

## 出力とエラー

- `--output human`（既定）と `--output markdown` では、成功時の標準出力を抑制します。`--output json` / `--json` は機械可読出力を維持し、quiet は抑制に使われません。
- エラーは stderr に出ます。quiet 中にコマンドが失敗し、標準出力へ人間向け内容が既に出ていた場合、その捕捉内容も stderr に戻されます。捕捉が64 KiBを超えて切り詰められていた場合は、省略を示すメッセージも stderr に出ます。
- 比較対象ファイルの読み込み・形式検証や比較条件の失敗は `ProfileError` / `ValueError` として処理されます。終了コードは個々のエラーに設定された値に従い、たとえば別 run を要求するエラーは2、不正・不一致のレポートは5です。`_run` は人間向けエラーを `strata: ...` と stderr に出し、`--output json` ではエラー JSON を標準出力に出します。
- `--out` を使う場合、Markdown は最大64 KiBで、新規ファイルとして排他的に作成されます。既存ファイルまたは symlink は終了コード2のエラーになり、quiet でも書き込み副作用は抑制されません。

## 根拠

- 索引上の配置・コマンド階層: `docs/cli/README.md:662-670`（`strata bench compare` と `--quiet` の予定リンク）。
- 比較 parser: `strata_cli/cli.py:343-347`。
- one-shot parser への `--quiet` / `--json` の追加と既定値: `strata_cli/cli.py:508-515`（`bench_compare` を対象 tuple に含み、`argparse.SUPPRESS` を指定）。
- 比較処理、Markdown / JSON 出力と `--out` の制約: `strata_cli/cli.py:1129-1133`, `strata_cli/cli.py:1163-1174`。
- 比較条件、警告、provisional status: `strata_cli/bench.py:1006-1081`。
- レポート読み込みと validation: `strata_cli/bench.py:891-949`。
- quiet の分岐、JSON 出力時の例外、失敗時の捕捉出力: `strata_cli/cli.py:2223-2248`。
- エラー / 成功の出力先と形式: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2193`。
- Markdown ファイルのサイズ制限、既存ファイル拒否、新規作成: `strata_cli/bench.py:1301-1308`, `strata_cli/bench.py:668-677`。

調査時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。Release 配布物や別 platform での実行結果は調査していません。
