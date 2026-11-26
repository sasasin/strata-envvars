# `--status-file`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--status-file` |
| 別名 | なし |
| 値 | JSON 進捗ファイルのパス（文字列） |

## 役割

保存済み preset の再チェック中に進捗を JSON ファイルへ書き出します。主に Desktop app が実行状況を読むための出力です。再チェックの判定条件や preset の選択は変えません。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config.json> --status-file /tmp/recheck-progress.json
```

`<preset>` は保存済み preset、対象は profile 名または実行設定 JSON として説明されています。実装の target 解決処理はインストール済みモデル名も受け付けます（`terminal/strata_cli/tune_commands.py:88-96,117-140`）。

## 値と既定値

値はパス文字列で、既定値は `None`（未指定）です。`type`、存在確認、拡張子検査、親ディレクトリ作成などの parser 側 validation はありません。複数回指定した場合の独自処理もありません（`argparse` の通常の引数処理に委ねられます）。

## 実行時の動作

`strata presets recheck` parser が値を受け取り、`_recheck` が `autotune.recheck` に進捗 callback を渡します（`terminal/strata_cli/tune_commands.py:88-96,615-653`）。再チェックは測定段階ごとに `stage`、`message`、`elapsed_s` などを status JSON に書き、処理完了後は `state: "done"` と結果を書きます（`terminal/strata_control/autotune.py:959-968,1011-1012`、`terminal/strata_cli/tune_commands.py:647-657`）。

status ファイルは `path + ".tmp"` に UTF-8 JSON として書いた後、置換して更新されます。親ディレクトリは作成しません。指定先に既存ファイルがあれば置換されます（`terminal/strata_cli/tune_commands.py:240-248`）。

`--status-file` はコマンドの最終出力形式を選びません。最終結果の人間向け表示または JSON 出力は別の `--output` が選びます（`terminal/strata_cli/tune_commands.py:59-61,475-476,658-662`）。

再チェック結果は `presets.record_recheck` に記録されます。`keep` の場合は最終成功時刻を更新し、同一性情報や測定値も条件に応じて更新します。この記録処理は `--status-file` の有無にかかわらず行われます（`terminal/strata_cli/tune_commands.py:652-657`、`terminal/strata_control/presets.py:441-458`）。

## 適用条件と副作用

再チェックが進捗 callback を呼ぶまで status ファイルは作成・更新されません。preset が見つからない、PC 状態が再チェック不可なほど変化した、preset と指定 target の選択条件が合わないなど、callback より前に失敗した場合は進捗ファイルがないことがあります（`terminal/strata_cli/tune_commands.py:618-631,647-653`）。

status ファイルの書き込みまたは置換で `OSError` が起きても無視され、再チェック自体はそのエラーだけでは中断しません（`terminal/strata_cli/tune_commands.py:240-248`）。一方、通常の再チェックではエンジンを起動して測定します。エンジン起動失敗は再チェック結果の `retune` 判定になり得ます（`terminal/strata_control/autotune.py:959-975`）。

## 出力とエラー

再チェックが完了すると status JSON の `state` は `done` になり、`result` に再チェック結果が入ります。その後、通常のコマンド出力にも verdict と preset 情報が表示されます（`terminal/strata_cli/tune_commands.py:654-662`）。status ファイルへの書き込み失敗自体は警告やエラーとして報告されません。

PC の変化が大きすぎる場合と保存時の選択条件が一致しない場合は、status 更新なしでエラーコード `5` を返します（`terminal/strata_cli/tune_commands.py:622-631`）。それ以外の `PresetError` はコード `5`、`OSError` / `ValueError` は例外に `exit_code` があればその値、なければ `2` で処理されます（`terminal/strata_cli/tune_commands.py:527-530`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:88-96` — `presets recheck` parser と `--status-file` の既定値。
- `terminal/strata_cli/tune_commands.py:240-248` — JSON の一時ファイル書き込み、置換、`OSError` の無視。
- `terminal/strata_cli/tune_commands.py:615-662` — 再チェック前の拒否条件、進捗・完了時の書き込み、preset 記録、出力。
- `terminal/strata_control/autotune.py:937-1012` — 再チェック中の進捗通知、測定と判定、終了結果。
- `terminal/strata_control/presets.py:441-458` — 再チェック結果の preset への記録と `keep` 時の更新。
