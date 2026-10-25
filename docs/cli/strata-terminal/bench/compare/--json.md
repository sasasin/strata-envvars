# `strata bench compare --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench compare` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値なしの真偽フラグ。既定値は `false` |

## 役割

比較結果を人向けテキストではなく、1行の JSON として標準出力へ出します。対象の `compare` は baseline と candidate の保存済み benchmark report を読み、workload の一致を検査したうえで比較結果を作ります（`strata_cli/cli.py:343-347,1163-1174`）。

## 使い方

```sh
strata bench compare ./bench/results/baseline ./bench/results/candidate --json
```

位置引数には各レポートのファイル、または `results.json` を含むディレクトリを指定できます。読み込み時、ディレクトリなら `results.json` が対象になります（`strata_cli/bench.py:891-896`）。

## 値と既定値

`--json` は `argparse` の `store_true` で、引数値を取りません。省略時は `false` で、比較コマンドの出力既定値は `--output human` です（`strata_cli/cli.py:343-347,508-514`）。

## 実行時の動作

parser は `--json` を `bench_compare` に含む one-shot parser 群へ追加します。`main()` は status 等の一部コマンドを除き、真になった `--json` を `a.output = "json"` に変換してから `_run()` を呼びます。そのため `--output markdown` と併記しても JSON が選択されます（`strata_cli/cli.py:508-514,2232-2237`）。

比較処理は両レポートをロードしてから `bench.compare()` を呼びます。成功時は `{"schema_version":1,"ok":true,"comparison":...}` の JSON を標準出力に出し、終了コード 0 です。比較値には各 phase と指標の baseline/candidate/delta、主な phase の中央値、警告が含まれます。結果は provisional と明示され、driver・engine binary・model artifact・monitor attachment はレポートから確認できない旨が警告されます（`strata_cli/cli.py:1163-1174,535-542`; `strata_cli/bench.py:1006-1081`）。

## 適用条件と副作用

比較処理は保存レポートを読むだけで、`--json` 自体によるファイル作成・変更や benchmark の実行はありません。レポートは通常ファイルでサイズ上限 4 MiB、JSON/schema・phase 形状が検証されます（`strata_cli/bench.py:891-949`）。

両方の run が成功済みで、run ID が異なり、suite・model ID・phase 数・workload/concurrency が一致する必要があります。request evidence は phase あたり最大64件で、各 fingerprint、`max_tokens`、label の形式も検証されます。両方に source config digest がある場合は一致が必要です。報告環境の model context、slots、groups、queue 設定、devices 等は両者で一致しなければ拒否され、欠落している場合は警告になります（`strata_cli/bench.py:978-989,1006-1048`）。

このコマンドには `--out` もありますが、比較コマンドでは `--out` は `--output markdown` と併用する必要があります。`--json` を有効にしたまま `--out` を使うと、JSON 出力へ変換後に code 2 のエラーになります（`strata_cli/cli.py:1131-1133,1163-1174`）。

## 出力とエラー

成功時の JSON envelope は `schema_version: 1`, `ok: true`, `comparison` を持ちます（`strata_cli/cli.py:535-542,1173-1174`）。ロード、比較条件、`--out` の組み合わせ等で失敗した場合、JSON モードでは標準出力に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を出します。通常の `ProfileError` は `ValueError` 経路で処理され、条件により code 2 または 5、ファイル等の OS エラーは code 6 になります（`strata_cli/cli.py:527-532,2166-2183`; `strata_cli/bench.py:894-900,1008-1047`）。

## 根拠

- parser、`--output` 既定値、共通 `--json` 登録: `strata_cli/cli.py:343-347,508-514`
- `--json` から JSON 出力への変換: `strata_cli/cli.py:2232-2237`
- compare のレポート読込・成功出力と `--out` 制約: `strata_cli/cli.py:1129-1133,1163-1174`
- report のファイル・schema 検証: `strata_cli/bench.py:891-949`
- 比較の成立条件、警告、比較データ生成: `strata_cli/bench.py:978-1081`
- JSON 成功・失敗形式と終了コード経路: `strata_cli/cli.py:527-542,2166-2188`
- 索引上の配置と scope: [CLI 索引](../../../README.md) の `strata bench compare`。
