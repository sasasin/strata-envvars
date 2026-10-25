# `--optional-concurrency`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--optional-concurrency` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効 |

## 役割

標準 suite `standard-v1` の必須 workload の後に、任意の同時実行段階を追加します。追加段階では短いリクエスト4件を同時に送り、これを3ラウンド実行します（`strata_cli/cli.py:297-300,315-317`; `strata_cli/bench_standard.py:3-7,852-868`）。

## 使い方

既にモデルを読み込んだ loopback server を使って標準ベンチマークを行い、任意段階も実行する例です。benchmark は実際に推論リクエストを送るため、サーバーに負荷をかけてよいときに実行してください。

```sh
strata bench run --url http://127.0.0.1:8080 --optional-concurrency
```

`--suite` の既定値は `standard-v1` です。`--profile` を指定すると、既に稼働している profile の server を利用します。応答する server がない場合、`--no-start` がなければ CLI は profile の engine を起動して実行後に停止します（`strata_cli/cli.py:297-300,1237-1248,1292-1307`）。

## 値と既定値

- parser は `action="store_true"` で定義しており、未指定時は `False`、指定時は `True` です。値は付けません。たとえば `--optional-concurrency true` は `true` が未認識引数となり、argparse が usage とエラーを stderr に出して終了コード 2 で終了します（`strata_cli/cli.py:315-317,2223-2231`）。
- 同じフラグを複数回指定しても、真偽値が変わるだけで段階数は増えません（`strata_cli/cli.py:315-317`; `strata_cli/bench_standard.py:852-868`）。
- 未指定なら任意段階は実行せず、レポートの `run.optional_concurrency` は `false`、concurrency phase の planned 件数は 0 です。指定時は `true`、planned 件数は12になります（`strata_cli/bench_standard.py:877-879,933-940,1049-1050`）。

## 実行時の動作

- `standard-v1` の warm-up 1件、performance 9件、sanity 12件を順に実行した後に任意段階が始まります。各ラウンドでは4件分の worker を開始してから gate を開き、3ラウンドを順番に行います（`strata_cli/bench_standard.py:56-57,510-556,843-868`; fixture の request ID は `bench/prompts/standard-v1/build.json:145-203`）。
- フラグは `bench_standard.run(..., optional_concurrency=...)` に渡され、その条件で追加 requests、`concurrency_rounds`、4並列の `short-burst` summary を結果に含めます（`strata_cli/cli.py:1302-1305`; `strata_cli/bench_standard.py:852-868,925-940`）。
- `--concurrency`、`--repeat`、`--request-timeout` など serving suite 用の値を標準 suite で指定すると、フラグの有無にかかわらず workload 固定のため終了コード 2 になります。任意段階を追加する方法はこのフラグです（`strata_cli/cli.py:1241-1248`）。
- parser はこのフラグを全 suite で受理できる位置に定義していますが、serving suite の処理は `bench.run()` に進み、このフラグを渡しません。そのため serving suite と一緒に指定しても効果はありません（`strata_cli/cli.py:315-317,1183-1234,1237-1248,1302-1305`）。

## 適用条件と副作用

- 有効なのは `standard-v1` の実行経路です。対象は Strata server で、health 応答に加え loaded model が必要です。`--url` では指定先を使い、`--profile` では既存 server を使うか、`--no-start` がなければ engine 起動・停止の経路になります（`strata_cli/cli.py:1237-1248,1292-1307`; `strata_cli/bench_standard.py:781-789`）。
- このフラグにより、対象 server に最大4件を同時に送るリクエストが3ラウンド追加されます。GPU/engine を含む server workload が増え、他の処理と競合し得ます。ここでは性能向上を保証しません（`strata_cli/bench_standard.py:531-556,852-868`）。
- 出力先を `--out` で指定した場合、既存ディレクトリや symlink があると上書きせず終了コード 2 になります。省略時は `./bench/results` があればその下、なければ `./bench-results` の下に新規ディレクトリを作り、`README.md` と `results.json` などを出力します（`strata_cli/cli.py:1279-1281`; `strata_cli/bench_standard.py:777-780,834-840,899-960`）。

## 出力とエラー

- 標準実行では human 出力にレポートと結果のパスを表示し、`--output json` では JSON に `ok`、結果パス、状態、quality、summaries を出力します。フラグ指定時は結果に `run.optional_concurrency: true`、concurrency phase の request counts と rounds、summary が記録されます（`strata_cli/cli.py:1321-1328`; `strata_cli/bench_standard.py:925-940`）。
- 稼働 server がなく `--profile --no-start` を指定した場合、engine が返す失敗は終了コード 5 です。server health がない、model が未ロード、`/props` に応答しない場合も `ProfileError` の終了コード 5 になります。`--out` が既に存在する場合は終了コード 2 です（`strata_cli/cli.py:1292-1295,2166-2173`; `strata_cli/bench_standard.py:777-789`）。
- concurrency request が失敗した場合は個別結果に記録されます。server が応答しなくなった場合は後続ラウンドを skipped として記録します。optional 段階の skipped 件数は `extensions.optional_stage_skipped` に記録され、status 判定で必須段階の skipped と区別されます（`strata_cli/bench_standard.py:857-868,877-896,941-949`）。通常終了でも run status が `complete` 以外なら CLI は終了コード 6 を返します。起動した engine の停止に失敗した場合も終了コード 6 となり、stderr に警告し、可能なら `ENGINE-NOT-STOPPED.txt` を書きます（`strata_cli/cli.py:1312-1328`）。

## 根拠

- parser、suite default、値なしフラグ: `strata_cli/cli.py:297-317`
- 標準 suite と serving suite の分岐、標準 workload 固定の検査: `strata_cli/cli.py:1183-1248`
- profile の engine 起動条件、フラグを runner に渡す箇所、停止・出力: `strata_cli/cli.py:1279-1328`
- 標準 suite の事前条件、loaded model 検査、既存出力先拒否: `strata_cli/bench_standard.py:766-789`
- 同時 request の実装と任意段階の順序・中断処理: `strata_cli/bench_standard.py:510-556,843-896`
- 結果フィールド、件数、summary、optional skip 記録: `strata_cli/bench_standard.py:925-960,1041-1057`
- fixture の concurrency request ID: `bench/prompts/standard-v1/build.json:145-203`
- 調査時の状態: `git rev-parse HEAD` は上記 SHA、`git status --short --branch` は `## main...origin/main`（変更表示なし）。ソース変更、build、CLI 実行、テスト、GPU 実行、性能測定は行っていません。
