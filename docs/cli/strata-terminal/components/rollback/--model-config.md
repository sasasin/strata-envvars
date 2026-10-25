# `--model-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`。任意の文字列。parser はファイル形式や存在を検証しない |

## 役割

rollback の parser は `--model-config` を受理しますが、このコマンドのロールバック処理では値を参照しません。エンジンの切替前テストに使う run config を渡しても、ロールバック対象エンジンの起動テストには使われず、ファイルも読み込まれません。

## 使い方

```sh
strata components rollback --model-config /path/to/run-config.json
```

この例ではオプションの構文を示しています。rollback は値の内容にかかわらず同じ処理を行います。

## 値と既定値

- `RUN_CONFIG.json` は必須の値です。値を省略すると `argparse` が引数エラーにします。
- 既定値は `None`（未指定）です。
- parser では `type`、`choices`、独自 validator を指定していません。値は文字列として受理され、パスの存在・JSON 内容は rollback 経路で検証されません。
- 重複指定時の扱いを独自に変更する処理はありません。`argparse` の通常の `store` 動作では最後に指定した値が namespace に残りますが、rollback 処理はその値を使いません。

## 実行時の動作

`strata_cli/update_cmd.py` の `_common()` が `--model-config` を追加し、`components rollback` parser も同じ共通引数を使います。実行時には `a.model_config` が `Context.run_config` に設定されます。しかし rollback 分岐は `updater.rollback_engine(ctx)` を呼び、同関数は `ctx.run_config` を参照しません。そのため、このコマンドでの当オプションの実行時効果はありません。

`rollback_engine()` は前回保持されたエンジンを探し、稼働中エンジンがあれば `--wait` の設定に従って待機または失敗し、保持済みパッケージの manifest と全ファイルを検証してから、状態ファイルの pin を更新してそのエンジンを次回起動対象にします。モデル設定を使った test-start は行わず、feed の取得・ダウンロードも行いません。これらは rollback の動作であり、`--model-config` によるものではありません。

この同じオプションは `strata update` / `strata components update` にも登録されています。それらの更新経路では値が `default_test_start()` に渡され、指定された run config を新エンジンの test-start に使います。これは rollback には適用されない sibling command の挙動です。

## 適用条件と副作用

rollback では、指定値が存在しないパスや不正な JSON であっても、その値を読む経路がないため `--model-config` に起因するファイルアクセスやエラーはありません。ロールバック自体は `.updates/state.json` の engine 状態（`pinned`、`previous`、`active`、必要に応じ `skipped` と履歴）を書き換えます。また、エンジン identity が変わった場合は tuning preset を再確認対象として記録します。モデル設定ファイルを変更する処理はありません。

## 出力とエラー

成功時、human 出力は `Engine rolled back: <from> -> <to>.` と preset の状態を案内します。JSON 系出力は rollback 結果を含む JSON を stdout に出します。エラーは human 出力なら `strata: ...` を stderr に、JSON 系なら `ok: false` と error 情報を stdout に出します。

主な失敗条件は、戻り先が記録されていない（終了コード 2）、既にその戻り先が有効（2）、以前のパッケージが欠損・破損している（5）、現在の PC で以前のパッケージを選択できない（5）、エンジン稼働中で待機条件を満たせない（7）です。値のファイル不在や JSON 不正は rollback では失敗条件になりません。共通 parser で値そのものを省略した場合は usage error（通常終了コード 2）です。

## 根拠

- 対象 revision と作業状態: Strata checkout の `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`。
- コマンド階層と共通 parser の登録: `strata_cli/cli.py:115`, `strata_cli/cli.py:140`。
- parser 定義、値の既定値、`Context.run_config` への設定、rollback 分岐: `strata_cli/update_cmd.py:30-59`, `strata_cli/update_cmd.py:174-196`。
- run config が実際に参照される更新時 test-start 経路: `strata_control/updater.py:331`, `strata_control/updater.py:842-850`, `strata_control/updater.py:957-960`。
- rollback の戻り先確認、パッケージ検証、pin と状態更新、結果: `strata_control/updater.py:1033-1078`。
- エラーの human/JSON 出力: `strata_cli/update_cmd.py:163-172`, `strata_cli/update_cmd.py:225-234`。
- rollback の成功表示: `strata_cli/update_cmd.py:185-196`。
