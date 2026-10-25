# `strata bench report`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench report` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/bench.py`、`strata_cli/bench_standard.py` |
| 入力 | 保存済み `results.json`、またはそのファイルを含むディレクトリ |

## 役割

保存済みベンチマーク結果を読み直して検証し、人間向け要約、JSON、Markdown を表示します。標準プロトコル (`strata bench run --suite standard-v1`) と serving suite の2形式を判別して扱います。比較結果を作るコマンドではなく、実行中のベンチマークも開始しません（parser: `strata_cli/cli.py:291-300,339-342`; dispatch: `strata_cli/cli.py:1134-1162`）。

## 使い方

```sh
# 結果ディレクトリ、または results.json を指定
strata bench report ./bench-run
strata bench report ./bench-run/results.json

# JSON の要約を標準出力へ出す
strata bench report ./bench-run --output json

# Markdown を標準出力へ出す
strata bench report ./bench-run --output markdown

# Markdown を新しいファイルに保存する（親ディレクトリは事前に用意）
strata bench report ./bench-run --output markdown --out ./report.md
```

ディレクトリを指定するとその直下の `results.json` を読みます。ファイルを指定するとそのファイルを読みます。`--output` の値は `human`（既定）、`json`、`markdown` です。`--out` は Markdown 出力と組み合わせる必要があります（`strata_cli/bench.py:891-896`; `strata_cli/bench_standard.py:1241-1244`; parser: `strata_cli/cli.py:339-342`）。

## 実行モード

| モード | 動作 |
| --- | --- |
| `--output human`（既定） | 形式ごとの読みやすい要約を標準出力に表示します。 |
| `--output json` | 成功時に `summary` を含む JSON 応答を標準出力に表示します。 |
| `--output markdown` | Markdown レポートを標準出力に表示します。 |
| `--output markdown --out FILE` | Markdown レポートを新規ファイルに保存し、保存先を標準出力に表示します。 |

## 主な動作と副作用

- `results.json` の `format` が標準プロトコル形式なら `bench_standard` の検証を通し、それ以外は serving suite 形式として `bench` の検証を通します。別形式や不正なスキーマを統合して読むことはしません（`strata_cli/bench_standard.py:1256-1265`; `strata_cli/bench.py:891-949`）。
- 標準形式では run status、quality、summary 群を含む要約を返します。serving suite 形式では run の成功・キャンセル状態、suite、各 phase の要求数・成功数・主要な latency / throughput 等を要約します（`strata_cli/cli.py:1146-1162`; `strata_cli/bench_standard.py:1122-1157`; `strata_cli/bench.py:952-975,1120-1155`）。
- report が `failed`、未完了、またはキャンセル状態でも、形式・内容を読み込んで要約できれば report 自体は終了コード 0 です。ベンチマーク結果の成否は出力内で確認してください（`strata_cli/cli.py:1146-1162`; `strata_cli/bench.py:1124-1127`）。
- 入力レポートは読み取り専用です。ファイル出力を指定した場合だけ Markdown を作成します。既存ファイルや symlink は上書きせず、ファイル作成は排他的に行います。出力は64 KiBを超えると拒否されます（`strata_cli/bench.py:668-677,1301-1308`）。
- 出力ファイルの親ディレクトリは自動作成されません。既存ファイルや親ディレクトリのないパスを指定するとファイル操作エラーになります（`strata_cli/bench.py:668-677`; `strata_cli/cli.py:2176-2183`）。

## 出力と失敗

- 不正な形式・スキーマ、読み込めない入力、またはサイズ上限を超えた入力は失敗します。serving suite report は通常ファイルで4 MiB以下、標準形式 report は64 MiB以下である必要があります。validation error は終了コード 5 です（`strata_cli/bench.py:891-900,902-949`; `strata_cli/bench_standard.py:1241-1253`）。
- `--out` を `--output markdown` なしで使う場合は終了コード 2 です。出力ファイルがすでにある場合もコード 2、Markdown が64 KiBを超える場合はコード 6 です（`strata_cli/cli.py:1129-1133`; `strata_cli/bench.py:1301-1308`）。
- `--output json` では成功応答または `{ok:false,error:...}` を標準出力に出します。human / markdown モードのエラーは `strata: ...` の形式で標準エラーに出ます。通常のファイル操作エラーは終了コード 6 です（`strata_cli/cli.py:527-542,2176-2183`）。

## 注意点

Markdown は共有用の要約です。serving suite の Markdown はクライアント観測値とサーバー報告 telemetry の要約であり、ハードウェアやモデル品質の認定ではありません（`strata_cli/bench.py:1182-1205`）。標準形式のデータ内容と解釈は標準プロトコル文書を参照してください。

索引 (`docs/cli/README.md:656-660`) には `--json` と `--quiet` も列挙されていますが、この revision の report parser が定義するのは `--output` と `--out` だけです（`strata_cli/cli.py:339-342`）。report に `--json` または `--quiet` を渡すと、未認識引数として終了コード 2 になります（`strata_cli/cli.py:2223-2231`）。この文書では parser の実装を記録しています。

## 関連文書

- [`strata bench`](../README.md) — benchmark 系コマンド全体
- [`strata bench run`](../run/README.md) — report の生成元（索引上の予定文書）
- [`strata bench compare`](../compare/README.md) — serving suite report の比較
- [CLI 文書索引](../../../README.md) — command と option の scope
- [標準ベンチマークプロトコル](../../../../BENCHMARK_PROTOCOL.md)

## 根拠

- Strata `strata_cli/cli.py:291-300,339-342` — `bench` 階層と report parser の引数・既定値。
- Strata `strata_cli/cli.py:1129-1162` — Markdown 出力条件、2形式の振り分け、成功時の出力。
- Strata `strata_cli/cli.py:527-542,2166-2183` — 成功・失敗出力と終了コード処理。
- Strata `strata_cli/bench.py:668-677,891-975,1120-1155,1182-1215,1301-1308` — serving suite の読込・検証・要約・Markdown 作成。
- Strata `strata_cli/bench_standard.py:1122-1180,1241-1265` — 標準形式の要約・Markdown・判別と検証。
- `docs/cli/README.md:652-660` — `strata bench report` の階層と `--help`、`--json`、`--out`、`--output` の scope。
- `docs/BENCHMARK_PROTOCOL.md` — 標準ベンチマークの protocol と結果形式。
