# `strata models move --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--output` |
| 別名 | なし。`--json` は別のフラグで、JSON 出力への alias として登録される |
| 値 | `human`、`json`、`jsonl` |

## 役割

モデルファイルの移動コマンドが標準出力へ出す形式を選びます。`--output` は出力先ファイルを指定するものではありません。移動先フォルダーは位置引数 `NEW_FOLDER` で渡します（parser: `strata_cli/cli.py:162-171`、処理: `strata_cli/cli.py:623-634`）。

## 使い方

```sh
strata models move --plan --output json /path/to/new-model-folder
strata models move --output jsonl /path/to/new-model-folder
strata models move --status --output json
```

最初の例は移動計画を JSON で表示し、2番目は移動中の進捗を JSON Lines で出力します。例のパスは移動先フォルダーを表します。

## 値と既定値

- 省略時は `human` です。
- `human` は人向けのテキスト出力です。
- `json` は機械処理向けの JSON を選びます。
- `jsonl` は機械処理向けの JSON Lines を選びます。通常の移動では進捗イベントが1行ずつ出ます。
- parser は上記3値だけを受理します。別の値は `argparse` の引数エラーとなり、usage とエラーを stderr に出して終了コード `2` で終了します（`strata_cli/cli.py:171`）。
- `--json` は one-shot parser 群に追加される独立フラグです。`strata models move --json` は `--output json` と同じ設定になります。`--output jsonl --json` の組合せは main の one-shot/streaming 判定で拒否されます（`strata_cli/cli.py:508-515, 2232-2235`）。

## 実行時の動作

出力形式は移動処理の選択やファイル操作を変えず、結果の表示方法を切り替えます。`human` では進捗を同じ行に表示し、完了または停止のメッセージを出します。`json` は進捗を表示せず、最後に schema version 付きの結果オブジェクトを出します。`jsonl` は進捗イベントを1行ずつ flush し、最後に `event: result` の JSON オブジェクトを出します（`strata_cli/cli.py:642-660`）。

`--plan` と `--status` は `--output jsonl` を指定しても進捗ストリームを作らず、単一の JSON オブジェクトを出力します。`--leave` も結果またはエラーを単一の JSON オブジェクトで出力します。`--resume` は中断された移動先・元フォルダーを復元して通常の移動処理へ進むため、`jsonl` では通常移動と同様に進捗イベントを出します（`strata_cli/cli.py:627-634, 668-705`）。

`--quiet` を併用しても、`json` / `jsonl` の機械可読出力は抑止されません。main は出力形式が機械形式なら quiet 用の stdout 捕捉を行わず実行します（`strata_cli/cli.py:2236-2248`）。

## 適用条件と副作用

通常の移動は `--output` の値にかかわらず `models_move.move` を呼びます。移動先が別ドライブなら `.part` へコピーし、サイズと SHA-256 を検証してから確定名へ変更し、その後に元ファイルを削除します。同じドライブなら rename を使います。中断・失敗時の状態記録もこの処理に属し、`--output` はこれらを無効化しません（`strata_control/models_move.py:223-258, 379-417, 441-531`）。

`--plan` は移動計画を表示しますが、内部の `plan()` は移動先を作成して書き込みテスト用一時ファイルを作成・削除します。そのため文面上の「change nothing」とは異なり、移動ファイル自体は動かさないものの、移動先フォルダーが未作成なら作成される場合があります（`strata_cli/cli.py:627-634`、`strata_control/models_move.py:123-132, 137-169`）。

移動先が元フォルダーと同じ、互いに内包する、見つからない、書き込みできない場合など、計画時の問題は plan 結果の `ok: false` として表現され、終了コード `5` になります。異なる出力形式では人向け文面または JSON になります（`strata_control/models_move.py:137-184`、`strata_cli/cli.py:627-634`）。

## 出力とエラー

- 通常移動の成功は `human` と `json` で終了コード `0`、安全に停止した未完了移動は終了コード `6` です。機械形式では結果オブジェクトの `done` / `stopped` 等を確認できます（`strata_cli/cli.py:656-660`）。
- `MoveError` は終了コード `5` です。機械形式では `ok: false`、エラーコード・メッセージ・詳細と、利用可能な移動概要を JSON で stdout に出します。人向け形式では stderr にエラーを出します（`strata_cli/cli.py:649-655`）。
- `--status` は中断状態の有無にかかわらず終了コード `0` です。`--resume` / `--leave` に中断状態がない場合は終了コード `5` です（`strata_cli/cli.py:673-684`）。
- 移動先 `NEW_FOLDER` を省略した通常実行では、JSON 指定時も不足メッセージを stderr に出して終了コード `2` で終了します（`strata_cli/cli.py:623-625`）。
- JSON Lines の詳細なイベント schema や全ての例外型別出力は、この調査では網羅していません。確認した範囲では、移動中の progress イベントと終了時の result/error オブジェクトが stdout に出ます。

## 根拠

- parser と許可値・既定値: `strata_cli/cli.py:162-171`
- 共通 `--json` 登録と one-shot 設定: `strata_cli/cli.py:508-515, 2223-2237`
- plan・進捗・完了・失敗の出力と終了コード: `strata_cli/cli.py:617-660`
- status / resume / leave の出力: `strata_cli/cli.py:668-705`
- move plan のパス検証・書き込み検査: `strata_control/models_move.py:123-184`
- ファイル移動、検証、状態保存と停止・失敗処理: `strata_control/models_move.py:223-258, 379-531`
