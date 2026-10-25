# `strata bench report --out`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench report` |
| オプション | `--out` |
| 別名 | なし |
| 値 | Markdown レポートの出力先ファイルパス（`NEW_FILE`） |

## 役割

既存のベンチマークレポートを Markdown に整形し、指定した新規ファイルへ保存します。対象は `strata bench report` の `--out` です。同じオプションは `strata bench compare` にもありますが、別コマンドのためこの文書の対象外です。

## 使い方

```sh
strata bench report ./results.json --output markdown --out ./report.md
```

`path` にはレポートファイル、または `results.json` を含むレポートディレクトリを渡します。`--out` を使う場合は `--output markdown` も指定します。

## 値と既定値

- `--out` は値を一つ取ります。値はパス文字列として `Path` に渡されます。パスはプロセスの作業ディレクトリを基準に解決されます。
- 省略時は出力先ファイルを作らず、Markdown を標準出力へ出します。
- 同じ `--out` を複数回指定した場合の parser action は通常の `argparse` の単一値指定で、後の値が採用されます。
- `--out` の値が空文字列なら処理側の真偽判定を通らず、省略時と同じく標準出力になります。

## 実行時の動作

`--out` の出力は `--output markdown` の場合に限られます。`--out` と既定の `--output human`、`--output json`、または `--json` を組み合わせると、処理は `--out requires --output markdown` で拒否され、終了コード 2 になります。`--json` は `--output json` の alias です。

入力が標準ベンチマーク形式なら、`strata_cli.bench_standard` がレポートを検証し Markdown を生成します。それ以外は `strata_cli.bench` が従来形式の serving benchmark レポートとして読み込み、検証して Markdown を生成します。いずれの経路でも生成後、`--out` のパスへ新規作成します。出力先が既にある場合は上書きしません。書き込みが成功すると、`Markdown report: <絶対パス>` を表示します。

`--quiet` を併用すると、Markdown ファイルは作成されますが、成功時の案内メッセージは抑制されます。これは human 出力を捕捉して成功時に表示しない処理によります。

## 適用条件と副作用

- 出力は UTF-8 の Markdown です。生成内容が 64 KiB を超えると拒否され、終了コード 6 になります。
- 出力先に既存のファイルまたはシンボリックリンクがあると、終了コード 2 で失敗します。作成は `O_EXCL` を使うため、確認後に別プロセスがファイルを作成する競合でも既存ファイルを置き換えません。
- 出力ファイルは新規作成モード `0600` で開かれ、書き込み後に flush と `fsync` が行われます。親ディレクトリは自動作成されません。作成・書き込み時の OS エラーは CLI 共通処理でファイル操作エラーとして報告され、終了コード 6 になります。
- 入力レポートの読込失敗や検証不一致は失敗となり、出力ファイルは生成されません。旧形式のレポートは通常ファイルかつ 4 MiB 未満であること等を確認し、標準形式は 64 MiB 以下で形式・スキーマを検証します。

## 出力とエラー

- 成功時: `Markdown report: <絶対パス>` を標準出力へ出し、終了コード 0 を返します。`--quiet` の場合、この成功案内は表示されません。
- `--output markdown` 以外で `--out` を指定: stderr に `strata: --out requires --output markdown`、終了コード 2。
- 出力先が既に存在する: stderr に `strata: Markdown output file already exists`、終了コード 2。
- Markdown が 64 KiB 超: stderr にサイズ上限エラー、終了コード 6。
- 入力を読めない、または形式・スキーマが無効: CLI エラーとして報告し、検証エラーに応じた失敗コードを返します。出力ファイル作成前の失敗です。
- `--output json` で `--out` 条件違反になった場合、エラーは JSON 形式で出力されます。通常の human 出力ではエラーは stderr に出ます。

## 根拠

- parser の位置引数、既定値 `human`、選択肢、`--out NEW_FILE` の定義: `strata_cli/cli.py:339-342`。
- `--json` alias と `--quiet` の登録: `strata_cli/cli.py:508-515`。
- `--out` の条件チェック、標準形式／旧形式ごとの Markdown 生成、ファイル書き込みと成功メッセージ: `strata_cli/cli.py:1129-1162`。
- 出力先が既存の場合の拒否と 64 KiB 上限: `strata_cli/bench.py:1301-1308`。
- 排他的な新規ファイル作成、モード `0600`、flush・`fsync`、失敗時の削除: `strata_cli/bench.py:668-677`。
- 旧形式レポートのファイル条件と検証: `strata_cli/bench.py:891-930`。
- 標準形式レポートの 64 MiB 上限、JSON 読み込みと validation: `strata_cli/bench_standard.py:1241-1265`、validation の形式・スキーマ確認: `strata_cli/bench_standard.py:965-981`。
- CLI 共通の human／JSON エラー出力: `strata_cli/cli.py:527-532`。`OSError` の報告と終了コード 6: `strata_cli/cli.py:2176-2183`。
- `--quiet` による成功時標準出力の抑制: `strata_cli/cli.py:2232-2247`。

この調査ではソースを読み取り、CLI を実行していません。動的なファイルシステム権限や OS ごとの差は実測していません。
