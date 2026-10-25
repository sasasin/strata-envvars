# `--cancel-file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--cancel-file PATH` |
| 別名 | なし |
| 値 | 停止通知に使うファイルパス。必須の文字列引数で、既定値は未指定（`None`）。 |

## 役割

モデルファイルの移動中に指定パスが存在することを検知すると、安全停止を要求します。モデルの移動処理は同一ボリュームなら rename、別ボリュームなら検証付き copy を行い、既に完了したファイルの移動を保ったまま止まります（`strata_cli/cli.py:162-171, 640-648`; `strata_control/models_move.py:5-12, 512-521`）。

## 使い方

```sh
strata models move /mnt/storage/Strata --cancel-file /tmp/stop-model-move
```

別プロセス等で `/tmp/stop-model-move` を作成すると停止条件になります。ファイルの内容は読まれず、Strata がこの通知ファイルを作成・削除する処理もありません（`strata_cli/cli.py:640-648`）。

## 値と既定値

- `argparse` の `--cancel-file` は `PATH` という metavar の値を1つ取ります。型変換・存在確認などの parser validation はなく、省略時は `None` です（`strata_cli/cli.py:170`）。
- 実行時には値を `Path` に変換し、その `exists()` をキャンセル判定に使います。相対パスは実行時のカレントディレクトリを基準に解決されます。存在する通常ファイルやディレクトリは、内容に関係なく停止条件になります。未指定ならキャンセル判定は常に偽です（`strata_cli/cli.py:640-648`）。
- 値を複数回指定した場合の parser 動作は `argparse` の通常の単一値引数です。Strata 独自の重複値処理はありません（`strata_cli/cli.py:170`）。

## 実行時の動作

`strata models move NEW_FOLDER` の通常移動でのみ、`Path(cancel_file).exists()` が `models_move.move` の `cancelled` callback として渡されます（`strata_cli/cli.py:623-648`）。移動処理は計画検査・書き込み可能性確認の後、各ファイルの前に callback を確認し、別ボリュームのコピー時はコピーと検証のチャンク処理中にも確認します（`strata_control/models_move.py:379-400, 441-445`; `strata_control/models_move.py:194-205, 223-258`）。同一ボリュームの rename 自体の最中には callback を再確認しません（`strata_control/models_move.py:441-459`）。

`--resume` は保存された移動元・先を復元して通常の `_models_move` に戻るため、同時に渡した `--cancel-file` も再開処理に適用されます。`--status` は状態を表示するだけで、`--leave` は中断移動の後始末を行う分岐であり、いずれもこの callback を使いません（`strata_cli/cli.py:621-622, 668-705`）。`--plan` も `move` を呼ばず計画を出して戻るため、キャンセルファイルは参照されません（`strata_cli/cli.py:627-634`）。

停止時、実行中コピーの `.part` は破棄され、完了済みファイルは移動先に残ります。設定ファイル中の移動済みモデル参照は更新されます。実際にファイルが1件以上移動済みなら中断状態を記録して `--resume` / `--leave` に備え、まだ何も移動していなければ状態記録を消します（`strata_control/models_move.py:223-258, 434-439, 512-521`）。

## 適用条件と副作用

このオプションはキャンセル通知先を指定するだけで、通知ファイルの作成監視プロセスやポーリング間隔を別途設定しません。callback の確認箇所に到達した時点で存在を判定します（`strata_cli/cli.py:640-648`; `strata_control/models_move.py:441-445, 194-205, 229-238`）。

停止要求より前に `move` は移動先の計画・書込検査を行います。移動先が未作成なら検査過程でディレクトリが作られ、書込検査用一時ファイルも作成・削除され得ます（`strata_control/models_move.py:123-133, 137-169, 379-400`）。通知ファイル自体は読み取りのみです。

また、移動先にある過去の `.part` ファイルは、最初のキャンセル確認より前に削除対象として走査されます（`strata_control/models_move.py:395-400, 441-445`）。

## 出力とエラー

停止が成立すると、通常出力は `Moving stopped. Nothing was lost.` で終了コード `6` です。`--output json` など機械出力では `ok: true` と `event: "result"` を含む結果に `done: false` / `stopped: true` が含まれます。`--output jsonl` は各進捗イベントに続けて結果イベントを出します。キャンセルファイルが最初から存在する場合は、最初のファイル処理前に停止するため進捗イベントなしで結果だけが出ることがあります（`strata_cli/cli.py:642-660`; `strata_control/models_move.py:423-432, 441-445, 512-521`）。

移動先の不正、空き容量不足、コピー検証失敗、I/O 失敗など、停止判定より先に発生した `MoveError` は標準エラー（人間向け）または `ok: false` の JSON（機械向け）で報告され、終了コード `5` です（`strata_cli/cli.py:647-655`; `strata_control/models_move.py:137-184, 241-255, 388-400, 522-531`）。引数不足など parser 後のコマンド使用エラーは標準エラーで案内され、終了コード `2` です（`strata_cli/cli.py:623-625`）。

## 根拠

- `strata_cli/cli.py:162-171` — `models move` の parser 定義。`--cancel-file PATH` は任意の値を取る。
- `strata_cli/cli.py:617-660` — 通常実行、PATH の変換、キャンセル callback、出力と終了コード。
- `strata_cli/cli.py:668-705` — `--status` / `--resume` / `--leave` の分岐。再開は通常実行に戻る。
- `strata_control/models_move.py:123-184, 379-400` — 移動計画・書込検査・移動前の確認。
- `strata_control/models_move.py:194-258, 441-531` — コピー中の確認、安全停止、完了・失敗時の処理。

調査範囲は上記 checkout のソースです。同一 revision の CLI `--help` および Release 配布物は照合していません。
