# `--concurrency`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--concurrency` |
| 別名 | なし |
| 値 | 整数。serving suite ごとに `1..16`、`parallel-overload-v1` のみ `1..64` |

## 役割

serving benchmark が同時に扱うリクエスト数を指定します。対象は `serving-smoke`、`parallel-mixed-v1`、`parallel-overload-v1`、`parallel-cancel-v1`、`parallel-prefill-cancel-v1` です。省略時は 4 です。

## 使い方

起動済みサーバーを URL で指定し、`serving-smoke` の混合負荷で同時リクエスト数を 3 にする例です。serving suite では出力先にまだ存在しないディレクトリを `--out` で指定します。

```sh
strata bench run --url http://127.0.0.1:8080 --suite serving-smoke --concurrency 3 --out ./bench-smoke-3
```

`--profile` を使う場合も、serving suite はその profile のアドレスで応答する、モデルを読み込み済みのサーバーを必要とします。この経路は標準 benchmark のように engine を起動しません。

## 値と既定値

- parser は `int` として読み込みます。省略値 `None` は serving suite の処理に入ると 4 になります。範囲は overload suite 以外が `1..16`、`parallel-overload-v1` が `1..64` です（`strata_cli/cli.py:297-303,1188-1195`）。
- 整数に変換できない値は argparse の引数エラーになります。整数でも範囲外なら `strata: concurrency must be ...` を stderr に出して終了コード 2 で終了します（`strata_cli/cli.py:1193-1196,2223-2231`）。
- `--suite standard-v1` は既定 suite ですが、このオプションの適用対象ではありません。指定すると標準プロトコルが workload を固定しているため使用不可として終了コード 2 になります。標準 suite の任意段階を追加する場合は別オプション `--optional-concurrency` を使います（`strata_cli/cli.py:297-300,315-317,1237-1248`）。

## 実行時の動作

値は serving benchmark の `bench.run()` へ渡されます（`strata_cli/cli.py:1186-1195,1219-1225`）。suite による違いは次のとおりです。

- `serving-smoke` は warmup 1 件、serial 2 件、mixed で指定数のリクエストを送ります。mixed の client worker 数も指定数です。
- `parallel-mixed-v1` は warmup 1 件、serial 2 件、mixed を 2 段階実行し、mixed の各段階で指定数のリクエストと worker を使います。
- `parallel-overload-v1` は warmup 後の overload 段階で指定数のリクエストを同時に開始します。server の admission limit より大きい数が必要です。server が `max_queue` と正の `queue_timeout` を telemetry で報告しない場合も実行できません。
- `parallel-cancel-v1` と `parallel-prefill-cancel-v1` では、値は主に実行前提の検査に使われます。前者は concurrency が server の全 effective slot 数以上であること、後者は 2 以上であることを求めます。cancel 段階の送信数はこの値から直接決めず、slot 数や cancel 用 request に基づきます。

phase ごとに `/v1/chat/completions` へストリーミング request を送り、server telemetry を取得して計測値を記録します。したがって、この値は対象 server に実 workload を発生させます。`parallel-overload-v1` では指定値が server の admission limit 以下だと拒否されます。cancel suite に必要な slot・queue・disconnect telemetry がない場合も実行前に拒否されます（`strata_cli/bench.py:223-247,549-609,744-791,815-841`）。

進行状況は出力先の `progress.json`、最終結果は `results.json` に保存されます。出力ディレクトリがすでに存在する場合は開始せず、既存内容を上書きしません（`strata_cli/bench.py:744-756,792-802,857-888`）。

## 適用条件と副作用

- `--profile` と `--url` はどちらか一方が必須です。serving suite では加えて `--out` が必須です（`strata_cli/cli.py:293-314,1183-1189`）。
- すべての suite で telemetry により loaded model と Strata instance を確認します。benchmark 中は対象 server に推論 request を送り、telemetry を定期取得します（`strata_cli/bench.py:757-765,576-590`）。同じ server 上の他の利用者の処理と競合する可能性があるため、負荷を発生させてよいタイミングで実行してください。
- overload suite は `concurrency > admission_limit` を要求します（`strata_cli/bench.py:766-774`）。`parallel-cancel-v1` は 1..16 の effective slots、disconnect telemetry、queue、2 秒以上の queue timeout を要求し、指定値が全 slot 数以上でなければ拒否します。`parallel-prefill-cancel-v1` は少なくとも 2 slots と concurrency 2 を要求します（`strata_cli/bench.py:776-791`）。
- serving suite は protocol 固定の `standard-v1` と別経路です。標準 benchmark における任意 concurrency 段階は `--optional-concurrency` が選び、4 リクエストを 3 回送る仕様です（`strata_cli/cli.py:315-317,1237-1248`; `strata_cli/bench_standard.py:852-875`）。

## 出力とエラー

human 出力では summary と `results.json` の場所を表示し、JSON 出力では成功状態・結果パス・summary を返します。request の失敗や suite の失敗は結果に記録され、benchmark が不成功なら終了コード 6 です（`strata_cli/cli.py:1226-1234`; `strata_cli/bench.py:633-666,843-888`）。引数・suite 前提条件のエラーは stderr または JSON error と終了コードで返します。たとえば、標準 suite で指定した場合、値が範囲外の場合は終了コード 2、loaded model や必要な telemetry がない場合は通常終了コード 5 です（`strata_cli/cli.py:1193-1196,1241-1248,2166-2188`; `strata_cli/bench.py:757-791`）。

## 根拠

- parser、suite の適用範囲、既定値: `strata_cli/cli.py:291-317`
- serving suite への値の既定化、範囲検査、渡し先: `strata_cli/cli.py:1183-1234`
- 標準 suite での拒否: `strata_cli/cli.py:1237-1248`
- suite ごとの request 数・worker 数、実際の request 送信: `strata_cli/bench.py:223-247,549-609,815-841`
- server telemetry と suite 固有の前提条件: `strata_cli/bench.py:744-791`
- 出力ディレクトリ、進捗・結果ファイル: `strata_cli/bench.py:792-802,843-888`
- 調査時の Strata checkout 状態: `git rev-parse HEAD` は上記 SHA、`git status --short --branch` は `## main...origin/main`（変更表示なし）。build、CLI 実行、テスト、GPU 実行、性能測定は行っていません。
