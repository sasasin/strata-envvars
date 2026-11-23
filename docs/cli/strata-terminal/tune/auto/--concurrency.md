# `strata tune auto --concurrency`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--concurrency` |
| 別名 | なし |
| 値 | 整数 `N`。省略時は `1`、明示値は `2`〜`8` |

## 役割

自動チューニングで各設定を比較するとき、逐次リクエストではなく複数リクエストを同時に処理したときの合計生成速度で評価する。複数の利用者や agent が同じモデルを同時利用する状況を想定した測定であり、単一リクエストの速度測定とは評価条件が異なる。parser は `N` を整数として受け付け、既定値を `1` にする（`terminal/strata_cli/tune_commands.py:21-36`）。

## 使い方

```sh
# 4 件同時のリクエスト負荷で、モデル設定を比較する
strata tune auto qwen/IQ3_S --concurrency 4

# 同じ負荷条件の測定計画だけを表示し、engine は起動しない
strata tune auto qwen/IQ3_S --concurrency 4 --plan
```

`target` にはインストール済みモデル名、保存 profile 名、または run configuration の JSON を指定できる（`terminal/strata_cli/tune_commands.py:27`、`terminal/strata_cli/tune_commands.py:117-140`）。

## 値と既定値

- 省略時は `1`。この場合は同時負荷の評価フェーズを設けず、従来どおり 1 件ずつ測定する（`terminal/strata_cli/tune_commands.py:35`、`terminal/strata_control/autotune.py:104-107`）。
- 明示値は `2`〜`8`。`0`、負数、`1` の明示、`8` 超は `strata tune auto` の実行処理で拒否され、終了コード `2` になる（`terminal/strata_cli/tune_commands.py:332-335`）。値を整数に変換できない場合は `argparse` の型変換エラーとなる（`terminal/strata_cli/tune_commands.py:35`）。
- 同じオプションを複数回指定する場合、parser に特別な重複処理はなく通常の `argparse` の値保持に従う（登録箇所: `terminal/strata_cli/tune_commands.py:35`）。

## 実行時の動作

指定値は tuner の `Options.concurrency` に渡され、測定用 `RequestSet.clients` になります（`terminal/strata_cli/tune_commands.py:342-345`、`terminal/strata_control/autotune.py:386-395`）。`N > 1` では測定 worker 用の設定コピーに `parallel: N` を設定します。worker は利用者の run configuration をコピーして run ごとの JSON に保存し、loopback の `serve.server` を起動して測定します（`terminal/strata_cli/tune_commands.py:371-376`、`terminal/strata_control/tune_session.py:484-495`、`terminal/strata_control/tune_session.py:536-564`）。

worker は同時リクエストの負荷を一度ウォームアップした後、3 回測定します。各回は `N` 個のスレッドからそれぞれ 200 token を要求し、完了までの経過時間に対する全リクエストの生成 token 数で合計 token/s を算出します（`terminal/strata_control/tune_session.py:386-409`、`terminal/strata_control/tune_session.py:445-456`）。この負荷測定値が得られると、`chat` / `coding` のどちらを選んでもその値が設定評価の指標になります（`terminal/strata_control/autotune.py:146-162`）。`--plan` を付けた場合は同じ concurrency を含む計画を表示して終了し、測定 worker は作成されません（`terminal/strata_cli/tune_commands.py:349-353`）。

結果が `improved` または `default_confirmed` で `--no-save` を付けていない場合、preset が保存されます。`N > 1` で保存した preset は concurrency を choices に記録し、後の起動時に単一リクエストで動く設定には適用しません（`terminal/strata_cli/tune_commands.py:396-410`、`terminal/strata_control/presets.py:482-519`）。保存済み preset を通常起動に反映する挙動自体は、このオプションの測定時ではなく preset overlay 側で判定されます。

## 適用条件と副作用

- 指定値に合わせて測定用 worker の同時処理数を要求する。engine が報告した `batch_slots` が `N` 未満なら、キュー待ちの測定になるのを避けるため測定失敗として扱い、要求数以下にするか `--concurrency` を外すよう案内する。engine が slot 数を報告しない場合、この比較による事前拒否は行われない（`terminal/strata_control/tune_session.py:445-450`）。
- 負荷を維持できないなど同時測定で有効な token 数を得られない場合、測定は `NO_TOKENS` となる（`terminal/strata_control/tune_session.py:386-409`、`terminal/strata_control/tune_session.py:451-456`）。
- `--plan` を除く実行では、engine/worker の起動と loopback HTTP リクエストが発生する。作業ディレクトリを指定しなければ `strata-tune-` の一時ディレクトリに設定・ログを作り、終了時に削除する。`--work-dir` 指定時はその作業領域を保持する（`terminal/strata_cli/tune_commands.py:371-376`）。
- 対象設定の `parallel` や engine 引数へ直接書き戻す処理はなく、測定は worker 用コピーで行う。結果保存時は preset、試行履歴、tune report の保存処理に進む。`--no-save` は preset 作成を抑止するが、試行履歴と report の保存呼び出しは残る（`terminal/strata_control/tune_session.py:484-495`、`terminal/strata_cli/tune_commands.py:392-418`）。

## 出力とエラー

- 無効な範囲の整数は human 出力では標準エラーに `strata: --concurrency is a number of requests from 2 to 8` を出して終了コード `2`、`--output json` では `ok: false` と error object を標準出力に出す（`terminal/strata_cli/tune_commands.py:109-114`、`terminal/strata_cli/tune_commands.py:332-335`）。
- engine が要求 slot 数を扱えない場合は測定失敗となり、最終結果を表示して終了コード `6` になる。通常の成功結果は `--output human` では人向け結果、`--output json` では JSON を標準出力に出す。中断時は終了コード `130`（`terminal/strata_control/tune_session.py:445-456`、`terminal/strata_cli/tune_commands.py:421-425`）。
- 進捗は human 出力時に標準エラーへ出る。指定した `--status-file` がある場合は各進捗を JSON として更新する（`terminal/strata_cli/tune_commands.py:358-369`）。

## 根拠

- parser 登録、整数型、既定値、help の意味: `terminal/strata_cli/tune_commands.py:21-36`
- CLI dispatch と対象ロード: `terminal/strata_cli/cli.py:514-515`、`terminal/strata_cli/cli.py:1702-1723`、`terminal/strata_cli/tune_commands.py:117-140`
- 値の範囲検証と tuner への受け渡し: `terminal/strata_cli/tune_commands.py:328-345`
- concurrency を各測定へ反映し、負荷計測で評価する処理: `terminal/strata_control/autotune.py:146-162`、`terminal/strata_control/autotune.py:386-395`、`terminal/strata_control/tune_session.py:386-409`、`terminal/strata_control/tune_session.py:430-456`
- slot 不足時の失敗、worker 設定と副作用: `terminal/strata_cli/tune_commands.py:371-376`、`terminal/strata_control/tune_session.py:445-450`、`terminal/strata_control/tune_session.py:536-564`
- preset 保存と同時起動時の適用条件: `terminal/strata_cli/tune_commands.py:392-418`、`terminal/strata_control/presets.py:470-519`
