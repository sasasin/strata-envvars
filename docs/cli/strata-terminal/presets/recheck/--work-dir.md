# `strata presets recheck --work-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--work-dir` |
| 別名 | なし |
| 値 | パス文字列（`argparse` の型・選択肢による追加検証なし） |

## 役割

再チェック中に worker が使う実行設定とログの置き場所を指定します。保存済み tuning preset の設定で一時的なローカル engine を起動し、性能とメモリー使用量を再測定するコマンドです。

## 使い方

```sh
strata presets recheck PRESET PROFILE --work-dir ./recheck-work
```

`PRESET` は preset の参照、`PROFILE` は対象 profile 名または run configuration JSON を指します。コマンドは設定を読んで再チェックし、結果を preset の記録へ反映します。

## 値と既定値

- parser は `--work-dir` を `default=None` で定義し、値を文字列のまま受け取ります。存在確認、絶対パス化、空文字列や書式の専用 validation はありません（`strata_cli/tune_commands.py:82-90`）。
- 省略時は `tempfile.mkdtemp(prefix="strata-recheck-")` で一時ディレクトリを作り、それを worker の作業場所にします。明示時は指定文字列を `Path` に変換します（`strata_cli/tune_commands.py:427-429`）。
- worker は作業場所に `mkdir(parents=True, exist_ok=True)` を行います。したがって未作成の親ディレクトリは作られ、既存ディレクトリも使用されます。ディレクトリとして作成・利用できないパスは I/O エラーになります（`strata_control/tune_session.py:423-435`）。

## 実行時の動作

`_recheck` は引数の作業場所を `WorkerSession` に渡し、再チェック関数を呼び出します。worker の起動ごとに `engine-N.log`、`worker-N.log`、`run-N.json` を作成します。engine log は空にしてから書き、worker log は `open(..., "w")`、設定 JSON は `write_text` で書くため、同じディレクトリ内に同名のファイルがあれば上書きされます。処理後にこの作業場所やファイルを削除する処理は、確認した実行経路にはありません（`strata_cli/tune_commands.py:427-438`; `strata_control/tune_session.py:443-468,477-484`）。

再チェックは保存済み設定を適用して測定し、必要なら prompt 速度の再測定や engine 更新後の標準設定との比較も行います。`--work-dir` は測定基準や preset 保存場所を変更しません（`strata_control/autotune.py:885-905,918-948`）。`--status-file` は進捗 JSON の別出力先で、status 書き込み失敗は無視されます（`strata_cli/tune_commands.py:432-442,149-157`）。GPU lock、serve directory、boot timeout も別の parser 引数です（`strata_cli/tune_commands.py:85-90,126-136`）。

## 適用条件と副作用

このオプションは `strata presets recheck` の parser にのみ登録されています。`strata presets` の他のサブコマンドや `strata tune auto` の `--work-dir` とは別スコープです（`strata_cli/tune_commands.py:49-90`; 索引 [`README.md`](../../../README.md) の `strata presets recheck` 節）。

worker は一時ポートと loopback の host/API key を設定して `serve.server` 子プロセスを起動し、設定内の `cwd` ではなく指定された serve directory を子プロセスの作業ディレクトリに使います。`--work-dir` は run config とログの保管先であり、engine 起動時の cwd 指定ではありません（`strata_control/tune_session.py:461-484`）。明示したディレクトリを共有・再利用すると既存の `engine-N.log`、`worker-N.log`、`run-N.json` が置き換わる可能性があるため、保持したいファイルがある場所は避けてください。

## 出力とエラー

通常出力は `--output human|json` が制御し、JSON モードでは成功結果を stdout に、human モードでは再チェック中の進捗を stderr、最終結果を stdout に出します（`strata_cli/tune_commands.py:82-90,426-446`）。preset の識別に失敗する場合は `PresetError` として code 5、`OSError` / `ValueError` は既定 code 2 でエラー出力となります。人向けエラーは stderr、JSON モードでは `{"ok": false, "error": ...}` を stdout に出します（`strata_cli/tune_commands.py:103-108,289-294,342-347`）。

再チェック結果の `keep` / `retune` などは `record_recheck` に保存されます。`keep` の場合は最終確認時刻と identity を更新し、測定値が保存済み値より 3% 超速ければその測定値も更新します（`strata_cli/tune_commands.py:437-447`; `strata_control/presets.py:412-429`）。

## 根拠

- `strata_cli/tune_commands.py:49-90` — `presets recheck` の parser と option scope。
- `strata_cli/tune_commands.py:411-447` — path の選択、worker 構築、recheck 呼び出し、status・結果出力。
- `strata_control/tune_session.py:420-435,443-468,477-484,506-522` — 作業場所の作成、設定・ログ書き込み、worker 起動と終了。
- `strata_control/autotune.py:885-955` — 再チェックの測定条件・判定経路。
- `strata_control/presets.py:412-429` — 再チェック結果の preset への記録。
- `/home/sasasin/src/github.com/sasasin/strata-envvars/docs/cli/README.md:912-923` — 対象コマンドと予定リンク、option scope の照合。
