# `strata update --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

更新確認・更新処理の表示形式を選びます。`human` は人向けの進捗や結果、`json` は進捗イベントを出さず処理結果を JSON で出力し、`jsonl` は更新中のイベントを 1 行ずつ JSON Lines 形式で出力した後、最終結果も JSON で出力します。

## 使い方

```sh
# 更新内容だけを確認し、機械可読な JSON を受け取る
strata update --check --output json

# 更新を実行し、イベントと最終結果を JSON Lines で受け取る
strata update --yes --output jsonl
```

## 値と既定値

値は `human`、`json`、`jsonl` の固定選択肢で、省略時は `human` です。別名や値の大文字小文字変換は定義されていません。別の値や値なしは argparse の引数エラーとなり、更新処理には進みません（`terminal/strata_cli/update_cmd.py:47-57`）。

## 実行時の動作

- `human` では更新開始表示、更新中の進捗・段階表示、完了結果を人向けに表示します。ダウンロード進捗は TTY なら同じ行を更新し、TTY 以外では概ね 10% 刻みと完了時に表示します（`terminal/strata_cli/update_cmd.py:117-139, 368-377`）。
- `json` は進捗イベントを抑止し、処理後に `schema_version: 1` と `ok` を含む結果オブジェクトを標準出力へ出します。`--check` の場合は確認レポートを同様に出力します（`terminal/strata_cli/update_cmd.py:117-126, 361-377`）。
- `jsonl` は進捗・段階・モデル状態のイベントごとに、`schema_version: 1` を付けた JSON を 1 行出力して flush します。通常処理の最後には `ok` を含む結果オブジェクトも出力します（`terminal/strata_cli/update_cmd.py:121-139, 371-377`; `terminal/strata_control/updater.py:391, 435, 586`; `terminal/strata_control/engine_update.py:309, 347, 355, 388, 390, 398`）。
- `--check` は機械出力モード（`json` または `jsonl`）でもイベント列ではなく、確認レポート 1 個を出します（`terminal/strata_cli/update_cmd.py:361-367`）。
- 機械出力モードでは、実行中モデルを止めるかの対話確認を行わず、確認用コールバックも出力しません。`--yes` と同様に質問を省く動作ですが、`--output` 自体がモデル停止を許可するわけではありません。モデルを停止して更新するには別途 `--stop-model` が必要です（`terminal/strata_cli/update_cmd.py:404-421`）。
- `strata update` parser には `--json` alias はありません。CLI の `--json` 一括処理は `update` を対象外としているため、このコマンドでは `--output` を指定します（`terminal/strata_cli/update_cmd.py:60-69`; `terminal/strata_cli/cli.py:2335-2338`）。

## 適用条件と副作用

出力形式の選択は更新対象や更新可否を変えません。通常の `strata update` は署名済み feed を読み、必要に応じてネットワーク取得・検証・エンジン切替を行います。`--output` はファイルを指定せず、標準出力への表示方法を変えます（`terminal/strata_cli/update_cmd.py:355-377`）。

機械出力モードではプロンプトが無効になるため、TTY で実行した場合も対話的なモデル停止確認には進みません。エラーは `json` / `jsonl` では `schema_version`、`ok: false`、`error` を含む JSON を標準出力へ出し、人向けモードでは `strata: ...` を標準エラーへ出します。返される終了コードは失敗の種類に応じます（`terminal/strata_cli/update_cmd.py:307-316, 378-390`）。

## 出力とエラー

選択肢外の値は argparse が拒否し、usage とエラーを表示して終了コード 2 となります（parser 登録: `terminal/strata_cli/update_cmd.py:56`; CLI の引数解析: `terminal/strata_cli/cli.py:2325-2334`）。処理中の feed・署名・取得拒否・中断などの例外は、機械出力なら JSON エラー、人向けなら標準エラーに変換されます。中断時の終了コードは 130 で、部分ダウンロードは次回に再開できる旨をエラーに含めます（`terminal/strata_cli/update_cmd.py:311-316, 378-390`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-57` — `--output` の parser 定義、選択肢、既定値。
- `terminal/strata_cli/update_cmd.py:117-139` — 人向け進捗と JSONL イベントの生成、機械出力時の進捗抑止。
- `terminal/strata_cli/update_cmd.py:307-390` — 出力モード判定、確認・更新結果、エラー変換と終了コード。
- `terminal/strata_cli/update_cmd.py:404-421` — 機械出力時の対話確認抑止とモデル停止許可の分離。
- `terminal/strata_control/updater.py:391, 435, 586`、`terminal/strata_control/engine_update.py:309, 347, 355, 388, 390, 398` — 更新中に送られる待機・段階・進捗・モデル状態イベント。
- `terminal/strata_cli/cli.py:2325-2338` — argparse による引数処理と `--json` の適用対象。
