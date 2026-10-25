# `strata bench report --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench report` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力への alias） |
| 値 | `human`、`json`、`markdown` |
| 既定値 | `human` |

## 役割

既存ベンチマーク結果の表示形式を選びます。`--output` 自体は出力ファイルを指定しません。Markdown をファイルへ保存する場合は `--out NEW_FILE` を併用します。入力結果は位置引数 `path` で指定します。

## 使い方

```sh
strata bench report ./bench-results/run-01 --output json
strata bench report ./bench-results/run-01 --output markdown
strata bench report ./bench-results/run-01 --output markdown --out ./run-01-summary.md
```

ファイル出力例の保存先は未作成のパスにしてください。`--out` を使うとき `--output markdown` は必須です。

## 値と既定値

Parser は `--output` の値を `human`、`json`、`markdown` に限定し、既定値を `human` にします。別の値を指定すると argparse が引数エラーとして usage とエラーを表示して終了コード 2 で終了します。オプションは `strata bench report` の parser に属します（`strata bench compare` にも同じ選択肢がありますが別スコープです）。

- `human`: 要約を通常の人向けテキストで標準出力へ表示します。
- `json`: 要約を機械可読 JSON として標準出力へ表示します。`--json` は one-shot コマンド共通の alias で、実行時に `--output json` と同じ値に設定されます。
- `markdown`: Markdown レポートを標準出力へ表示します。`--out FILE` を加えると標準出力の Markdown の代わりにファイルを作成し、作成先を示す `Markdown report: ...` を標準出力へ出します。

`--quiet` もこのコマンドで受理されます。`--quiet` と `--output human` または `markdown` を組み合わせると、成功時は標準出力が抑止されます。`--quiet` は `json` 出力を抑止しません。`--json` と `--output markdown` を併記した場合も、共通処理が `--json` を見て最終的な出力値を `json` に変更します。そのため `--out` も併記していれば `--out requires --output markdown` で拒否されます。

## 実行時の動作

コマンドはまず入力を標準 benchmark 形式として判定します。標準形式なら `bench_standard` の検証済み結果を使い、その他の形式なら serving benchmark の `bench.load` で読み込み・検証します。ディレクトリを指定した場合はその中の `results.json` が入力になります。どちらの形式でも `human` は形式に応じた人向け要約、`json` は `summary` を含む JSON、`markdown` は対応する Markdown 要約を出力します。Markdown の生成は標準レポートでは `bench_standard.report_markdown`、serving レポートでは `bench.markdown_report` が担当します。

`--out` は `--output markdown` のときだけ有効です。保存先は新規ファイルとして作成され、既存ファイルや symlink は置換されず終了コード 2 のエラーになります。実装は排他的作成 (`O_EXCL`) を使うため、事前確認後に同名ファイルが作られた場合も既存ファイルを上書きしません。出力は UTF-8、ファイル保存時の上限は 64 KiB で、作成時に `0600` を mode として要求します（実効 mode は OS の umask の影響を受けます）。親ディレクトリは自動作成しません。入力結果は Markdown の保存前に読み込み・検証されます。

## 適用条件と副作用

- `--output` は表示形式のみを選択します。出力先ファイルを作成する副作用は `--out` を併用した場合に限られます。
- `--out` 指定時は Markdown 形式でなければなりません。条件違反は入力を読む前に終了コード 2 で拒否されます。
- Markdown は既存ファイルを保護して新規作成されます。親ディレクトリがない、書き込み権限がないなどの OS エラーはファイル操作エラーとして失敗します。
- quiet mode は人向け標準出力を捕捉し、成功時に表示しません。JSON 出力はこの抑止の対象外です。

## 出力とエラー

- 正常な `human` / `json` は標準出力へ要約を出し、終了コード 0 を返します。JSON の成功応答は `schema_version`、`ok: true`、`summary` を含みます。
- 正常な `markdown` は標準出力へ Markdown を出します。`--out` を使う場合はファイルを作成して作成先の案内を出します。
- `--out` と Markdown 以外の出力形式の組み合わせは終了コード 2 です。JSON モードの場合は JSON error 応答、それ以外は標準エラーに `strata: --out requires --output markdown` を出します。
- 入力を読み取れない、形式・schema が未対応、または検証に通らない場合は失敗します。serving benchmark の loader は通常、読み取り失敗や未対応レポートに終了コード 5 を付けます。標準形式の loader も結果を検証し、不正な標準結果を拒否します。
- `--out` への Markdown 保存で内容が 64 KiB を超える場合は終了コード 6、保存先が既に存在する場合は終了コード 2 です。その他の OS ファイルエラーは CLI の共通処理で終了コード 6 として報告されます。
- `--quiet` により成功時の human/Markdown 出力が抑止されても、失敗時は捕捉済み出力があれば標準エラーへ戻されます。

## 根拠

- `strata_cli/cli.py:339-342` — `report` parser、位置引数 `path`、`--output` の choices と既定値、`--out`。
- `strata_cli/cli.py:508-515` — one-shot コマンド共通の `--json` alias と `--quiet`。
- `strata_cli/cli.py:1129-1162` — `--out` 条件、standard/serving レポート判定、各出力形式の分岐と出力先。
- `strata_cli/cli.py:527-542` — JSON/標準エラーの error 出力と成功時の JSON/human 出力。
- `strata_cli/cli.py:2166-2188` — ValueError/OSError 等を CLI error と終了コードへ変換する経路。
- `strata_cli/cli.py:2223-2248` — parser 実行、`--json` が最終的に `output=json` に設定される処理、quiet 時の stdout 抑止。
- `strata_cli/bench.py:668-677` — `O_EXCL` による新規ファイル作成、mode `0600`、失敗時の部分ファイル削除。
- `strata_cli/bench.py:891-900, 938-948` — serving 結果のサイズ・型・schema 検証と読み込みエラー。
- `strata_cli/bench.py:1182-1205, 1301-1308` — Markdown 要約、64 KiB 制限、既存パス拒否。
- `strata_cli/bench_standard.py:1241-1265` — ディレクトリ内 `results.json` の選択、標準形式判定と検証済み読み込み。
- `docs/BENCHMARK_PROTOCOL.md:44-47` — 利用者向けの report 再表示説明。
- `docs/DEVELOPER_INTEGRATION_HANDOFF.md:133-136` — JSON 表示および Markdown ファイル出力の使用例。

調査は上記 checkout の parser と実装、および同 revision の利用者向け文書に限定しました。CLI `--help`、Release 配布物、実環境でのファイル作成は確認していません。出力ファイルに対する OS 固有の ACL・umask の追加効果は実行環境を調べていないため記述していません。
