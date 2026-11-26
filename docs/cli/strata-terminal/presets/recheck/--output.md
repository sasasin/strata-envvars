# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

再チェック結果の表示形式を選びます。`human` は人が読む進捗・結果、`json` は機械処理向けの JSON を出します。この指定は再チェックの測定方法や判定を切り替えません。コマンドは保存済み preset の設定でエンジンを起動して性能を測り、完了結果を preset に記録します。

## 使い方

```sh
# JSON を標準出力へ出す（<preset> と <profile-or-config> は実際の ID / profile 名 / run-config JSON パスに置き換える）
strata presets recheck <preset> <profile-or-config> --output json
```

省略時は `human` です。同じコマンドで明示する場合は `--output human` を指定します。

## 値と既定値

- parser は `human` と `json` だけを受理し、省略時は `human` を設定します。`--output` に短縮別名はありません（`terminal/strata_cli/tune_commands.py:59-61,88-97`）。
- `--output` を値なしで指定する、または別の値を渡す形式は parser の選択肢に合いません。parser が引数を拒否する場合、`presets_command` や再チェック処理には進みません。

## 実行時の動作

- `presets_command` は `a.output == "json"` を機械出力モードとして `_recheck` に渡します（`terminal/strata_cli/tune_commands.py:472-476,525-526`）。
- 既定の `human` では測定中の進捗を標準エラーへ逐次表示し、完了時に判定を標準出力へ表示します。`json` では進捗表示を抑え、完了時に `schema_version: 1` と `ok: true` を含む JSON を標準出力へ出します。再チェック結果には `verdict`、`reason`、測定等の `result`、更新後の `preset` が含まれます（`terminal/strata_cli/tune_commands.py:101-106,639-661`）。
- `json` は `--status-file` の進捗出力を無効にしません。status file が指定されていれば処理中と完了時の状態を JSON ファイルへ書きます。この書き込みは `--output` にかかわらず行われます（`terminal/strata_cli/tune_commands.py:647-657`）。
- `--output` は測定や保存を省略しません。再チェック完了時には結果を `presets.record_recheck` で保存し、`keep` の場合は成功日時なども更新します（`terminal/strata_cli/tune_commands.py:652-661`、`terminal/strata_control/presets.py:441-458`）。

## 適用条件と副作用

表示形式は `strata presets recheck` に適用されます。実行時には保存済み preset と対象 profile / run configuration を読み、エンジンを起動して測定します。既定では一時 work directory を使い、終了時に削除します。`--work-dir` を指定するとそのディレクトリを保持します。これらの実行上の副作用は `--output` の値で変わりません（`terminal/strata_cli/tune_commands.py:615-644`）。

## 出力とエラー

- 人向け出力では進捗が標準エラー、最終結果が標準出力です。JSON モードでは進捗を出さず、最終 JSON を標準出力へ出します（`terminal/strata_cli/tune_commands.py:639-661`）。
- JSON モードの処理エラーは `schema_version: 1`、`ok: false`、`error`（終了コードとメッセージ）の JSON になります。人向けモードでは `strata: ...` を標準エラーへ出します（`terminal/strata_cli/tune_commands.py:109-114`）。
- PC の状態が再チェックに適さない場合や preset と対象の選択条件が一致しない場合、再チェックを開始せず終了コード `5` で失敗します（`terminal/strata_cli/tune_commands.py:618-631`）。preset の例外も終了コード `5`、`OSError` / `ValueError` は例外側に `exit_code` がなければ `2` で処理されます（`terminal/strata_cli/tune_commands.py:527-530`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61,88-97` — `presets recheck` parser、値の選択肢・既定値、および同コマンドに属する追加引数。
- `terminal/strata_cli/tune_commands.py:101-114,472-476,525-531` — human / JSON 出力の切り替え、成功・失敗 payload、例外と終了コード。
- `terminal/strata_cli/tune_commands.py:615-661` — 再チェックの前提検査、進捗表示、status file、測定、結果保存、最終出力。
- `terminal/strata_control/autotune.py:937-1012` — 再チェックが測定を行い `keep` / `retune` / `inconclusive` を返す処理。
- `terminal/strata_control/presets.py:441-458` — 再チェック結果を preset に永続化する処理。
- `docs/cli/README.md:825-834` — 索引上のコマンド階層と `--output` のリンク位置。parser のスコープと一致。
