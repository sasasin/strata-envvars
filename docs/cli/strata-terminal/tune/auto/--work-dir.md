# `--work-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--work-dir` |
| 別名 | なし |
| 値 | ディレクトリパス（文字列） |

## 役割

自動チューニング中に使う設定ファイルとログの置き場所を指定する。既定では実行ごとの一時ディレクトリを使い、終了時に削除する。独自のパスを指定すると、測定ごとの設定とログをその場所に残せる。

## 使い方

```sh
strata tune auto qwen/IQ3_S --work-dir ./tune-work
```

## 値と既定値

- `--work-dir` は値を1つ取る。parser は文字列として受け取り、パスの存在・形式・書き込み権限を事前検証しない。
- 省略時は `tempfile.mkdtemp(prefix="strata-tune-")` で一時ディレクトリを作る。
- 明示値は `Path(a.work_dir)` として使う。相対パスはプロセスの作業ディレクトリ基準で扱われる。空文字列は分岐上「未指定」と同様に扱われ、一時ディレクトリになる。

## 実行時の動作

`strata tune auto` の処理で `--work-dir` を指定すると、そのパスを `WorkerSession` に渡す。`WorkerSession` は親ディレクトリも含め `mkdir(parents=True, exist_ok=True)` で作成する。チューニングの各測定で `run-N.json`、`engine-N.log`、`worker-N.log` をその中に作り、エンジンを起動する設定とログの出力先に使う。繰り返し同じディレクトリを使う場合、同じ番号のファイルは空にするか書き直されるため、以前の内容は保持されない。

指定パスには終了時の削除処理を登録しないため、ディレクトリとファイルは実行後も残る。省略時の一時ディレクトリは `atexit` に `shutil.rmtree(..., True)` を登録して削除する。起動に失敗した直近のエンジンログは、通常の作業ディレクトリとは別にプリセット領域の `last-failed-engine.log` にも保存される場合がある。

## 適用条件と副作用

- このオプションは `strata tune auto` に登録されている。`strata tune` の別サブコマンドや `strata presets recheck` にも独立した `--work-dir` があるが、それぞれ別の parser scope であり、この文書の対象外。
- 指定先がなければ作成する。既存のディレクトリなら再利用し、その中の `run-N.json` とログを作成・上書きする。
- チューニング自体が失敗しても指定ディレクトリを削除する処理はない。不要になったファイルは利用者が削除する。

## 出力とエラー

オプション値自体について、専用の validation message や範囲エラーは定義されていない。ディレクトリ作成やファイル書き込みができない場合は、その処理で `OSError` が起き得る。`auto` 内でこのパス操作を捕捉して CLI 用のエラーに変換する処理は確認できなかったため、表示や終了コードはここでは断定しない。なお、子プロセス起動失敗は `WorkerSession` が `StartFailed` に変換し、`auto` のチューニング結果として扱う。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` の parser 定義。`--work-dir` は `default=None` の値付き引数で、説明は実行設定・ログの場所。
- `terminal/strata_cli/tune_commands.py:309-353` — 対象読み込み・エンジン確認後に plan-only 分岐があり、計測を行う場合にだけ作業ディレクトリ処理へ進む。
- `terminal/strata_cli/tune_commands.py:371-376` — 明示値または一時ディレクトリを選択し、一時ディレクトリだけ削除登録したうえで `WorkerSession` を作る。
- `terminal/strata_cli/tune_commands.py:206-220` — 失敗したエンジンログの末尾をプリセット領域の `last-failed-engine.log` に保存し、現在ユーザーだけにアクセスを制限する処理。
- `terminal/strata_control/tune_session.py:484-504` — 作業ディレクトリを作成する処理。
- `terminal/strata_control/tune_session.py:527-572` — 測定番号ごとの設定・ログファイルを書き、serve worker を起動する処理。起動不能時は `StartFailed` に変換する。
- `terminal/strata_control/tune_session.py:590-610` — 起動後の失敗を記録し、プロセス終了処理を行う箇所。
- `terminal/strata_cli/cli.py:423-424,514-515` — `tune` サブコマンド群の登録と `tune auto` parser の追加。

調査範囲は上記 revision の CLI parser、`auto` 実装、`WorkerSession` の作業ディレクトリ利用まで。実行環境ごとのファイルシステム権限や `atexit` が実行されない異常終了時の挙動は実測していない。
