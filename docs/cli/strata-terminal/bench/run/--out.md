# `strata bench run --out`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--out NEW_DIRECTORY` |
| 別名 | なし |
| 値 | 出力先ディレクトリのパス。parser では文字列として受け取り、実行時に `Path` に変換する |

## 役割

ベンチマーク結果を書き込む新規ディレクトリを指定します。`standard-v1`（既定 suite）では省略でき、省略時はカレントディレクトリに応じて `./bench/results` または `./bench-results` の下に一意な名前のフォルダーを作ります。標準以外の serving suite では必須です（`strata_cli/cli.py:297-311,1186-1190,1279-1281`）。

## 使い方

```sh
# 標準ベンチマーク。空いている出力先を明示する
strata bench run --profile Office --out ./bench-results/my-run

# serving suite。--out は必須
strata bench run --url https://example.invalid --suite serving-smoke --out ./bench-results/smoke-01
```

`--profile` と `--url` は相互排他で、どちらか一方が必要です。例の URL は形式を示すプレースホルダーであり、実行可能な接続先ではありません（`strata_cli/cli.py:293-300`）。

## 値と既定値

- 値はパス文字列です。`--out` 自体に `type`、形式、絶対パスの強制はなく、相対パスはプロセスのカレントディレクトリ基準で解決されます（`strata_cli/cli.py:309-311,1279-1281`）。
- `standard-v1` では未指定が許されます。`./bench/results` がディレクトリとして存在すればそこを使い、そうでなければ `./bench-results` を使います。その下に UTC 日付、GPU 名（取得できない場合は `cpu`）、run ID の末尾を含むフォルダー名を生成します。親ディレクトリは作成されます（`strata_cli/cli.py:1279-1281`; `strata_cli/bench_standard.py:834-839`）。
- 明示したパスは既存のファイル・ディレクトリ・シンボリックリンクと衝突すると拒否されます。標準・serving のいずれも、結果ディレクトリは新規作成で、既存の内容を上書きしません（`strata_cli/bench_standard.py:777-779,839`; `strata_cli/bench.py:755-756,792`）。
- serving suite では親ディレクトリを自動作成しません。指定した出力先の親が存在しない場合は作成に失敗します（`strata_cli/bench.py:792`; `strata_control/private_files.py:320-330`）。
- 同じ `--out` を複数回指定した場合の個別検証はありません。`argparse` の通常の単一値引数として最後に解析された値が使われます（`strata_cli/cli.py:309-311`）。空文字列も parser では拒否されず、`Path("")` は現在のディレクトリを指すため、通常は既存先として拒否されます（同 `:1279`; `strata_cli/bench_standard.py:777-778`; `strata_cli/bench.py:755-756`）。

## 実行時の動作

### `standard-v1`（既定）

指定した、または自動生成した新規ディレクトリに、結果の `results.json` と人向け `README.md` を作成します。条件により `outputs.jsonl`、`config.json`、`provenance/` 以下の資料、engine log も書き込みます。ファイルは新規作成モードで書き込まれ、既存ファイルを置き換えません（`strata_cli/bench_standard.py:899-923,958-960`; `strata_cli/bench.py:668-677`）。ディレクトリは POSIX では mode `0700` で作成されます（`strata_control/private_files.py:320-330`）。

`--profile` のサーバーがまだ応答しない場合、`--no-start` がなければベンチマーク用に engine を起動します。プロファイルの起動・ロードは `bench_standard.run()` が出力先の既存チェックを行うより前に実行されます。そのため、すでに存在する `--out` を指定しても、その前段で engine 起動が行われる場合があります。既に稼働中の profile サーバーは停止しません。`--url` では指定したサーバーを対象にします（`strata_cli/cli.py:1256-1305`; `strata_cli/bench_standard.py:777-785`）。

### serving suite

`serving-smoke` など標準以外では `--out` が必要で、指定先に `progress.json` と最終的な `results.json` を作成します。進捗ファイルは実行中に更新されます。出力ディレクトリは API/telemetry の事前確認後に作られます（`strata_cli/cli.py:1186-1225`; `strata_cli/bench.py:755-802,881-888`）。保存済み `--profile` を使う場合は benchmark lease を取得してから benchmark runner を呼び出します（`strata_cli/cli.py:1219-1225`）。

## 適用条件と副作用

- `--out` は `bench run` 専用です。同じ名前の `strata bench report` / `compare` の `--out` は Markdown ファイル用で、別スコープ・別動作です（`strata_cli/cli.py:335-347,1132-1174`）。
- 明示パスの親ディレクトリがない、書き込み権限がない、またはパス作成に失敗した場合は出力を完了できません。serving suite と標準 suite はどちらも新しい出力ディレクトリを求めます（`strata_cli/bench.py:755-756,792`; `strata_cli/bench_standard.py:777-779,839`）。
- 標準 suite はベンチマーク通信を行い、profile 起動経路では engine の起動・終了も伴います。`--out` はそれらを無効化せず、成果物の保存先だけを変えます（`strata_cli/cli.py:1288-1307`）。
- Windows での ACL 設定は `private_mkdir` が行いますが、この調査では Windows 上での実行確認はしていません。ソースでは Windows の権限設定失敗を握りつぶす経路があります（`strata_control/private_files.py:331-345`）。

## 出力とエラー

- 既存の出力先は `ProfileError`（終了コード 2）として拒否されます。書き込みなどの `OSError` は CLI の共通処理でエラー表示され、終了コード 6 になります（`strata_cli/bench_standard.py:777-779`; `strata_cli/bench.py:755-756`; `strata_cli/cli.py:2166-2183`）。
- 自動生成パスを使う標準 suite は、通常出力でレポートと結果の絶対パスを表示します。`--output json` では JSON に結果パスを含めます。serving suite も通常出力または JSON に `results.json` のパスを含めます（`strata_cli/cli.py:1226-1234,1321-1328`）。
- ベンチマーク結果が完了扱いでない場合、成果物を保存したうえで終了コード 6 になることがあります。標準 suite は engine の停止に失敗すると `ENGINE-NOT-STOPPED.txt` を追加し、その engine が port/GPU を保持している可能性を stderr に表示します（`strata_cli/cli.py:1312-1328`）。

## 根拠

- `strata_cli/cli.py:291-314` — `bench run` parser、suite、`--out` の宣言と説明。
- `strata_cli/cli.py:1129-1234` — serving suite と標準 suite の振り分け、出力先の引き渡し、結果表示。
- `strata_cli/cli.py:1237-1328` — 標準 suite の実行、profile engine 起動・停止、既定出力ルートと失敗表示。
- `strata_cli/bench_standard.py:766-840,899-960` — 標準 suite の既存先検査、フォルダー生成、成果物の書き込み。
- `strata_cli/bench.py:744-802,881-888` — serving suite の既存先検査、進捗・結果ファイルの作成。
- `strata_control/private_files.py:320-346` — 出力ディレクトリ作成と権限設定。
- `strata_cli/cli.py:2166-2183` — 共通のエラー表示と終了コード。
- `docs/cli/README.md:610-623`（strata-envvars）— 対象のコマンド階層と `--out` の索引位置。
