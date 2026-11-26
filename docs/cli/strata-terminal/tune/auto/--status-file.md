# `strata tune auto --status-file`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--status-file` |
| 別名 | なし |
| 値 | JSON 状態を書き出すファイルパス（文字列）。既定値は `None`（出力しない） |

## 役割

自動チューニング中の進捗と最終結果を JSON ファイルに書き出します。parser の説明ではデスクトップアプリ向けとされていますが、CLI からも任意のパスを指定できます。チューニングの対象・設定は位置引数 `target` で渡します。

## 使い方

```sh
strata tune auto my-profile --status-file /tmp/strata-tune-status.json
```

`target` にはインストール済みモデル、保存済み profile、または実行設定 JSON を指定できます。`--status-file` を省略した場合は状態ファイルを出力しません。

## 値と既定値

- 値はパス文字列で、parser に型変換・存在確認・書込み可能性などの事前検証はありません。既定値は `None` です (`terminal/strata_cli/tune_commands.py:21-49`)。
- 親ディレクトリは作成されません。指定先や一時ファイルへの書込み、置換で `OSError` が起きても、その例外は状態出力処理内で無視されます (`terminal/strata_cli/tune_commands.py:240-248`)。

## 実行時の動作

`strata tune auto` の進捗 callback は受け取った進捗情報を状態辞書に反映し、残り時間の表示用フィールドを加えてから、指定先へ JSON を書きます。処理完了時には `state: "done"`、`stage: "done"` とチューニング結果を含めた状態をもう一度書きます (`terminal/strata_cli/tune_commands.py:355-369`, `terminal/strata_cli/tune_commands.py:383-385`, `terminal/strata_cli/tune_commands.py:414-420`)。

書込みは UTF-8 の JSON を `<指定パス>.tmp` に一旦作成し、atomic replace 関数で指定パスへ置換します。既存の指定先があれば置き換わります。置換関数は Windows で読取り中のファイルへの `PermissionError` を最大 5 秒再試行し、それ以外のエラーは呼出し元へ返しますが、このオプションの状態書込み処理は `OSError` を捕捉して無視します (`terminal/strata_cli/tune_commands.py:240-248`, `terminal/strata_control/atomic.py:18-34`)。

`--plan` は計画を表示して tuner を開始せずに戻る分岐であり、その前に進捗 callback は設定されません。このため `--status-file` は更新されません。また、対象解決や validation など tuner 開始前に返るエラー経路でも状態ファイルへの書込みはありません (`terminal/strata_cli/tune_commands.py:314-353`, `terminal/strata_cli/tune_commands.py:355-369`)。

同じ文字列の `--status-file` は `strata presets recheck` にもありますが、そちらは別コマンドの parser と実行経路です。本書の対象は `strata tune auto` のみです (`terminal/strata_cli/tune_commands.py:21-49`, `terminal/strata_cli/tune_commands.py:88-96`)。

## 適用条件と副作用

- `--status-file` が指定され、通常のチューニングが進捗 callback を呼ぶときに状態ファイルを書きます。省略時は `_write_status` が何もしません (`terminal/strata_cli/tune_commands.py:240-242`, `terminal/strata_cli/tune_commands.py:362-369`)。
- 指定先と同じディレクトリに一時ファイル `<指定パス>.tmp` を作成し、最終ファイルを置換します。したがって一時ファイルの作成権限も必要です。書込み失敗は CLI の処理失敗として通知されず、進捗がファイルに反映されない場合があります (`terminal/strata_cli/tune_commands.py:243-248`)。
- status ファイル自体を削除する処理はこの経路では確認できません。`--work-dir` の有無による作業用ディレクトリの後始末は別処理であり、status ファイルの指定先とは連動しません (`terminal/strata_cli/tune_commands.py:371-373`)。

## 出力とエラー

状態ファイルへの `write_text` または atomic replace で発生した `OSError` は握りつぶされます。専用の警告、標準エラー出力、終了コード変更はこの書込み処理にはありません (`terminal/strata_cli/tune_commands.py:240-248`)。ただし状態ファイル以外のチューニング処理の失敗は、このオプションの説明範囲外です。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-49` — `strata tune auto` parser と `--status-file` の既定値・help。
- `terminal/strata_cli/tune_commands.py:240-248` — JSON 化、`.tmp` への書込み、atomic replace、`OSError` の無視。
- `terminal/strata_cli/tune_commands.py:314-353` — `--plan` と事前失敗の return 経路。
- `terminal/strata_cli/tune_commands.py:355-385` — status 初期値、進捗 callback、tuner 実行。
- `terminal/strata_cli/tune_commands.py:414-425` — 完了状態の書込みと通常出力。
- `terminal/strata_control/atomic.py:18-34` — replace の再試行条件と `os.replace`。
- `terminal/strata_cli/tune_commands.py:88-96` — 別コマンド `strata presets recheck` にある同名オプション。
