# `strata presets recheck --work-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--work-dir` |
| 別名 | なし |
| 値 | 作業ディレクトリのパス（文字列） |

## 役割

プリセットの短い再チェックで起動する計測用 worker の設定 JSON とログを置く場所を指定する。通常は一時ディレクトリが使われ、明示した場合は診断用ファイルを実行後も残せる。これは `strata tune auto` にもある同名オプションとは別の parser 引数で、ここでは `strata presets recheck` にだけ適用される（`terminal/strata_cli/tune_commands.py:21-48,55-96`）。

## 使い方

```sh
# 計測 worker の設定とログを ./recheck-work に残す
strata presets recheck PRESET PROFILE --work-dir ./recheck-work
```

`PRESET` は保存済みプリセット、`PROFILE` はそのプリセットが属する profile 名または run configuration JSON である。引数順と `--work-dir` の受理範囲は recheck parser に定義されている（`terminal/strata_cli/tune_commands.py:88-96`）。

## 値と既定値

- 値は必須の文字列で、parser にパス形式・存在・書込可否の事前 validation はない。既定値は `None`（未指定）。（`terminal/strata_cli/tune_commands.py:88-96`）
- 指定値は `Path(a.work_dir)` に変換される。相対パスはプロセスの現在ディレクトリ基準で解決され、`expanduser()` などの展開処理は行われない。（`terminal/strata_cli/tune_commands.py:615-644`）
- 空文字列を渡した場合は偽値として扱われ、明示指定なしと同様に自動生成ディレクトリが使われる。（`terminal/strata_cli/tune_commands.py:640-642`）

## 実行時の動作

recheck はプリセットの状態と対象構成を照合した後、明示値があればそのパスを `WorkerSession` に渡す。未指定なら `strata-recheck-` 接頭辞の一時ディレクトリを作り、終了時の削除を `atexit` に登録する。明示したディレクトリは `WorkerSession` が親ディレクトリも含めて作成し、削除登録は行わないため、worker 設定とログが残る。（`terminal/strata_cli/tune_commands.py:615-644`; `terminal/strata_control/tune_session.py:484-500`）

各計測 worker は `engine-N.log`、`worker-N.log`、`run-N.json` をそのディレクトリに書く。既存ディレクトリを指定すると、同名ファイルはログ初期化や `open(..., "w")`、`write_text()` により上書きされる。（`terminal/strata_control/tune_session.py:527-552,562-569`）

## 適用条件と副作用

- `--work-dir` は再チェックを実行する際の作業領域に適用される。再チェック本体は保存済み設定で worker を起動し、測定に失敗した場合など必要に応じて標準設定の比較も行う。計測結果は完了後にプリセットへ記録される。（`terminal/strata_cli/tune_commands.py:643-657`; `terminal/strata_control/autotune.py:937-1008`）
- 指定ディレクトリは作成され、計測設定・worker/engine ログが書き込まれる。明示指定時は自動削除されず、同名の既存ファイルを上書きする可能性がある。（`terminal/strata_control/tune_session.py:494-495,547-552,562-569`）
- 存在する通常ファイルをディレクトリとして指定した場合や、作成・書込みに失敗した場合の `OSError` は `strata presets` のエラー経路で処理される。（`terminal/strata_control/tune_session.py:494-495`; `terminal/strata_cli/tune_commands.py:472-530`）

## 出力とエラー

既定の人間向け出力は標準出力、進捗メッセージは標準エラーに出る。`--output json` を指定した場合は人間向け進捗を抑止し、JSON 結果を標準出力へ出す（この `--output` は `presets` の共通 parser 引数）。（`terminal/strata_cli/tune_commands.py:59-61,615-661`; `_print` / `_fail`: `terminal/strata_cli/tune_commands.py:101-114`）

作業ディレクトリの作成・書込みに伴う `OSError` は人間向けでは標準エラーに `strata: <理由>`、JSON モードでは `ok: false` の JSON として報告され、通常の `OSError` は終了コード 2 になる。プリセット不整合など `PresetError` は終了コード 5。（`terminal/strata_cli/tune_commands.py:109-114,472-530`）

## 根拠

- `terminal/strata_cli/tune_commands.py:55-96` — `presets recheck` の parser、位置引数、共通 `--output`、`--work-dir` の default と scope。
- `terminal/strata_cli/tune_commands.py:615-644` — パスの選択、一時領域の生成と削除登録、worker への引き渡し。
- `terminal/strata_control/tune_session.py:484-500,527-569` — 作業ディレクトリ作成、計測ファイル名と書込み、worker 起動。
- `terminal/strata_control/autotune.py:937-1012` — 再チェックの測定と結果経路。
- `terminal/strata_cli/tune_commands.py:101-114,472-530,652-661` — 出力、例外処理、結果保存後の表示。
