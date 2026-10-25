# `strata tune run --repeats`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--repeats` |
| 別名 | なし |
| 値 | 整数。1 未満は実行計画で 1 に補正 |
| 既定値 | `3` |

## 役割

各ベースライン・候補設定の測定を何回集計するかを指定する。既定値は 3 回で、実行計画に記録した回数以上の有効測定が揃わない候補は推薦対象にならない。`strata tune plan` にも同名オプションがあるが、これは `strata tune run` の説明であり、両者の parser 定義は別である（`strata_cli/cli.py:405-409,414-426`）。

## 使い方

```sh
strata tune run --engine /path/to/strata-engine --backend cuda --model example --repeats 5
```

`--engine`、`--backend`、`--model` は `run` で必須。例の engine パスや backend は利用環境に合わせる（`strata_cli/cli.py:414-426`）。

## 値と既定値

- parser は `type=int`、既定値 `3` で受け付ける。整数に変換できない文字列は argparse の解析エラーとなり、`_tune_run` には到達しない（`strata_cli/cli.py:425-426`）。
- parser に最小値の指定や追加 validation はない。計画生成時に `max(1, int(repeats))` が使われるため、`0` や負数はエラーにならず `1` として扱われる（`strata_control/tuning.py:762-767`）。
- 明示しなければ `3`。計画上の値は job の plan と report に記録される（`strata_cli/cli.py:425-426`; `strata_control/tuning.py:644`）。

## 実行時の動作

1. `strata tune run` は値を `plan_tuning(..., repeats=a.repeats)` に渡す（`strata_cli/cli.py:1763-1768`）。
2. ベースライン、各候補、最後のベースライン再測定について、それぞれ最初にウォームアップ測定を 1 回行う。その後、計画の `repeats` 回を集計対象として測る。したがって `--repeats N` は総起動回数ではなく、各設定あたり集計する反復数であり、正常に進めば各設定はウォームアップ分を含めて `N + 1` 回測定される（`strata_control/tuning.py:423-470,486-523`）。
3. 候補の推薦には、成功状態で少なくとも `repeats` 件の測定値が必要。さらに目的指標の中央値がベースラインより改善し、候補の最悪値がベースラインの最悪値より悪くないことが条件となる（`strata_control/tuning.py:596-620`）。反復を増やすと、この必要測定数と各候補の実測回数も増える。
4. 実行時間は `--trials` と `--time` にも左右される。時間上限は新しい候補を開始する前に調べ、進行中の候補の反復を途中で打ち切る条件ではない。また上限後でもベースライン再測定は行う（`strata_control/tuning.py:439-469`; `strata_cli/cli.py:421-426`）。
5. 既定の `--mode protocol` は engine の serve protocol で測定する。`--mode api` では `--config` と `--api-expect` が必須で、同じ反復処理を HTTP API 測定に適用する（`strata_cli/cli.py:431-434,1771-1786`; `strata_control/tune_api.py:259-292`）。

測定関数は設定ごとに engine/worker を起動し、測定後に終了する。protocol mode は engine に workload を送り、API mode は指定 config のコピーを一時 JSON ファイルに書いて worker を起動し、終了後そのファイルを削除する（`strata_control/tune_engine.py:388-432,596-608`; `strata_control/tune_api.py:265-292`）。

## 適用条件と副作用

- `--repeats` は候補の値探索範囲や候補数を変更せず、各設定を測る回数と推薦に必要な測定数を変更する。`--hold` などで検索次元がなくても、baseline は測定される（`strata_control/tuning.py:423-440,502-523,525-555`）。
- 反復を増やすほど各設定での engine 起動・workload 実行が増える。ベースラインと再測定も対象なので、最大候補数を `T`、反復数を `N` とした正常経路では、測定呼び出しは最大で `(T + 2) × (N + 1)` 回となる。時間上限や失敗で候補数・測定回数はこれより少なくなり得る（`strata_control/tuning.py:423-470,486-523`）。
- run は job ごとに状態ファイル `job.json` を保存し、実行中はその job のディレクトリに排他的 lease ファイルを作る。既定の保存先は `STRATA_TUNE_DIR` があればその値、なければ Strata の state base 以下の `tuning`。`--state-dir` で保存先を指定できる（`strata_cli/cli.py:1643-1650,458-459,1708-1709`; `strata_control/tuning.py:325-362,389-419`）。
- sweep は実行中に active profile を変更しない。推薦の適用は別の `strata tune apply` 操作である（`strata_cli/cli.py:1750-1755,1840-1846`）。

## 出力と失敗

- 人間向け出力は job ID/state、baseline の測定数、実行した候補数、失敗候補、推薦などを表示する。JSON 出力は job 全体を含む成功レスポンスを返す（`strata_cli/cli.py:1805-1846`）。
- baseline の測定に失敗すると候補探索は行わず、レポートに `baseline_failed` を記録し、推薦なしとなる（`strata_control/tuning.py:429-460,596-620`）。候補の測定失敗や token なし・API の正当性チェック失敗は、その候補の status/reason に記録され、成功候補として選ばれない（`strata_control/tuning.py:486-523`）。
- 同じ job ID の lease が残っている場合、実行は例外経路になり job を `failed` として記録する。job ID は plan ごとに生成される（`strata_control/tuning.py:389-407,476-483,762-764`）。engine ファイルが存在しない場合や API mode で必須指定がない場合は JSON/human 形式のエラーを返し、終了コード `2` となる（`strata_cli/cli.py:1759-1762,1771-1779`）。

## 根拠

- parser と `run` 固有の既定値: `strata_cli/cli.py:414-426`
- plan への引き渡しと mode 別測定関数: `strata_cli/cli.py:1759-1786`
- repeat の補正、ウォームアップと反復、計測失敗時の処理: `strata_control/tuning.py:486-523,762-767`
- 候補数・時間上限、baseline 再測定、job の保存と lease: `strata_control/tuning.py:325-362,389-419,423-483`
- 推薦に必要な反復数と選定規則: `strata_control/tuning.py:596-620,644`
- protocol harness と API harness の起動・後始末: `strata_control/tune_engine.py:388-432,596-608`; `strata_control/tune_api.py:259-292`
- state directory と run dispatch、出力: `strata_cli/cli.py:1643-1650,1708-1709,1805-1846`

## 関連文書

- [`strata tune plan --repeats`](../plan/--repeats.md)
- [CLI 索引](../../../README.md)
