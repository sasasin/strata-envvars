# `--hold`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の対象リポジトリは `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--hold` |
| 別名 | なし |
| 値 | 探索次元 ID を1つ指定（例: `kv`）。同じオプションを複数回指定できます。 |

## 役割

指定した探索次元を候補探索から外し、基準測定では固定値として扱うためのオプションです。`--hold` は `strata tune plan` にもありますが、ここでは索引で指定された `strata tune run` の parser と実行経路を説明します。索引上のコマンド階層は `tune/run` です（`docs/cli/README.md` の `strata tune run` 節）。

現行 revision では、通常の次元を hold したときに固定値が測定用引数へ正しく変換されない問題があります。計画の意図と実際の実行結果を区別して利用してください。

## 使い方

```sh
strata tune run --engine /path/to/strata --backend cuda --model example-model --hold kv --hold spec_min_p
```

`--engine`、`--backend`、`--model` は `run` の必須引数です。上の例の `kv`、`spec_min_p` は探索次元 ID です。これらの通常次元は現行実装で後述の不整合に当たるため、この例は構文を示すものであり、正常な固定測定を保証しません（parser: `strata_cli/cli.py:414-459`、次元定義: `strata_control/tuning.py:72-118`）。

## 値と既定値

- `action="append"`、`default=[]` で、指定するたびに値を文字列のリストへ追加します。指定を省略すると hold はありません（`strata_cli/cli.py:456-457`）。
- parser に `choices`、`type`、独自の値 validator はありません。`--hold` の直後に値がなければ argparse が構文エラーにし、使用法を表示して終了コード 2 とします。空文字列は引数として渡せますが、次元 ID と一致しないため未知 ID と同様に扱われます（`strata_cli/cli.py:40-45,456-457`; argparse の標準処理）。
- 重複値は parser 上は複数回記録されますが、計画作成時に `set(hold)` へ変換されるため、効果は一度の指定と同じです（`strata_control/tuning.py:736-743`）。
- ID は `ple_io`、`kv`、`kv_grow`、`expert_cache`、`host_core`、`pool_affinity`、`pool_workers`、`spec_min_p`、`vram_reserve`、`pcie_frac`、`prompt_cache_tail` などです。ただし、実際に候補として提示されるのは backend と engine が対応するフラグにより許可された次元だけです（`strata_control/tuning.py:72-118,151-174`）。

## 実行時の動作

`strata tune run` は engine の `--help` 出力から受理フラグを読み、次元ごとに backend 条件と必要フラグの有無を検査します。engine が実行できない場合はフラグ一覧を取得できない状態として記録され、取得できた場合はエンジンが受け付けない次元を除外します（`strata_control/tuning.py:151-174,205-224`）。

hold が有効な次元 ID と一致すると、その次元は `plan.dimensions`（候補探索対象）から除かれ、`plan.fixed` に入ります。未知 ID、または選択 backend / engine では提供されない ID はエラー終了にならず、除外理由 `held constant, or not a dimension of this backend` として計画に記録されます（`strata_control/tuning.py:734-752`）。そのため、綴り間違いでも hold が適用されたようにはなりません。

**実装上の不整合:** 通常の次元を hold すると `plan.fixed` の値は `None` です。基準測定の引数生成はその値を省略せず文字列 `"None"` に変換し、対応する engine フラグへ渡します（`strata_control/tuning.py:739-740,427-429,557-575`; `strata_control/tune_engine.py:415-420`）。例えば `--hold kv` では `--kv None` 相当になります。engine 側は `--kv` の値を読み、その後 `fp16`、`int8`、`q4_0`、`k8v4` 以外を拒否するため、この基準測定は通常 `--kv` の値エラーになります（`src/program/generate.cpp:2480,3186-3189`）。したがって、通常次元について「hold すればエンジン既定値を使って正常に測定できる」とはこの revision のソースから確認できません。

一方、`prompt_cache_tail` は benchmark-only 次元として登録され、基準測定では「engine 自身の既定値に固定」と plan に記録されます。benchmark-only の設定は実運用向け引数に出力されない実装です（`strata_control/tuning.py:117-118,739-740,557-575`）。この次元が候補に含まれるかは backend と engine のフラグに依存します。

hold は探索候補数を減らすため、測定する設定と推薦対象に影響します。Tuner は hold 済み設定から baseline を測定し、baseline が成功した場合は残りの次元の組合せを候補測定し、最後に baseline を再測定します（`strata_control/tuning.py:423-475,525-555`）。`--hold` 自体はプロファイルを変更しません。`tune run` の推薦適用は別の `strata tune apply` 操作です（`strata_cli/cli.py:1840-1846`）。

## 適用条件と副作用

- 次元候補は `strata_control/tuning.py` の静的な次元表だけで決まらず、指定 backend および実 engine の `--help` で確認されたフラグにも依存します。条件に合わない hold ID は除外理由として残ります（`strata_control/tuning.py:151-174,205-224,734-752`）。
- run は engine の `--help` を子プロセスとして実行してフラグを調べます。測定時にはさらに engine を起動します（`strata_control/tuning.py:205-224`; `strata_control/tune_engine.py:415-420`）。
- tuning job は状態ディレクトリに記録され、排他 lease を取得します。baseline を含む測定が行われ、hold した通常次元の前述の不整合により baseline が失敗しても、その job の測定記録は作られます（`strata_control/tuning.py:423-431,477-484`）。
- backend に提供可能な次元がない場合も、hold の有無とは別に baseline を測定して候補探索を行わない経路があります（`strata_control/tuning.py:433-440`; `strata_cli/cli.py:1798-1800`）。

## 出力とエラー

- 人間向け出力では探索する次元 ID と測定方式を表示します。hold 指定が不明または非対応の場合、その ID と除外理由は plan に含まれます（`strata_cli/cli.py:1788-1800`; `strata_control/tuning.py:741-752`）。
- `--output json` では成功時に job を JSON で出力します。測定できない候補や baseline は job の report/status に失敗として記録されます（`strata_cli/cli.py:1802-1807`; `strata_control/tuning.py:423-482`）。
- 測定失敗は job の状態・report に記録されます。`Tuner.run()` が例外も `failed` job として保存して返すため、`_tune_run()` はその結果を通常の出力経路へ進めて終了コード 0 を返します。従って、hold 由来の測定失敗は必ずしも CLI の非 0 終了コードにはなりません（`strata_control/tuning.py:477-482`; `strata_cli/cli.py:1802-1847`）。
- engine path が存在しない場合は stderr にエラー（JSON 出力時はエラー JSON）を出し、終了コード 2 です（`strata_cli/cli.py:1759-1762,527-532`）。通常次元の hold による無効な値は `--hold` 自体の parser エラーではなく、測定候補の engine 起動失敗として扱われます（`strata_control/tuning.py:477-482`; `src/program/generate.cpp:3186-3189`）。
- `--mode api` では `--config` と `--api-expect` が必須です。不足時は stderr（JSON 指定時はエラー JSON）と終了コード 2 になります（`strata_cli/cli.py:1771-1784`）。これらは `--hold` 固有の制約ではありません。

## 根拠

- `strata_cli/cli.py:414-459` — `strata tune run` parser と `--hold` の宣言。
- `strata_cli/cli.py:1742-1807,1840-1846` — 実行計画への引き渡し、測定・出力、推薦適用が別操作であること。
- `strata_control/tuning.py:72-118,151-174,205-224,723-768` — 次元 ID と backend / engine による許可、hold の計画上の処理。
- `strata_control/tuning.py:423-482,525-575` — baseline / 候補の測定順、組合せ生成、測定引数への変換。
- `strata_control/tune_engine.py:415-420` — 測定 engine の argv へのフラグ・値の追加。
- `src/program/generate.cpp:2480,3186-3191` — `--kv` の受け取りと許容値検査の例。

調査範囲は上記 checkout の Python CLI・tuning 実装と `generate.cpp` の `--kv` 処理です。実バイナリを起動した動作確認、他 backend の測定、Release 配布物の照合は行っていません。
