# `strata bench compare --out`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench compare` |
| オプション | `--out NEW_FILE` |
| 別名 | なし |
| 値 | Markdown 比較レポートを書き込む新規ファイルのパス |

## 役割

2 件の保存済み serving benchmark run を比較し、その比較結果を Markdown ファイルとして保存します。入力の読み込みと比較条件の検査は `strata bench compare` が行い、`--out` は `--output markdown` で生成した結果の保存先を指定します（`strata_cli/cli.py:343-347, 1163-1172`）。

## 使い方

```sh
strata bench compare ./baseline/results.json ./candidate/results.json \
  --output markdown --out ./comparison.md
```

引数 `baseline` と `candidate` には各 run のレポートファイル、または `results.json` を含むディレクトリを渡せます。相対パスは実行時の作業ディレクトリを基準に解釈されます（`strata_cli/cli.py:344-347, 1164`; `strata_cli/bench.py:891-896`）。出力先の親ディレクトリは事前に存在している必要があります。

## 値と既定値

- `--out` は `NEW_FILE` を1つ受け取ります。parser 上は省略可能で、既定値は `None` です。省略時、`--output markdown` の比較結果はファイルに保存されず stdout に出力されます（`strata_cli/cli.py:346-347, 1165-1172`）。
- `--out` を指定した場合は `--output markdown` も必要です。既定の `--output human` や `--output json` と併用すると比較前に終了コード `2` で失敗します（`strata_cli/cli.py:346, 1131-1133`）。
- 拡張子やパス形式に関する独自の parser validation はありません。書き込み先の親ディレクトリがない、または書き込みできない場合はファイル操作エラーになります（`strata_cli/cli.py:347, 1167-1169, 2176-2183`）。

## 実行時の動作

1. baseline と candidate を順に読み込みます。入力は通常ファイルで、サイズは4 MiB未満でなければならず、Strata serving benchmark report の形式検証を通過する必要があります。ディレクトリを指定した場合は、その中の `results.json` を読みます（`strata_cli/bench.py:891-949`）。
2. 両 run が成功していること、run ID が異なること、suite・model ID・phase 数・request workload・concurrency が一致することを確認します。両方に source config digest があれば一致も要求し、記録された環境情報の不一致も拒否します。情報が欠けている場合は警告になります（`strata_cli/bench.py:978-989, 1006-1048`）。
3. 比較結果を Markdown に整形します。結果には provisional comparison の表示、主要指標と phase ごとの比較、警告が含まれます（`strata_cli/bench.py:1258-1298`）。`--out` を指定すると、比較結果を新規ファイルに書き込み、成功時は `Markdown comparison: <絶対パス>` を stdout に表示します。指定しない場合は Markdown 本文を stdout に出します（`strata_cli/cli.py:1163-1172`）。

## 適用条件と副作用

- このオプションは `strata bench compare` 専用です。同じ階層の `strata bench report --out` もありますが、別コマンド・別スコープです（`strata_cli/cli.py:339-347`）。
- `--out` の使用時には `--output markdown` が必須です。`--json` は one-shot command の `--output json` alias で、指定すると `--out` の Markdown 条件を満たさず終了コード `2` になります（`strata_cli/cli.py:508-515, 1131-1133, 2232-2235`）。
- 出力ファイルが既にある場合（シンボリックリンクを含む）は上書きしません。本文は最大64 KiBで、ファイルは排他的な新規作成（`O_EXCL`）、モード `0600`、flush と `fsync` を使って書かれます（`strata_cli/bench.py:668-678, 1301-1308`）。
- `--quiet` と併用すると成功時の人間向け stdout（保存先の通知を含む）は抑制されます。指定したファイルへの書き込みは通常どおり行われます（`strata_cli/cli.py:508-515, 2236-2247`）。
- 比較レポートは性能向上やハードウェア適格性を証明するものではありません。比較結果自体も qualification を `provisional` とし、未証明の環境要素を警告に出します（`strata_cli/bench.py:1048, 1073-1080, 1258-1262, 1294-1297`）。

## 出力とエラー

- `--out` と `--output markdown` の正常時はファイルを作成し、保存先を stdout に表示して終了コード `0` を返します。Markdown を `--out` なしで選んだ場合は本文を stdout に出します（`strata_cli/cli.py:1165-1172`）。
- `--out` に `--output markdown` を併用しない場合は終了コード `2` です。通常表示では stderr に `strata: --out requires --output markdown`、`--output json` では JSON 形式のエラーを stdout に出します（`strata_cli/cli.py:1131-1133, 527-532`）。
- 読めない・形式不正・4 MiB以上の入力、成功していない run、異なる suite/model/workload/concurrency/environment など比較条件の不一致は比較に失敗します。比較条件違反の終了コードは主に `5`、同一 run ID は `2` です（`strata_cli/bench.py:891-949, 1006-1048`）。
- 出力先が既存ファイルまたは symlink の場合は終了コード `2`、Markdown が64 KiBを超える場合は `6` です。OS の書き込みエラーも CLI の file error 経路で終了コード `6` になります（`strata_cli/bench.py:1301-1308, 668-678`; `strata_cli/cli.py:2176-2183`）。

## 根拠

- parser 定義と `--json` / `--quiet` 登録: `strata_cli/cli.py:343-347, 508-515`
- 引数検査、比較、Markdown 出力: `strata_cli/cli.py:1129-1133, 1163-1174`
- report の読み込みと検証: `strata_cli/bench.py:891-949`
- 比較の適用条件と警告: `strata_cli/bench.py:978-1081`
- Markdown 生成、新規ファイル作成、サイズ・既存ファイル制約: `strata_cli/bench.py:1258-1308`
- エラー変換と quiet 時の stdout 抑制: `strata_cli/cli.py:519-542, 2166-2183, 2232-2247`

索引上の配置は [`strata bench compare`](../../../README.md) に従っています。索引では `--out` のみが比較コマンドの Markdown 保存先として列挙されています。
