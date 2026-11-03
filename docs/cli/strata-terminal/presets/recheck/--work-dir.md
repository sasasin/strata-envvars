# `--work-dir`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--work-dir` |
| 別名 | なし |
| 値 | 作業ファイルを置くディレクトリのパス（文字列） |

## 役割

再チェック中に起動する worker の設定ファイルとログを指定ディレクトリへ保存します。既定の一時ディレクトリを使わず、実行後にログなどを確認したい場合に指定します。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config.json> --work-dir ./recheck-work
```

## 値と既定値

`argparse` は必須の文字列値を1つ受け取ります。パスの存在、種類、書き込み可否に関する事前 validation はありません。指定を省略した場合、`tempfile.mkdtemp(prefix="strata-recheck-")` で一時ディレクトリを作ります。空文字列を渡した場合も `a.work_dir` が偽となるため、一時ディレクトリが使われます。複数回指定時は通常の `argparse` の動作で最後の値が残ります。〔`strata_cli/tune_commands.py:84-92,432-434`〕

## 実行時の動作

指定値は `Path(a.work_dir)` に変換され、`WorkerSession` に渡されます。`WorkerSession` は `mkdir(parents=True, exist_ok=True)` でディレクトリを作成するため、存在しない親ディレクトリも作られ、既存ディレクトリも受け入れます。相対パスは CLI プロセスの作業ディレクトリ基準です。〔`strata_cli/tune_commands.py:432-436`、`strata_control/tune_session.py:423-432`〕

worker 起動ごとに `engine-N.log`、`worker-N.log`、`run-N.json` をこのディレクトリに書きます。ログは空にして書き始める／`w` モードで開くため、既存の同名ファイルは上書きされます。再チェックは通常、保存済み設定で測定し、必要に応じて prompt 速度の再測定や標準設定との比較のため追加 worker を起動します。〔`strata_control/tune_session.py:463-479`、`strata_control/autotune.py:907-945`〕

明示したディレクトリはコマンド終了時に自動削除されません。一方、省略時に作成した専用一時ディレクトリは `atexit` に削除処理が登録されます。〔`strata_cli/tune_commands.py:432-434`〕

## 適用条件と副作用

このオプションは `strata presets recheck` 専用です。同名の `--work-dir` は `strata tune auto` にもありますが、索引上もコマンドスコープが異なります。〔`strata_cli/tune_commands.py:22-48,84-92`〕

指定先がファイルである、または作成・書き込みできない場合はディレクトリ作成やファイル書き込みで失敗します。既存ディレクトリを指定すると、実行番号が `1` から始まるため既存の `engine-1.log`、`worker-1.log`、`run-1.json` が上書きされ得ます。ログ保持用に専用ディレクトリを指定してください。〔`strata_control/tune_session.py:431,463-468,477`〕

## 出力とエラー

再チェックの進捗・結果出力は `--output` の設定で制御されます。このコマンド自身は `--output` の既定値を `human` としており、`--work-dir` は出力形式を変えません。作業ディレクトリの作成・書き込みで発生した `OSError` は共通エラー経路で処理され、human 出力では stderr に `strata: <エラー>`、JSON 出力では `ok: false` のエラー JSON となります。〔`strata_cli/tune_commands.py:55-57,348-351`〕

## 根拠

- parser と既定値: `strata_cli/tune_commands.py:84-92`
- 指定値の変換、一時ディレクトリと終了時削除: `strata_cli/tune_commands.py:416-436`
- ディレクトリ作成: `strata_control/tune_session.py:423-432`
- worker 用ファイルとプロセス起動: `strata_control/tune_session.py:463-485`
- 再チェックが worker を起動する条件: `strata_control/autotune.py:885-945`
- エラー整形: `strata_cli/tune_commands.py:105-110,348-351`
