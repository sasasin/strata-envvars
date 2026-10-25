# `strata bench run --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ JSON 出力を選ぶ別フラグ） |
| 値 | `human` または `json` |

## 役割

ベンチマーク実行結果を標準出力へ人向けテキストまたは機械処理向け JSON で表示します。標準 suite と serving suite のどちらでも使えます。結果ファイルの保存先を指定するオプションではありません。

## 使い方

```sh
strata bench run --url https://strata.example --output json
```

この例は既定の `standard-v1` suite を使います。保存先は別の `--out` で指定できます。`--profile` を使う場合も同様に `--output json` を追加します。

## 値と既定値

- `human`: 人向け表示。省略時の既定値です。
- `json`: 1行の JSON を標準出力へ出します。
- parser はこの2値だけを受理します。別の値を渡すと argparse が usage とエラーを標準エラーへ出し、終了コード 2 で終了します。この段階では JSON エラー形式になりません。
- 同じ parser にある `--json` は `--output json` の別表記です。`--json` を付けると main 処理が `--output` の値を `json` に設定するため、両方を指定した場合も JSON になります。

## 実行時の動作

`--output json` は表示形式を切り替えます。ベンチマークの種類、測定内容、保存処理は切り替えません。標準 suite では JSON に schema version、成功状態、結果ディレクトリ内の `results.json` の絶対パス、status、quality、summaries が含まれます。serving suite では schema version、成功状態、`results.json` の絶対パス、summary が含まれます。通常の進行ログはベンチマーク処理中に標準エラーへ送られ、JSON は標準出力に出ます。

`--quiet` と併用した場合、human モードでは通常の標準出力を抑え、失敗時には捕捉した表示を標準エラーへ出すことがあります。JSON モードでは quiet による標準出力の捕捉を行わず、JSON レコードを標準出力へ出します。

両 suite とも結果ファイルは別途作成されます。標準 suite は `results.json` と `README.md` を新規作成し、serving suite は `results.json` と進捗ファイルを保存します。JSON 出力を選んでも既存ディレクトリへ上書きする動作にはなりません。既存の出力ディレクトリは拒否されます。

失敗時も、処理段階に応じて JSON エラーまたは JSON の結果レコードが標準出力に出ます。標準 suite と serving suite の完了・失敗結果は `ok` と終了コードで表され、正常終了は 0、ベンチマーク失敗は 6 です。事前条件など `_error` を通るエラーは `ok: false` とエラー情報を含む JSON を出し、個別に定めた終了コードを返します。オプション値の argparse 検証エラーはこの経路より前に発生します。

## 適用条件と副作用

このオプションは `strata bench run` 専用です。`strata bench report` や `strata bench cancel` における同名オプションの仕様は、それぞれ別 parser スコープです。

出力形式による標準出力の差以外に `--output` 固有のファイル、ネットワーク、server、GPU への副作用はありません。ただしコマンド自体は選択した suite の測定を実行し、結果ディレクトリを作成します。JSON を利用する自動処理では、進行ログが標準エラーへ出る点を考慮してください。

## 根拠

- `strata_cli/cli.py:293-314` — `bench run` parser、`--output` の値・既定値、suite と `--out` の定義。
- `strata_cli/cli.py:508-515` — one-shot コマンドで `--json` を `--output json` の alias とし、quiet option を登録。
- `strata_cli/cli.py:1129-1133, 1183-1234` — JSON モード判定、serving suite の前提検証、stdout/stderr の分離、JSON/human 出力と終了コード。
- `strata_cli/cli.py:1237-1328` — standard suite の workload 制約、処理ログの stderr 転送、JSON/human 出力、終了コード。
- `strata_cli/cli.py:527-542, 2166-2193, 2223-2235` — JSON エラー形式、処理例外、parser 後の `--json` 適用。parser 自体の不正値は dispatch より前に拒否。
- `strata_cli/bench_standard.py:771-785, 834-839, 953-960` — standard suite の出力先競合検査と新規結果ファイル作成。
- `strata_cli/bench.py:744-760, 792-802, 881-887` — serving suite の出力先競合検査、進捗・結果ファイル作成。

索引の配置は [`docs/cli/README.md`](../../../README.md) の `strata bench run` 節に一致します。調査時点で作成先は存在しませんでした。調査はソースコードの静的確認に限り、CLI help の実行、build、ベンチマーク、GPU 実行、テストは行っていません。
