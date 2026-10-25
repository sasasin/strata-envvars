# `--model-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--model-config RUN_CONFIG.json` |
| 別名 | なし |
| 値 | モデルの run config JSON ファイルへのパス。parser では文字列として受け取る |

## 役割

更新候補エンジンを切り替える前に行う test-start で使うモデルの run config を指定します。指定しない場合は、インストール済みモデルから test-start 用の設定を自動選択します。これはモデルの選択・更新オプションではありません。

## 使い方

```sh
strata components update --model-config /path/to/strata-model.json
```

パスは実行時の作業ディレクトリから解決されます。`argparse` 上はこの値を必須とし、値の形式やパスの存在を parser 段階では検査しません。

## 値と既定値

- 値の既定値は `None` です。空文字列を `--model-config=` で明示した場合も、実行時には未指定と同じ扱いになります。
- `RUN_CONFIG.json` は `utf-8-sig` で読める JSON オブジェクトで、`args` が文字列だけの配列、`exe` と `tokenizer` が空でない文字列である必要があります。ファイルが読めない、JSON が不正、または必須フィールドが合わない場合、test-start は失敗します。
- 相対パス、ホームディレクトリ記号 `~`、拡張子は parser による検証・展開を受けません。相対パスはプロセスの作業ディレクトリ基準です。

## 実行時の動作

`strata components update` と `strata update` は共通 parser の `_common()` でこの引数を定義します。値は update context の `run_config` にそのまま渡され、エンジン更新処理が test-start を実行する際に使います（`strata_cli/update_cmd.py:30-40, 42-55, 174-184`、`strata_control/updater.py:316-335, 953-960`）。

指定値がある場合はそのパスの JSON を使います。未指定または空文字列なら、インストール済みモデルのうち必要ファイルが揃ったものを探し、保存 profile が使うモデルを優先し、それ以外はモデル ID 順で選びます。対象モデルがなければ、設定を使った生成試験の代わりに新エンジンの `--version` 起動確認を行います（`strata_control/updater.py:701-717, 842-850`）。

設定 JSON は直接書き換えません。test-start 用の一時コピーでは `exe`、`backend`、`host`、空き loopback port、`log` を試験用に設定し、元の `lib_dirs` を除去します。そのコピーから一時 profile と隔離 runtime を作り、新エンジンを起動して必要なら一 token の生成を確認し、最後に停止します（`strata_control/updater.py:851-896`）。

この値が使われるのはエンジンを実際にインストールする経路です。`--check` は feed の確認で終了するため test-start をしません。また `--no-engine` でエンジン更新を無効にした場合もこの設定は使われません（`strata_cli/update_cmd.py:203-224`、`strata_control/updater.py:1274-1295`）。エンジンが最新などで更新対象にならない場合にも test-start は発生しません（`strata_control/updater.py:926-937`）。

## 適用条件と副作用

- 新しいエンジンが選ばれ、ダウンロードと package 検証を通過した後に設定ファイルを読みます。そのため指定ファイルの不備が判明する前に、更新 feed の確認、ネットワーク取得、staging 展開が行われることがあります。
- test-start は stage 内の新エンジンを使い、隔離した components/profile/runtime と `127.0.0.1` の空き port で行います。通常のユーザー profile やモデル設定ファイルは変更しません。試験ログは `.updates/logs` に保存され、古い試験ログは最大5件に整理されます（`strata_control/updater.py:774-785, 842-896`）。
- 試験に成功して初めて新エンジンが有効化されます。失敗時は更新候補をインストールせず、現在のエンジンを維持します（`strata_control/updater.py:953-976`）。
- `strata components rollback` も parser 上は `_common()` の引数を受理しますが、rollback 分岐は test-start をせずに戻るため、このオプションはそこで使われません（`strata_cli/update_cmd.py:57-59, 182-196`）。

## 出力とエラー

`--model-config` の値不足は `argparse` の usage error になります（通常終了コード 2）。指定ファイルを読めない、JSON として不正、必須フィールドが不足する、またはモデル起動・生成確認に失敗する場合は test-start failure となり、更新コマンドは終了コード 6 を返します。失敗理由は通常出力では stderr の `strata: ...`、`--json` または `--output json` では JSON の `error` に出力されます。試験失敗の詳細ログは `.updates/logs/test-start-<version>.log` に保持されます（`strata_control/profiles.py:135-147, 236-249`、`strata_control/updater.py:79-123, 821-839, 953-976`、`strata_cli/update_cmd.py:163-172, 225-234`）。

## 根拠

- parser と共有 scope: `strata_cli/update_cmd.py:30-59`
- `components update` から update context への値渡し、check/rollback 分岐: `strata_cli/update_cmd.py:174-224`
- モデル設定の自動選択: `strata_control/updater.py:701-717`
- 設定読込、隔離 test-start と一時ファイル処理: `strata_control/updater.py:842-896`
- run config の形式検証: `strata_control/profiles.py:135-147, 236-249`
- test-start 失敗時の現行エンジン維持と終了コード: `strata_control/updater.py:79-123, 953-976`
