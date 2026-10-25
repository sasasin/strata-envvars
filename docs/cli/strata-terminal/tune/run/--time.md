# `--time`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--time` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数 |

## 役割

`strata tune run` の候補設定 sweep に使う時間枠を指定します。既定値は 1800 秒（30 分）です。これはコマンド全体の厳密な実行タイムアウトではなく、候補を新たに開始するかを判定する時間枠です。

## 使い方

```sh
strata tune run --engine /path/to/strata --backend cuda --model example --time 900
```

この例では候補 sweep の時間枠を 900 秒にします。`--engine`、`--backend`、`--model` は `run` で必須です（`strata_cli/cli.py:414-424`）。

## 値と既定値

- parser は `type=float`、内部属性 `total_time`、既定値 `1800.0` として受け取ります（`strata_cli/cli.py:421-424`）。
- 数値に変換できない値は argparse の引数エラーになります。正数・有限値を要求する追加 validation はありません。変換可能な負数や `nan` / `inf` も拒否されず、計画へ渡ります（`strata_cli/cli.py:423-424`; `strata_control/tuning.py:723-728, 762-767`）。
- `--time` は候補数上限 `--trials`（既定 16）および候補あたりの反復数 `--repeats`（既定 3）と別の上限です（`strata_cli/cli.py:421-426`）。

## 実行時の動作

`_tune_run` は値を `plan_tuning(..., total_time_s=a.total_time)` に渡し、計画に保持します（`strata_cli/cli.py:1763-1768`; `strata_control/tuning.py:723-728, 762-767`）。tuner はまずベースラインを測定し、その完了後に候補探索用の時計を開始します。各候補を始める前に経過時間を値と比較し、超過していれば `time_limit` イベントを記録して新しい候補を開始しません（`strata_control/tuning.py:423-450`）。したがって、時間枠はベースライン測定には適用されません。

候補の測定中に枠を超えても、その測定は中断されません。枠を超えていないかは次候補の開始前にだけ確認します。また、ベースラインが成功し、ジョブがキャンセルされていない場合は最後の再測定も実施され、これも候補時間枠の外です（`strata_control/tuning.py:442-469`）。結果の表示は `at most ...s` として上限を示します（`strata_cli/cli.py:1788-1797`）。

ゼロまたは負数では、ベースライン後の最初の候補判定で時間枠超過となるため候補を開始しません。ただし、ベースラインと条件を満たす場合の最後の再測定は残ります。`nan` は大小比較が偽となるため時間判定で候補を止めず、候補数上限まで進みます。`inf` も有限時間で超過しません（`strata_control/tuning.py:447-450`）。一方、JSON 出力は `NaN` / `Infinity` を許可しないため、これらを渡したときは最終 JSON 化でエラーになります（`strata_cli/cli.py:535-542, 1805-1806, 2166-2173`）。

## 適用条件と副作用

この値は `strata tune run` のみを対象とします。同じ名前の `strata tune plan --time` は別 parser action で同じ秒単位・既定値を持ちますが、文書スコープは `run` です（`strata_cli/cli.py:398-407, 414-424`）。

時間枠だけでは全体の所要時間を制限できません。ベースラインや候補一件の測定が長引く場合、それぞれは測定側の制御に従います。たとえば `run` の parser では `--boot-timeout` と `--request-timeout` が別に設定でき、既定値はいずれも 600 秒です（`strata_cli/cli.py:443-446`）。時間枠到達時はそれまでの結果を保持して sweep を終え、正常なベースラインがあれば再確認へ進みます。

実行は tuning job を作り、job 状態・候補・計画・結果を state directory 以下の `job.json` 等に保存します。`--time` 自体が出力先を変えることはありません（`strata_control/tuning.py:317-335, 343-375`）。

## 出力とエラー

時間枠到達はジョブ内の `time_limit` イベントとして記録され、そこで CLI エラーにはなりません（`strata_control/tuning.py:447-450`）。人向け出力では実行件数と候補上限、job 状態、レポート参照コマンドを表示し、JSON 出力では job を返します（`strata_cli/cli.py:1805-1847`）。

数値に変換できない引数は argparse が usage とエラーを stderr に出して終了コード 2 とします（`strata_cli/cli.py:40-41, 2223-2231`）。engine が見つからない場合も `strata: no engine binary at ...` を stderr に出してコード 2 です（`strata_cli/cli.py:1759-1762, 527-532`）。測定中の例外は通常、候補の `TIMEOUT`、`FAIL_BOOT`、`UNMEASURED` 等として記録されます（`strata_control/tuning.py:486-523`）。

## 根拠

- parser と既定値: `strata_cli/cli.py:414-424`
- 値の受け渡し、計画・表示、前提エラー: `strata_cli/cli.py:1742-1803`
- 時間値の計画への格納、試行上限の扱い: `strata_control/tuning.py:723-768`
- ベースライン、候補開始判定、時間超過イベント、最後の再測定: `strata_control/tuning.py:423-484`
- job の永続化: `strata_control/tuning.py:317-375`
- 測定例外の候補状態化: `strata_control/tuning.py:486-523`
