# `--model-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`。必須の文字列値。parser 自体は形式・存在を検証しない |

## 役割

新しい engine を切り替える前に行う test-start で使用する run config を指定します。既定ではインストール済みモデルから run config を探します。指定すると、その設定を使ってステージング中の engine を起動し、モデルの読み込みと1 token の生成を確認します。

同じ parser 定義が `strata update` にも使われます。`strata components rollback` にも共通 parser のため登録されていますが、rollback 処理はこの値を参照しません（rollback 側の詳細は [`strata components rollback --model-config`](../../rollback/--model-config.md) を参照）。

## 使い方

```sh
strata components update --model-config /path/to/run-config.json
```

## 値と既定値

- 値は必須で、`argparse` の `metavar` は `RUN_CONFIG.json` です。値を省略すると parser の usage error になります。
- 未指定時の既定値は `None` です。`type`、`choices`、専用 validator は設定されておらず、parser は値を文字列として受理します。
- 重複指定時に独自処理はなく、`argparse` の通常の `store` 動作で最後の値が使われます。
- 指定値は `Path` に渡されます。`expanduser()` を呼ぶ処理はなく、相対パスはプロセスの現在ディレクトリを基準に読み込まれます。

## 実行時の動作

`components update` は共通 `run()` を実行し、`a.model_config` を `updater.Context.run_config` に渡します。通常の更新では engine のダウンロード・検証・ステージング後に test-start を行い、そのとき指定があれば指定パスを、なければ `discover_run_config()` が選んだインストール済みモデルの設定を使います。インストール済みモデルが見つからず設定も指定されていない場合は、モデル生成を伴わない engine の `--version` smoke check に進みます。

指定した設定ファイルを読み、JSON object として engine 用の設定に読み込みます。その後、テスト対象 engine の executable と backend、loopback host、空き port、隔離 sandbox 内の log path で上書きし、一時的な profile/runtime/component folder を使って engine を起動します。profile 作成時には、設定に `args` 配列（文字列要素のみ）と空でない `exe`・`tokenizer` があることも検査されます。起動後に generation-ready でなければ1 token probe を行い、成功するまで確認します。テスト用 runtime は停止され、一時 sandbox は削除されます。通常のユーザープロファイルや実行中 engine を使うテストではありません。

このオプションが作用するのは engine の test-start です。`--check` は `updater.check()` で早期 return するため値を読みません。`--no-engine` を付けた更新や、engine が更新対象にならず test-start 自体が発生しない場合も値は使われません。Control/app の更新にこの設定が適用される経路はありません。

## 適用条件と副作用

設定ファイルは engine を取得・ステージングした後、test-start で読み込まれます。そのため、存在しないパス、読めないファイル、不正な JSON、実行に使えない設定は parser 時点で拒否されず、engine の test-start 失敗になります。指定設定でテストに失敗した場合、新 engine への切替は行われず、従来の engine が引き続き使われます。失敗した test-start の診断情報は updater の履歴・失敗記録に保存され、engine log は update log 領域に保持されます（起動エラーの一般例外では専用 test-start failure に変換されます）。

run config の元ファイルは読み取り専用です。テスト用のコピーは stage 内の一時 sandbox に作られ、backend 等のテスト用値を上書きします。通常更新では feed/package の取得、展開、一時 runtime の起動・停止が発生するため、`--model-config` を指定しても更新処理全体が読み取り専用になるわけではありません。

## 出力とエラー

test-start が失敗すると、更新処理は engine を切り替えず失敗結果を返します。human 出力では `strata: ...` が stderr に出て、machine output (`--output json` / `jsonl`) では `ok: false` と error 情報を stdout に出します。test-start failure は update の失敗コード 6 の経路です。Ctrl-C は共通処理で終了コード 130 を返します。

## 根拠

- 索引上のコマンド scope と予定リンク: `docs/cli/README.md` の `strata components update` 節（このリポジトリ）。
- 調査 revision と作業ツリー状態: `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`。
- 共通 parser、値の既定値、`components update` / `components rollback` への登録: `strata_cli/update_cmd.py:30-59`。
- `Context.run_config` への値の引き渡し、check と rollback を含む分岐順序、更新呼び出し: `strata_cli/update_cmd.py:163-224`。
- インストール済み設定の選択規則: `strata_control/updater.py:701-717`。
- test-start に使う設定選択、設定読み込み・上書き、隔離 sandbox、engine 起動と generation probe、停止・cleanup: `strata_control/updater.py:842-896`。
- test-start 失敗時の記録と engine 切替前の実行順: `strata_control/updater.py:953-976`。
- 一時 profile 作成時に行われる run config の JSON / 必須項目検査: `strata_control/profiles.py:135-147`, `strata_control/profiles.py:236-249`。
- human / machine エラー出力と終了コードの伝播: `strata_cli/update_cmd.py:163-172`, `strata_cli/update_cmd.py:213-234`。
