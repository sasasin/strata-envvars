# `strata bench compare`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench compare` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/bench.py` |
| 入力 | 保存済み serving benchmark の結果ディレクトリ、または `results.json` |

## 役割

保存済みの serving benchmark 2件を baseline と candidate として読み込み、ワークロードと記録された環境条件を検査したうえで、各フェーズの指標差を表示します。比較結果の qualification は常に provisional であり、このコマンド単独ではハードウェアや monitor 状態を認証しません（`strata_cli/bench.py:1006-1081,1258-1297`）。

このコマンドは比較対象を新たに実行しません。`strata bench run` が作成した serving benchmark report を入力にします。run/report の概要は [`strata bench run`](../run/README.md)、[`strata bench report`](../report/README.md) を参照してください。

## 使い方

```sh
# 既存の結果ディレクトリを比較して、標準出力に人間向け結果を表示
strata bench compare ./bench-results/baseline ./bench-results/candidate

# Markdown を標準出力に表示
strata bench compare ./bench-results/baseline/results.json ./bench-results/candidate/results.json --output markdown

# Markdown を新規ファイルに保存
strata bench compare ./bench-results/baseline ./bench-results/candidate --output markdown --out ./comparison.md
```

入力にはディレクトリを指定するとその中の `results.json` を読み、ファイルを指定するとそのファイルを読みます。比較用 report は、たとえば `strata bench run --profile NAME --suite serving-smoke --out NEW_DIRECTORY` で作成できます。比較に使う2回の run では同じ suite とモデル、同じリクエスト fingerprint・並行数、記録される環境設定を揃えてください（parser: `strata_cli/cli.py:291-311,343-347`; load/compare: `strata_cli/bench.py:891-949,978-1081`）。

## 実行モード

| モード | 指定 | 動作 |
| --- | --- | --- |
| 人間向け表示 | 既定（`--output human`） | suite、provisional 状態、baseline/candidate、主要指標、注意事項を標準出力に表示します。 |
| JSON | `--output json` | `comparison` を含む JSON 成功応答を出力します。 |
| Markdown | `--output markdown` | Markdown 比較レポートを標準出力に表示します。 |
| Markdown ファイル | `--output markdown --out FILE` | 比較レポートを新規ファイルとして作成し、作成先を表示します。 |

Parser は `--output` に `human`、`json`、`markdown` を受け付け、既定値は `human` です。`--out` は `--output markdown` と同時に指定する必要があります（`strata_cli/cli.py:343-347,1129-1133`）。

## 主な動作と副作用

- 両方の入力を検証して読み込みます。ファイルは通常ファイルで 4 MiB 以下である必要があり、JSON schema/kind、run ID、suite、phase 等の形式も検査します（`strata_cli/bench.py:891-949`）。
- 2件とも成功済みで、異なる run ID を持ち、suite とモデル ID が一致し、フェーズ数が同じであることを要求します。各フェーズの種類・要求数・client worker 数・要求 fingerprint（prompt SHA-256、max tokens、label）も一致が必要です（`strata_cli/bench.py:978-1020`）。
- 両方に source config digest がある場合は一致を要求します。digest の欠落、managed launch による実行時設定の照合がない場合、または記録された環境情報が欠ける場合は warning を付けます。記録された環境値が異なる場合は比較を拒否します（`strata_cli/bench.py:1022-1048`）。
- フェーズごとに duration と p95 TTFT、p95 latency、output throughput などを比較します。primary phase の中央値も算出し、primary phase が3件未満なら warning を付けます。数値差は観測結果の表示であり、改善や適格性を判定するものではありません（`strata_cli/bench.py:1050-1081,1258-1297`）。
- 比較処理自体は入力 report を読み取ります。`--out` を使う場合だけ Markdown ファイルを作成します。出力ファイルが既にある場合（symlink を含む）は置き換えずに失敗し、生成内容が64 KiBを超える場合も失敗します（`strata_cli/cli.py:1163-1174`; `strata_cli/bench.py:1301-1308`）。

## 注意点

report による比較では、driver、engine binary、model artifact、monitor attachment は認証されません。また、環境情報は report が記録した値に基づき、独立した証明ではありません。比較結果は provisional として扱い、表示された割合だけから性能改善や同一条件を断定しないでください（`strata_cli/bench.py:1006-1048,1258-1297`）。

`strata bench compare` は `strata bench run` の standard protocol report ではなく、`strata.serving.benchmark` 形式の serving benchmark report を読み込みます。標準 benchmark report は別形式であり、この比較関数への入力としては扱われません（`strata_cli/cli.py:1163-1164`; `strata_cli/bench.py:901-938`）。

## 出力と失敗

- 読み込めない、形式が異なる、条件が合わない、または成功していない report はエラーになります。比較条件の不一致は主に終了コード 5、同じ run の重複や既存の Markdown 出力先はコード 2、Markdown が64 KiBを超える場合はコード 6 です（`strata_cli/bench.py:891-949,1006-1048,1301-1308`）。
- `--out` を `--output markdown` なしで指定すると、処理前に終了コード 2 で拒否されます（`strata_cli/cli.py:1129-1133`）。
- CLI は捕捉した `ValueError`、`OSError`、`ClientError` 等を共通エラー応答へ変換します。JSON 出力時は JSON 形式、それ以外は通常のエラー表示となります（`strata_cli/cli.py:2166-2188`）。個々の入力不正で常に同一の終了コードになるとは限らず、loader が返すエラーコードに従います。

## 関連文書

- [`strata bench run`](../run/README.md) — serving benchmark の実行と report 作成
- [`strata bench report`](../report/README.md) — 保存済み report の要約

上記の `run` と `report` の概要ページは索引に掲載されていますが、この調査時点ではまだ作成されていません。

- [CLI 索引](../../../README.md) — `strata bench compare` の option scope と文書一覧

## 根拠

- `strata_cli/cli.py:291-347` — `bench` 配下の subcommand と compare parser 定義。
- `strata_cli/cli.py:1129-1133,1163-1174` — 出力条件、入力ロード、compare、表示分岐。
- `strata_cli/bench.py:891-949` — report 入力形式と validation。
- `strata_cli/bench.py:978-1081` — workload/environment checks、比較指標、provisional result。
- `strata_cli/bench.py:1084-1117,1258-1308` — 人間向け/Markdown 出力と新規ファイル作成規則。
- `docs/cli/README.md:662-670` — コマンド階層と `--help`、`--json`、`--out`、`--output` の option scope。
