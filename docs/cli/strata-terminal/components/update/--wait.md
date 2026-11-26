# `--wait`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数（`float`） |

## 役割

更新対象のエンジンが稼働中の場合に、停止するまで指定秒数だけ待ってから更新を続けます。指定時間内に停止しなければ更新を拒否します。このオプション自体はエンジンを停止しません。

## 使い方

```sh
# エンジンが停止するまで最大300秒待ち、停止後に更新する
strata components update --wait 300
```

このコマンドはフィードを読み、更新があればコンポーネントをダウンロードして更新します。

## 値と既定値

`SECONDS` は `float` として解析されます。省略時は `None` で、実行時に `0.0` として扱われます。parser に最小値・最大値の指定や追加の範囲検証はありません。省略時または `0` では期限付きの待機をせず、稼働中なら後述の `ModelGate` による確認へ進みます。負数は拒否されませんが、待機処理に入り、稼働中なら直ちに busy として失敗します。正の値でも指定時間内に停止しなければ同じ失敗になります。（`terminal/strata_cli/update_cmd.py:47-56, 323-325`、`terminal/strata_control/updater.py:383-394, 2082-2097`）

## 実行時の動作

更新処理はフィードを取得して更新状態を保存した後、エンジンまたは Control に変更がある場合に、コンポーネントのダウンロードや切り替えに進む前に稼働状態を確認します。変更があり `--wait` が正の値なら、稼働中のエンジンがなくなるまで最大その秒数を待ちます。状態は3秒間隔で再確認され、待機中は `waiting` イベントを出します。停止を確認できれば更新を続行し、期限まで稼働中なら `Busy` を返します。（`terminal/strata_control/updater.py:451-470, 383-394, 2082-2097, 2109-2123`）

変更がない場合は待機しません。`--check` は確認処理だけを実行して終了するため、このオプションによる待機は行いません。（`terminal/strata_control/updater.py:2066-2079, 2082-2089`、`terminal/strata_cli/update_cmd.py:361-377`）

## 適用条件と副作用

`--wait` は稼働中のエンジンを停止せず、指定時間を超えても稼働状態が続く場合は更新を進めません。これは対話時の `ModelGate` による停止確認とは別の経路です。待機時間内に停止できなかった場合、利用者はエンジンを停止してコマンドを再実行する必要があります。（`terminal/strata_control/updater.py:2082-2097`、`terminal/strata_control/engine_update.py:285-323`）

待機確認より前に更新フィードを取得し、コンポーネントの `.updates/state.json` にフィード情報を保存します。そのため、待機が時間切れになって更新を拒否した場合も、フィード取得と更新状態の保存は発生しています。（`terminal/strata_control/updater.py:227-233, 255-265, 451-470, 2109-2118`）

待機確認の対象はエンジンまたは Control の更新です。`--app --no-engine --no-control` のようにアプリ installer だけを更新する場合、変更判定にアプリは含まれないため、`--wait` による待機は行われません。（`terminal/strata_control/updater.py:2066-2079, 2082-2097, 2119-2122`）

`--wait` を指定せず、変更対象がありエンジンが稼働中の場合は `ModelGate` が処理します。対話できる端末では停止確認を行い、`--yes` などで質問できない実行では、`--stop-model` の指定がなければ busy として拒否します。（`terminal/strata_cli/update_cmd.py:404-421`、`terminal/strata_control/engine_update.py:300-323`）

## 出力とエラー

待機中は人向け出力で「更新前にエンジンの停止を待っている」旨を表示します。`--output jsonl` では待機イベントを出力し、`--output json` では途中イベントを表示しません。（`terminal/strata_cli/update_cmd.py:117-139`）

時間切れなどで稼働中のエンジンが残ると `Busy` となり、通常のエラー出力は標準エラーに表示され、終了コードは `7` です。JSON 出力では `ok: false` とエラー内容を含む JSON を返します。（`terminal/strata_control/updater.py:61-83, 383-394`、`terminal/strata_cli/update_cmd.py:307-316, 378-388`）

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56, 59-79` — 共通 parser の `--wait` 定義と `strata components update` への登録。
- `terminal/strata_cli/update_cmd.py:307-325, 355-377` — 値を `Context.wait` に渡す処理と、`--check` で通常更新処理を迂回する分岐。
- `terminal/strata_control/updater.py:383-403, 2082-2097, 2109-2123` — 待機・期限切れ・更新前の稼働確認と更新順序。
- `terminal/strata_control/engine_update.py:285-323` — `--wait` による待機とは別に行うモデル停止への同意処理。
- `terminal/strata_cli/update_cmd.py:117-139, 378-388`、`terminal/strata_control/updater.py:61-83` — 待機イベント、失敗出力、busy の終了コード。
