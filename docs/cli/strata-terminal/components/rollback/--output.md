# `strata components rollback --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

rollback の結果や失敗を、人向けテキストか機械処理向け JSON で出力します。エンジンの切り替え処理自体は出力形式によって変わりません。`jsonl` は rollback 中に待機が発生した場合の待機イベントも1行の JSON として出し、完了時には結果オブジェクトを出します（`terminal/strata_cli/update_cmd.py:117-139,326-340`）。

## 使い方

```sh
# 人向けの結果表示（既定値）
strata components rollback

# 結果を JSON で受け取る
strata components rollback --output json

# 待機イベントと最終結果を JSON Lines として受け取る
strata components rollback --wait 30 --output jsonl
```

## 値と既定値

`--output` は `human`、`json`、`jsonl` のいずれかを受け取り、省略時は `human` です。値なし、またはこの3種類以外の値は `argparse` の引数エラーになります。別名や短縮形はありません（`terminal/strata_cli/update_cmd.py:47-57,80-82`）。

## 実行時の動作

- `human` では切り替え結果と、保存済み tuning preset の扱い、および次の操作案内を通常の文章で標準出力へ表示します（`terminal/strata_cli/update_cmd.py:332-339`）。
- `json` では成功時に `schema_version: 1`、`ok: true` と rollback 結果を含む JSON オブジェクトを標準出力へ出します。エラー時は `schema_version: 1`、`ok: false`、エラーコードとメッセージを含む JSON オブジェクトになります（`terminal/strata_cli/update_cmd.py:309-316,326-332,378-388`）。
- `jsonl` も成功・失敗の結果オブジェクトを1行の JSON として出します。エンジンが稼働中で `--wait` による待機が始まった場合、待機イベントも先に JSON 行で出力されます。待機がない rollback は、出力形式が JSON Lines でも結果行だけです（`terminal/strata_cli/update_cmd.py:117-139,326-332`、`terminal/strata_control/updater.py:383-394`）。

この option は `update_cmd` が登録する `strata components rollback` parser の共通引数です。CLI は同コマンドを `update_cmd.run()` へ渡し、rollback 分岐では `.updates` の状態に記録された前回のエンジンへ戻ります。`--feed` は使わず、rollback はダウンロードしません。`--backend` は検出対象のハードウェア指定に使われます。`--wait` は稼働中エンジンへの待機条件を変えます。`--force` と `--model-config` は rollback 分岐では参照されません（`terminal/strata_cli/cli.py:2210-2212`、`terminal/strata_cli/update_cmd.py:47-57,307-340`、`terminal/strata_control/updater.py:1776-1798`）。

## 適用条件と副作用

出力形式は rollback の可否や対象バージョンを変更しません。rollback はコンポーネントフォルダーの更新ロックを取得し、記録済みの前バージョンを読み込みます。対象パッケージの manifest と全ファイルを検証してから、エンジンの pin、active/previous/skipped 状態、履歴を更新し、状態ファイルへ保存します。エンジンの内容をダウンロード・削除する処理ではありません（`terminal/strata_control/updater.py:1776-1798,1723-1773`、状態保存: 同 `:227-265`）。

保存済み tuning preset は削除されません。エンジンの識別情報が変わった場合は短い再確認が必要な印を記録し、同一識別情報への復帰など印が不要な場合は新たに付けません（`terminal/strata_control/updater.py:1768-1773`、`terminal/strata_control/preset_marks.py:72-96`）。

エンジンが稼働中なら `--wait` の秒数だけ停止を待てます。対話端末で待機時間を指定せずに実行した場合は、待つかを質問し、肯定時は最大6時間待ちます。機械出力または入力が端末でない場合は質問せず、稼働が続いていれば終了コード `7` で拒否します（`terminal/strata_cli/update_cmd.py:504-520`、`terminal/strata_control/updater.py:383-394`）。

## 出力とエラー

- 前バージョンの記録がない、またはすでにそのバージョンを使っている場合は終了コード `2` です。
- 前バージョンの manifest / ファイル検証に失敗した場合、またはそのエンジンが現在の PC で使えなくなっていた場合は終了コード `5` です。
- エンジンが稼働中で待機できない場合は終了コード `7` です。これらの `UpdateError` は `human` では `strata: ...` を標準エラーへ、`json` / `jsonl` ではエラー JSON を標準出力へ出します（`terminal/strata_control/updater.py:1776-1798,72-82`、`terminal/strata_cli/update_cmd.py:311-316,378-388`）。
- `update_lock` は `.updates` ディレクトリと `update.lock` を開いて排他します。同じコンポーネント領域で別の updater が動作中なら終了コード `7` です。状態保存中などに起きた `OSError` も CLI の共通エラー処理へ渡り、機械出力時には JSON エラーになります（`terminal/strata_control/updater.py:195-224,255-265`、`terminal/strata_cli/cli.py:2258-2265`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-57,80-82` — 共通 parser の `--output` 定義と rollback parser への登録。
- `terminal/strata_cli/cli.py:2210-2212`、`terminal/strata_cli/update_cmd.py:307-340` — dispatch、rollback の出力分岐と成功時の形式。
- `terminal/strata_cli/update_cmd.py:117-139,504-520` — JSONL イベント、待機時の質問と非対話動作。
- `terminal/strata_control/updater.py:383-394,1776-1798,1723-1773` — 稼働中チェック、前バージョン検証と切り替え状態の更新。
- `terminal/strata_control/updater.py:195-265`、`terminal/strata_control/preset_marks.py:72-96` — 排他ロック、状態ファイル保存、preset 再確認印。
