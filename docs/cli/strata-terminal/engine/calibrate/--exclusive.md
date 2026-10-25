# `--exclusive`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--exclusive` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False`、指定時は `True`。 |

## 役割

計測・設定適用・ロールバックを実行する前に、対象デバイスを使う他のモデル実行を停止済みだと呼び出し側が表明するための確認フラグです。実行時には Strata 管理下の runtime と競合しないようローカル lease を取り、managed instance を検査します。ただし、このフラグ自体が任意の GPU 利用プロセスを検出・停止するわけではありません。

## 使い方

```sh
strata engine calibrate --profile four-gpu --measure --exclusive --out /path/to/new-report.json
strata engine calibrate --profile four-gpu --apply-result /path/to/report.json --exclusive
strata engine calibrate --profile four-gpu --rollback-result /path/to/report.json --exclusive
```

`--measure` では `--out` も必要です。計測結果の確認は `--review-result`、適用前の確認は `--review-rollback` で行います。これらの確認操作や `--plan` には `--exclusive` を付けません。

## 値と既定値

値を取らない `store_true` フラグで、別名はありません。省略時は偽です。`strata engine calibrate` は `--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のいずれか一つを必須として選ぶ parser なので、`--exclusive` はこれらのアクション選択とは独立です。

## 実行時の動作

- `--measure` は `--exclusive` と `--out REPORT.json` の両方を要求します。計測時の report は新規作成され、既存ファイルやシンボリックリンクがあるパスは拒否されます。計測は decode sweep を実行して report を保存しますが、run config は変更しません。
- `--apply-result` と `--rollback-result` は `--exclusive` がなければ実行前にエラーになります。`--apply-result` は候補設定の smoke generation 後に設定を適用し、元の run config と setup settings の rollback evidence を保存します。`--rollback-result` は適用前の設定を smoke generation してから復元します。
- `--plan`、`--review-result`、`--review-rollback` に `--exclusive` を足すと、アクションとの不整合として終了コード 2 になります。`--out` も `--measure` 以外との併用は拒否されます。
- 有効な実行では calibration が profile/config 用ロックと managed runtime の排他 activity lease を取り、未停止・状態不明を含む Strata managed instance があれば拒否します。対象 run config の host/port（profile override があればその endpoint も）のポートが応答中の場合も停止を求めます。これは利用者の確認を受け取るだけでなく、Strata 自身の managed runtime との同時実行を防ぐ処理です。

## 適用条件と副作用

`--exclusive` は `--measure`、`--apply-result`、`--rollback-result` 専用です。値の指定や環境変数による上書きはありません。

このフラグは他プロセスを停止せず、OS 全体の GPU 所有権を証明しません。Strata の端末向けガイドは、直接起動された legacy server や無関係な GPU プロセスは lease の対象外であり、Windows 側の制御にも未対応範囲があると明記しています。実行前に対象デバイスが他用途で使われていないことを運用者が確認してください。計測は数分ではなく概ね 15〜30 分の decode sweep です。

## 出力とエラー

- 不正な組み合わせ、`--measure` での `--exclusive` または `--out` の不足、適用・ロールバック時のフラグ不足は stderr に `strata: ...` を出し、終了コード 2 を返します（`--output json` では JSON error object）。
- managed runtime lease が競合中、managed instance が残る、設定ポートが稼働中、report/config が stale、または smoke/計測が失敗した場合は `ProfileError` 等のエラー経路になります。エラーは通常 stderr（JSON 出力時は JSON）に示され、コードで指定された終了コードが返ります。たとえば lease/instance/port 競合は 6、report 出力先が既に存在する場合は 2、計測キャンセルは 130 です。
- 計測成功時は report の絶対パスと結果を出力します。成功した計測は report を新規作成しますが、run config を適用するのは別操作の `--apply-result` です。

## 根拠

- Parser とスコープ: `strata_cli/cli.py:174-189`（calibrate parser、action の相互排他、`--exclusive` の型・既定値）。
- Dispatch と条件検査: `strata_cli/cli.py:1059-1113`（measure/apply/rollback 要件、review/plan での不許可、出力処理）、`strata_cli/cli.py:527-542`（human/JSON error と success 出力）、`strata_cli/cli.py:2166-2188`（エラー終了コードの返却）。
- 計測と排他判定: `strata_control/calibration.py:205-229`（ポート確認・managed runtime lease・稼働 instance 拒否）、`strata_control/calibration.py:270-313`（acknowledgement、lock と計測）、`strata_control/calibration.py:289-296`（既存 report と親ディレクトリの検査）、`strata_control/calibration.py:322-335`（計測 report の生成・保存）。
- lease と managed instance の状態確認: `strata_control/runtime.py:173-203`。
- 適用・復元時の確認と副作用: `strata_control/calibration.py:526-545`（apply 時の acknowledgement、lease、preflight）、`strata_control/calibration.py:553-626`（smoke、rollback evidence、config/settings 書き込み）、`strata_control/calibration.py:684-720`（rollback 時の acknowledgement、lease、preflight・smoke）。
- 利用者向け補足: `docs/TERMINAL.md:160`（lease の対象と legacy/Windows 制約）、`docs/TERMINAL_QUICKSTART.md:73-87`（利用手順例）。
