# `strata bench`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/bench.py`、`strata_cli/bench_standard.py` |

## 役割

Strata の稼働サーバーに実際の推論リクエストを送り、ベンチマーク結果とローカルの証跡ファイルを作成・表示・比較するコマンドです。`bench` の下には実行、実行中 run のキャンセル、保存済み結果の表示、2件の結果の比較があります。サブコマンドは必須です。

この Terminal CLI の `strata bench` は、ソース checkout に同梱される `bench.sh` / `BENCH.bat` と同じ quick speed check ではありません。標準プロトコルの結果形式と固定 workload は `strata bench run` が実装し、quick benchmark は別の入口です（`strata_cli/cli.py:291-294`、`docs/BENCHMARK_PROTOCOL.md:13-18`）。

## 代表的な使い方

```sh
# 保存済み profile で標準プロトコルを実行
strata bench run --profile NAME --track default --track-notes "release と setup の設定"

# 既に稼働しているサーバーへ標準プロトコルを実行
strata bench run --url http://127.0.0.1:8080

# serving suite の結果を、新規ディレクトリに保存
strata bench run --profile NAME --suite serving-smoke --out ./bench-run-01

# 保存済み結果を表示し、2件を比較
strata bench report ./bench-run-01
strata bench compare ./baseline ./candidate
```

オプション、値、既定値は各サブコマンドの文書を参照してください。

## 実行モード

| サブコマンド | 主な動作 |
| --- | --- |
| `run` | `--suite standard-v1`（既定）では固定の標準ベンチマークを実行します。`--suite serving-smoke` や `parallel-*` は稼働中 Strata サーバーに対する serving suite で、同一条件の運用比較向けです。 |
| `cancel` | 保存済み profile と絶対パスで指定した、現在実行中の対象 run だけにキャンセル要求を記録します。 |
| `report` | 保存済みレポートを読み直して検証し、人間向け・JSON・Markdown 形式で要約します。標準結果と serving suite 結果の両方を扱います。 |
| `compare` | baseline と candidate の結果を読み、成功 run であり workload 等が比較可能か検査してから比較します。 |

## `run` の主な動作と副作用

- 標準 suite は `--profile` で指定したエンジンを起動してモデル読み込みを待ち、ベンチマーク後にこの run が起動したエンジンを停止します。profile のサーバーがすでに応答している場合は既存サーバーを使い、停止しません。`--no-start` は profile のエンジン起動を禁止します（`strata_cli/cli.py:1237-1239,1292-1307`）。
- `--url` は指定先のサーバーを使います。標準 suite はサーバーの health、モデル読み込み状態、props などを確認してからリクエストします。固定 workload の標準 suite では concurrency・repeat・request timeout は変更できず、異なる運用条件を調べるときは serving suite を選びます（`strata_cli/bench_standard.py:781-789`、`strata_cli/cli.py:1241-1248`）。
- serving suite は、ロード済み Strata instance と versioned telemetry を必要とし、実行中にベンチマーク用リクエストを送ってテレメトリーの前後状態を記録します。suite ごとに server の queue、slots、disconnect telemetry 等の前提条件があります（`strata_cli/bench.py:744-791,812-888`）。
- 結果は新しい出力先に保存されます。標準 suite は既定で `./bench/results/`（存在するとき）、それ以外は `./bench-results/` の下に run ディレクトリを作り、`results.json` と `README.md` を保存します。serving suite は `--out` を必須とし、`progress.json` と `results.json` を書きます。存在する出力先は再利用せずエラーになります（`strata_cli/cli.py:1188-1196,1279-1281`、`strata_cli/bench_standard.py:766-780,958-960`、`strata_cli/bench.py:755-756,792-802,884-887`）。
- 保存済み profile を使う run は、同じ profile での重複実行を lease で拒否します（`strata_control/benchmarking.py:82-102`）。

標準 suite はモデルファイルの hash も取得し、レポートには実行環境・設定・リクエスト結果等を含みます。共有前に生成レポートを確認してください。利用者名、ホスト名、private address、API key などは一部置換されますが、すべての機密情報を自動判定できるわけではありません（`docs/BENCHMARK_PROTOCOL.md:42-51`）。

## 注意点

- 標準 suite のプロトコル文書はこの revision で draft と記載され、pilot validation pending です（`docs/BENCHMARK_PROTOCOL.md:1-4`）。結果の解釈や外部公開時にはその状態を考慮してください。
- profile の標準 run で CLI が起動したエンジンを停止できなかった場合、run は失敗扱いになり、`ENGINE-NOT-STOPPED.txt` を出力先に作成し、stderr に手動停止が必要な旨を表示します（`strata_cli/cli.py:1306-1320`）。
- `report` / `compare` の `--out` は Markdown 出力時のみ指定でき、既存ファイルを上書きしません（`strata_cli/cli.py:1132-1133`、`strata_cli/bench.py:1301-1308`）。
- CLI entry point は `bench` を含む `serve` / `bench` の実行前に API server 依存パッケージを確認し、不足時は stderr に案内して終了コード 5 で終了します。起動時に pip install は実行しません（`strata.py:14-27,39-43`）。

## 関連文書

- [`strata bench run` の概要とオプション一覧](../run/README.md)
- [`strata bench cancel`](../cancel/README.md)、[`strata bench report`](../report/README.md)、[`strata bench compare`](../compare/README.md)
- [CLI 文書索引](../../README.md)
- [標準ベンチマークプロトコル](../../../BENCHMARK_PROTOCOL.md)
- [Community benchmark guide（quick benchmark）](../../../COMMUNITY_BENCHMARKS.md)

## 根拠

- `strata_cli/cli.py:291-347` — `bench` および各サブコマンドの parser と実行例に関わる引数定義。
- `strata_cli/cli.py:1129-1234` — `report`、`compare`、`cancel`、serving suite の分岐、検証、実行、結果出力。
- `strata_cli/cli.py:1237-1328` — 標準 suite の実行経路、profile server / engine の扱い、結果と失敗処理。
- `strata_cli/bench.py:744-888,891-910,1006-1020,1301-1308` — serving suite の前提条件・進捗/結果保存、レポート読込・比較、Markdown 出力。
- `strata_cli/bench_standard.py:766-810,930-960` — 標準 suite の server 検査、レポート組立と新規ファイル作成。
- `strata_control/benchmarking.py:82-102,138-168` — profile 単位の重複 run 防止と正確な run へのキャンセル要求。
- `strata.py:14-27,39-43` — `bench` 実行前の依存パッケージ検査。
- `docs/BENCHMARK_PROTOCOL.md:1-18,28-51` — 標準プロトコルの状態、quick benchmark との区別、利用方法とレポート注意事項。
