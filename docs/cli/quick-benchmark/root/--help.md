# `--help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（`2026-10-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `python tools/strata_bench.py`（`bench.sh` / `BENCH.bat` からも起動） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。`argparse` が自動で登録するヘルプフラグ |

## 役割

quick benchmark の使用法と、同じ parser に登録されたオプション一覧を表示して終了します。Strata の `strata bench run` が行う標準 benchmark とは別の、`tools/strata_bench.py` の CLI ヘルプです。

## 使い方

Strata checkout のルートで直接実行する場合:

```sh
python tools/strata_bench.py --help
```

セットアップ済み checkout では wrapper からも渡せます:

```sh
./bench.sh --help
```

## 値と既定値

値は取りません。短縮形 `-h` と長形式 `--help` は同じ parser に登録されています。`ArgumentParser` の既定動作で生成されるため、`default` や `type` の個別設定はありません。parser は `--config`, `--url`, `--port`, `--gpu`, `--api-key`, `--runs`, `--clients`, `--long`, `--think`, `--out`, `--compare`, `--compare-only`, `--ready-timeout`, `--quiet` も登録しています。

## 実行時の動作

`main()` は parser を作成し、`parse_args()` を実行します。`--help` / `-h` が指定されると `argparse` が usage、description、登録済み引数を表示して処理を終了するため、通常の benchmark 実行、結果比較、レポート書き込み、サーバー起動には進みません。通常処理に進む設定判定や server 起動は `parse_args()` の後にあります。

スクリプトは parser を構築する前に `ab_engine`、`agent_turns_bench`、`serve_load` を import します。これらの import が失敗した場合はヘルプ表示まで到達しません。ヘルプ経路がそれらの import 以外にファイル・ネットワーク・プロセス・GPU へ作用する処理は、確認した `strata_bench.py` の範囲ではありません。

## 適用条件と副作用

`bench.sh` は checkout ルートへ移動して `.venv/bin/python` でスクリプトを起動します。venv がない場合はセットアップを促して終了し、Python parser のヘルプは表示しません。Windows の `BENCH.bat` も `.venv\Scripts\python.exe` の存在を確認してから引数を転送します。直接の `python tools/strata_bench.py --help` は wrapper の venv 条件を通りません。

## 出力とエラー

ヘルプは `argparse` が生成して標準出力へ表示し、成功終了します。未知の引数など parser エラーでは `argparse` が usage とエラーを表示して終了コード 2 で終了します。いずれも `main()` の後続 benchmark 処理には入りません。wrapper 経由の場合、Windows batch は Python の終了コードを保存して返します。

## 根拠

- `tools/strata_bench.py:30-55` — `argparse` と依存モジュールの import。
- `tools/strata_bench.py:932-948` — `ArgumentParser` の生成、全 option 登録、`parse_args()`。
- `tools/strata_bench.py:951-959` — parser 処理後の通常分岐開始。
- `tools/strata_bench.py:983-999` — benchmark 実行経路での server 再利用・起動。
- `tools/strata_bench.py:1017-1018` — benchmark 結果の書き込み。
- `tools/strata_bench.py:1040-1041` — CLI entry point。
- `bench.sh:6-13` — Linux wrapper の venv 条件と引数委譲。
- `BENCH.bat:8-18` — Windows wrapper の venv 条件・引数委譲・終了コード。
- 索引の位置とスコープ: `docs/cli/README.md:1522-1544`。
- quick benchmark と標準 benchmark の区別: `docs/BENCHMARK_PROTOCOL.md:13-18`、`docs/COMMUNITY_BENCHMARKS.md:96-105`。
