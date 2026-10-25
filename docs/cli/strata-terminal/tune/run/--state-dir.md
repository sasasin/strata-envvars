# `--state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリパスを表す文字列（parser に型変換・形式検証なし） |

## 役割

チューニング sweep のジョブ記録と履歴を保存する root ディレクトリを指定します。この値は `strata tune run` の parser にだけ定義されています。同名オプションを持つ `apply`、`rollback`、`status`、`list` とは別スコープであり、それぞれの文書を参照してください。

## 使い方

```sh
strata tune run --engine ./strata --backend cpu --model example --state-dir ./tuning-state
```

この例の `./tuning-state` は実行時の作業ディレクトリからの相対パスです。

## 値と既定値

- 値は `argparse` の通常の文字列として受け取り、既定値は `None` です。`--state-dir` 自体を省略した場合、または値が空文字列の場合、`STRATA_TUNE_DIR` が空でなければその値を採用します。両方とも未設定または空なら、OS 別の既定 root を使います。
- 優先順位は、truthy な `--state-dir`、truthy な `STRATA_TUNE_DIR`、OS 別既定値の順です。空白だけの値は truthy なので採用されます。`Path(value)` に渡され、`~` の展開や絶対パス化、存在確認による fallback は行われません。
- 既定 root は Windows では `%LOCALAPPDATA%\Strata\tuning`（`LOCALAPPDATA` がなければ home の `AppData\Local\Strata\tuning`）、POSIX では `$XDG_STATE_HOME/strata/tuning`（未設定なら `~/.local/state/strata/tuning`）です。

## 実行時の動作

CLI はこの root を `Tuner` に渡します。Tuner は root の下に plan ID のディレクトリを作り、その中の `job.json` を進捗・結果の状態ファイルとして一時ファイル経由で更新します。排他 lease `tuning.lease` もジョブディレクトリ内に作成され、正常な終了経路では削除されます。プロセス異常終了時には lease が残ることがあり、次の実行は既存 lease を理由付きで拒否します。履歴は選択した root の `history/history.jsonl` に追記されます。

同じ状態 root を `strata tune status`、`list`、`apply` 等にも指定しなければ、そちらの既定 root からこの run のジョブは見つかりません。`run` 自体は推奨値を記録するだけで、実行設定ファイル・profile への適用は行いません。

## 適用条件と副作用

このオプションは `strata tune run` の状態保存先だけを変えます。実行時には指定先にジョブ用ディレクトリ、`job.json` とその更新用一時ファイル、lease、履歴ファイルを作成・更新します。directory 作成・書き込みに必要な権限が必要です。既定値の決定は `STRATA_TUNE_DIR` と OS の状態ディレクトリに依存します。

## 出力とエラー

- 値が存在しない engine binary の指定は状態ディレクトリ作成前に拒否され、human 出力では stderr に `strata: no engine binary at ...`、終了コード `2` になります。JSON 出力では同じコードとエラーを JSON にします。
- 状態ディレクトリ作成時などの `OSError` は CLI 共通処理でファイル操作エラーとして表示され、終了コード `6` になります。JSON 出力の場合は JSON エラーです。
- Tuner 起動後の例外は通常 `job.json` に `failed` 状態とエラーを記録し、run の結果として出力します。ただし記録自体の書き込みに失敗した場合は CLI の `OSError` 経路になります。

## 根拠

- `strata_cli/cli.py:414-459` — `run` parser と `--state-dir` の定義（`default=None`、型・choices・validator なし）。
- `strata_cli/cli.py:1643-1650` — CLI 値、`STRATA_TUNE_DIR`、OS 別既定 root の優先順位。
- `strata_cli/cli.py:1708-1710,1742-1768,1802-1806` — 選択した root の run への受け渡し、engine の事前確認、Tuner 起動。
- `strata_cli/cli.py:519-532,2176-2183` — エラー出力形式とファイル操作エラーの終了コード。
- `strata_control/paths.py:13-21` — Windows/POSIX の既定 state base。
- `strata_control/tuning.py:317-362` — ジョブディレクトリ、`job.json`、一時ファイルと atomic replace。
- `strata_control/tuning.py:389-419,423-484` — lease 作成・解放と失敗記録。
- `strata_control/tuning.py:682-715` — `history/history.jsonl` への履歴記録。
- `docs/cli/README.md:741-767` — 索引上のコマンド階層および予定リンク。
- [`STRATA_TUNE_DIR` 環境変数文書](../../../../STRATA_TUNE_DIR.md) — 環境変数の補足。環境変数のこの文書内の記載は Strata commit `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）の調査であり、本書の source 根拠には混在させていません。

安全に実行できる同一 revision の CLI `--help` は今回実行していません。parser 定義と実使用箇所をソースで確認しました。Release 配布物・別 OS 上での実行結果は調査対象外です。
