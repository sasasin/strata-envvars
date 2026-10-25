# `strata tune status`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune status` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/tuning.py` |

## 役割

チューニングジョブの保存済み状態とレポートを読み、端末向けの要約または JSON として表示します。ジョブの実行や推奨設定の適用は行いません。推奨値の適用は [`strata tune apply`](../apply/README.md)、ジョブの作成は [`strata tune run`](../run/README.md) を参照してください。

## 使い方

```sh
# 既定の保存場所からジョブを表示
strata tune status JOB_ID

# 保存場所と JSON 出力を指定
strata tune status JOB_ID --state-dir ./tuning-state --output json
```

`JOB_ID` は必須の位置引数です。`--state-dir` を省略すると、環境変数 `STRATA_TUNE_DIR` が設定されていればその値を使い、未設定ならユーザー状態ディレクトリの `tuning/` を使います。POSIX では既定の状態ベースは `$XDG_STATE_HOME/strata`（`XDG_STATE_HOME` 未設定時は `~/.local/state/strata`）、Windows では `%LOCALAPPDATA%\Strata` です。

## 表示内容と動作

- 指定した保存場所の `<JOB_ID>/job.json` を読みます。ファイルが見つからない場合はエラーにします。
- 既定の `--output human` はジョブ ID、状態、backend と目的を表示します。レポートがあれば計測指標、試行数、ベースライン、推奨候補または推奨なしの理由、失敗した候補を続けて表示します。失敗理由は表示上 90 文字までです。
- `--output json` は読み込んだジョブ全体を `{"schema_version":1,"ok":true,"job":...}` の形で出力します。イベントや候補、エラー、レポートなど、保存記録に含まれる項目も返します。
- このコマンドの処理分岐は既存の `job.json` の読取りと出力を行い、設定ファイルへの推奨値適用やジョブ更新は行いません。保存ファイル自体はチューニング実行側が状態遷移ごとに書き換えます。

## 注意点と失敗

- `--output` は `human` または `json` のみ受け付け、既定値は `human` です。未知の値や必須の `JOB_ID` の欠落は argparse が拒否します。
- この `status` 分岐では `JOB_ID` の形式検証をしておらず、保存場所と結合してファイルパスを作ります。通常は `strata tune run` が返した ID を指定してください。
- 対象ファイルが存在しない、または通常ファイルでない場合は「no tuning job `<JOB_ID>`」を報告し、終了コード 2 になります。JSON 出力では `ok: false` とエラー情報を含む JSON を出します。
- ファイルの読み取りで OS エラーが起きた場合は共通エラー処理を通り、終了コード 6 になります。JSON が壊れている場合は JSON デコード例外が `ValueError` として処理され、終了コード 2 のエラーになります。
- `strata tune status` はジョブ記録の照会です。`strata tune auto status` は保存済みプリセットの有効性を確認する別の階層のコマンドです。

## 関連文書

- [`strata tune` コマンド概要](../README.md)
- [`strata tune run`](../run/README.md)
- [`strata tune apply`](../apply/README.md)
- [`strata tune list`](../list/README.md)
- [`--output`](--output.md)・[`--state-dir`](--state-dir.md)・[`--help`](--help.md)
- [CLI 索引](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:395-397,477-480` — `tune status` parser と必須位置引数、`--state-dir`、出力形式。
- Strata `strata_cli/cli.py:1632-1650,1678-1706` — 状態ディレクトリの選択、未検証の `JOB_ID` からのジョブ記録パス構築、human/JSON 表示、未発見時のエラー。
- Strata `strata_cli/cli.py:527-542,2166-2183` — JSON・人間向けの共通エラー形式と `ValueError` / `OSError` の終了コード。
- Strata `strata_control/paths.py:13-21` — OS ごとのユーザー状態ベース。
- Strata `strata_control/tuning.py:339-362,372-375` — `job.json` の構造と、チューニング側が状態遷移時に保存する処理。
- 調査範囲は上記 checkout のソースです。別の配布バイナリ、OS ごとの実行環境での実出力は確認していません。
