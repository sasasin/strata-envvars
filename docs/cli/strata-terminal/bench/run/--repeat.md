# `--repeat`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で未コミット変更なし。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--repeat` |
| 別名 | なし |
| 値 | 整数。serving suite では `1..5`、既定値 `1` |

## 役割

serving suite の測定フェーズを繰り返す回数を指定します。測定フェーズの再実行数を揃え、各 run の phase evidence と結果を保存します。標準 suite (`standard-v1`) は固定プロトコルなので、このオプションを指定できません。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8080 --suite serving-smoke --repeat 3 --out ./bench-results/smoke-repeat-3
```

`--url` と `--profile` は排他的に一方が必須です。serving suite では `--out` にまだ存在しない出力ディレクトリも必要です。例の URL はローカルの稼働中 Strata server を指し、出力先は新規ディレクトリにしてください（`strata_cli/cli.py:294-311`）。

## 値と既定値

- parser は `type=int, default=None` として受理します。省略時の `None` は serving suite の分岐で `1` に置き換えられます（`strata_cli/cli.py:303`, `strata_cli/cli.py:1188-1195`）。
- serving suite の値域は `1..5` です。`0`、負数、`6` 以上は benchmark を始める前に拒否され、終了コード `2` のエラーになります。人間向け出力は stderr の `strata: ...`、`--output json` では機械可読 JSON です（`strata_cli/cli.py:1193-1196`, `strata_cli/cli.py:527-532`）。整数でない引数は argparse の型変換エラーです。
- `standard-v1` が既定 suite です。この suite では `--repeat` を明示すると、たとえ `--repeat 1` でも「適用されないオプション」として終了コード `2` で拒否されます。未指定のままなら固定ワークロードで続行します（`strata_cli/cli.py:297-300`, `strata_cli/cli.py:1186-1187`, `strata_cli/cli.py:1241-1248`）。

## 実行時の動作

serving suite に渡された回数は `bench.run()` に渡り、予定 phase の一覧、進捗記録、phase 実行ループに使われます（`strata_cli/cli.py:1221-1225`, `strata_cli/bench.py:744-752`, `strata_cli/bench.py:795-802`）。suite ごとの適用は次のとおりです（`strata_cli/bench.py:50-54`, `strata_cli/bench.py:117-120`, `strata_cli/bench.py:815-841`）。

| Suite | `--repeat` の対象 |
| --- | --- |
| `serving-smoke` | `serial` と `mixed` |
| `parallel-mixed-v1` | `serial` と `mixed`（suite 定義内に `mixed` が2回あり、それぞれ反復） |
| `parallel-overload-v1` | `overload` |
| `parallel-cancel-v1` | 対象 phase なし。cancel phase と `warmup` / `recovery` は各1回 |
| `parallel-prefill-cancel-v1` | 対象 phase なし。cancel phase と `warmup` / `recovery` は各1回 |

したがってキャンセル suite でも値は `1..5` に検証されますが、現在の phase 構成では `--repeat` を変えても実行回数は変わりません。全 serving suite で `warmup` と `recovery` は1回だけです。途中で operator cancellation が起きた場合や、overload 以外の phase が失敗した場合、後続・反復 phase は打ち切られ得ます（`strata_cli/bench.py:827-842`）。

実行前には serving suite の入力値域を検証し、出力先が既存または symlink なら拒否します。また、稼働中で versioned telemetry を返す Strata instance と loaded model が必要です（`strata_cli/bench.py:748-760`）。出力先を新規作成し `progress.json` に予定 phase と進捗を書き、終了時に `results.json` を作成します。成功判定は全予定 phase の完了・成功などに依存します（`strata_cli/bench.py:792-802`, `strata_cli/bench.py:848-888`）。測定リクエストは指定先 server に送られます。

## 適用条件と副作用

- `--repeat` は `strata bench run` の引数です。`strata bench` の別サブコマンドには適用されません。索引でも `bench/run` の scope に置かれています（[`docs/cli/README.md`](../../../README.md) の `strata bench run` 節）。
- serving suite は `--profile` または `--url` のいずれかで対象 server を指定し、`--out` の新規ディレクトリへ進捗・結果を記録します。`--profile` が保存済み profile の場合は benchmark lease も取得します（`strata_cli/cli.py:294-311`, `strata_cli/cli.py:1219-1225`）。
- このオプションは相手 server の設定や GPU 設定を変える処理ではなく、suite の phase 実行回数を変えます。ただし値が増えると対象 server への測定リクエストと実行時間が増えます。性能向上を意味する設定ではありません。
- 比較可能な報告の読み込み時も、予定 phase は repeat `1..5` のいずれかとして検証されます（`strata_cli/bench.py:939-948`）。

## 出力とエラー

- 値域エラーや `standard-v1` での明示指定は終了コード `2` です（`strata_cli/cli.py:1194-1196`, `strata_cli/cli.py:1241-1248`）。
- serving suite の run は人間向けまたは JSON の summary と、`results.json` のパスを出力します。すべての phase が成功しなければ終了コード `6` になり得ます（`strata_cli/cli.py:1226-1234`）。反復中に失敗・キャンセルした場合も部分的な phase 結果を保存して成功扱いにしない経路があります（`strata_cli/bench.py:827-888`）。

## 根拠

- parser、値型・既定値、suite option の scope: `strata_cli/cli.py:291-314`
- 標準 suite での明示指定拒否と serving suite の既定値・範囲検査: `strata_cli/cli.py:1183-1196`, `strata_cli/cli.py:1241-1248`
- phase 定義、repeat 対象、計画と実行、停止条件: `strata_cli/bench.py:50-54`, `strata_cli/bench.py:117-120`, `strata_cli/bench.py:815-888`
- 結果 report の phase-plan 検証: `strata_cli/bench.py:939-948`
- 索引上のコマンド階層と option scope: `docs/cli/README.md:610-637`

調査範囲は上記 checkout のソースと Strata リポジトリ内の `docs/BENCHMARK_PROTOCOL.md` です。CLI help や Release 配布物との照合は行っていません。標準 suite の固定ワークロードについては、同 protocol が `--repeat` を拒否すると記載しています（`docs/BENCHMARK_PROTOCOL.md:42-44`）。
