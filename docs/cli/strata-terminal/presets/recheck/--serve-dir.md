# `--serve-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--serve-dir` |
| 別名 | なし |
| 値 | ディレクトリパス。`serve/` ディレクトリを含むフォルダー |

## 役割

再チェック中に測定用の `serve.server` ワーカープロセスを起動するとき、そのプロセスの作業ディレクトリを指定します。`strata presets recheck` のオプションであり、`strata tune auto` にも同名オプションがありますが、ここでは `presets/recheck` のスコープを説明します。

## 使い方

```sh
strata presets recheck PRESET PROFILE --serve-dir /opt/strata
```

`PRESET` は保存済みプリセット、`PROFILE` はそのプリセットが属するプロファイル名または run configuration JSON です。指定先には `serve/` が必要です（`strata_cli/tune_commands.py:82-88`）。

## 値と既定値

値は必須です。parser は値を文字列のまま受け取り、`type`、choices、独自のパス検証を設定していません（`strata_cli/tune_commands.py:82-90`）。未指定時は `None` となり、実行時には `Path(__file__).resolve().parent.parent`、すなわちインストールされた `strata_cli` モジュールの親ディレクトリを使います。この既定値はインストール配置に依存します（`strata_cli/tune_commands.py:126-130`）。

明示した相対パスは絶対パスへ変換されず `Path` に包まれ、ワーカープロセスの `cwd` として渡されます。そのため相対パスは CLI を実行したプロセスの作業ディレクトリ基準です（`strata_cli/tune_commands.py:126-130`、`strata_control/tune_session.py:478-484`）。

## 実行時の動作

`_recheck` はこの値を `WorkerSession` に渡します。セッションは `python -m serve.server --engine strata --config … --host 127.0.0.1 --port …` を構成し、指定ディレクトリを `cwd` にして子プロセスを起動します。再チェックでは保存済みプリセットの設定を適用した測定を行い、エンジンの tuning epoch が変わっている場合は標準設定との比較起動も追加します（`strata_cli/tune_commands.py:411-439`、`strata_control/tune_session.py:478-484`、`strata_control/autotune.py:885-945`）。

このオプションは測定ワーカーの起動場所を決めます。親プロセスの設定ファイル解決、モデルの `cwd`、測定内容や閾値を変更する処理は見当たりません。ワーカーはループバックの空きポートで起動され、終了時にプロセスを停止します（`strata_control/tune_session.py:461-484, 498-520`）。`--work-dir` を指定しない場合、再チェック用の一時ディレクトリが別途作られ、実行設定とログが置かれます（`strata_cli/tune_commands.py:427-429`、`strata_control/tune_session.py:430, 463-468`）。

## 適用条件と副作用

指定先がワーカーから `serve.server` を import・実行できる Strata の `serve/` 所有ディレクトリであることが前提です。parser は存在・ディレクトリ種別・`serve/` の有無を事前検査しません。プロセス起動時に `cwd` が使えない場合、`OSError` は `StartFailed(FAIL_BOOT, …)` に変換されます（`strata_control/tune_session.py:481-487`）。

再チェック自体は測定用ワーカーとエンジンを起動するため、通常は GPU/CPU を使います。指定ディレクトリに対する専用の書き込み処理は確認できません。測定用設定・ログの出力先は `--work-dir` 側です。再チェック結果はプリセットの `recheck.last_result` に保存され、判定が `keep` の場合は最終成功時刻、identity、および条件を満たす測定値も更新されます（`strata_cli/tune_commands.py:427-440`、`strata_control/presets.py:412-429`）。

## 出力とエラー

プリセットが現在の PC から大きく変化したため再チェック不可と判定される場合、処理を始めず stderr にエラー（または JSON 出力時のエラーオブジェクト）を出し、終了コード `5` を返します（`strata_cli/tune_commands.py:411-420`、`strata_cli/tune_commands.py:103-108`）。

ワーカーを起動できない場合は測定結果の `retune` 判定として記録されます。その後、通常の人向け出力では再チューニングを案内し、JSON では結果を返します。`retune` / `inconclusive` という判定自体は `_print` の成功経路で終了コード `0` です（`strata_control/tune_session.py:481-487`、`strata_control/autotune.py:918-923`、`strata_cli/tune_commands.py:437-447`、`strata_cli/tune_commands.py:95-100`）。

## 根拠

- parser と option scope: `strata_cli/tune_commands.py:49-55, 82-90`
- 既定値とパス変換: `strata_cli/tune_commands.py:126-130`
- 再チェックから worker session への適用: `strata_cli/tune_commands.py:411-440`
- worker subprocess の argv、作業ディレクトリ、起動失敗: `strata_control/tune_session.py:461-487`
- 再チェック測定と判定基準: `strata_control/autotune.py:885-955`
- 結果の永続化: `strata_control/presets.py:412-429`

