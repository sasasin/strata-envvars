# `--model-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`（モデル起動設定ファイルのパス） |

## 役割

エンジン更新時のテスト起動で使う run config を指定します。更新対象エンジンを切り替える前に、その設定でステージ済みエンジンを起動し、モデル読み込みと1 token の応答を確認します。このオプションは更新後の通常起動設定を変更するものではありません。

## 使い方

```sh
strata update --model-config /absolute/path/to/strata-example.json
```

このパスはテスト起動に使われます。CLI は実行前に存在確認や内容検証をせず、テスト起動時に読み込みます。

## 値と既定値

- 値は必須です。parser は `--model-config` に `default=None` と metavar `RUN_CONFIG.json` を設定し、型・選択肢・独自 validation は設定していません。省略時は `None` です。同じ引数を複数回指定した場合の値は argparse の通常の処理に従います。【`strata_cli/update_cmd.py:37-38`】
- 省略時、既定のテスト起動処理はインストール済みモデルを列挙し、ファイルが存在するモデルを候補にします。保存済みプロファイルが使う設定を優先し、それ以外はモデル ID 順に選びます。該当モデルがなければモデルなしの smoke test に進みます。【`strata_control/updater.py:701-717`, `strata_control/updater.py:842-850`】
- 指定ファイルは UTF-8 (BOM 付きも可) の JSON として読み込まれ、プロファイル用 run config 検証では `args` が文字列配列であること、`exe` と `tokenizer` が空でない文字列であることが確認されます。これらの検証は parser 段階ではなく、テスト起動時に行われます。【`strata_control/updater.py:852-854`, `strata_control/updater.py:867-870`, `strata_control/profiles.py:135-147`】

## 実行時の動作

parser の値は `update_cmd.run()` から `updater.Context.run_config` に渡されます。【`strata_cli/update_cmd.py:174-184`】通常の `strata update` では、エンジンをダウンロード・検証・ステージした後、指定 config を使ったテスト起動を行い、成功してからエンジンを切り替えます。【`strata_control/updater.py:944-959`, `strata_control/updater.py:977-1027`】

テスト用コピーでは `exe` と `backend` をテスト対象エンジン用に置き換え、`lib_dirs` を除去し、接続先を `127.0.0.1` と空きポートにし、ログを一時領域に設定します。元の指定ファイル自体は書き換えません。分離した component/runtime/profile ディレクトリで起動し、generation ready でなければ1 token 検証を要求します。【`strata_control/updater.py:852-884`】

この値が使われるのはエンジンのテスト起動です。`--check` は feed の確認結果を返して終了し、テスト起動を呼びません。また、`--no-engine` でエンジン更新を無効にした場合や `strata components rollback` の場合も、指定値はテスト起動に使われません（rollback 分岐は `run_update()` より前に処理されます）。【`strata_cli/update_cmd.py:185-209`, `strata_cli/update_cmd.py:210-224`】

## 適用条件と副作用

- 新しいエンジンパッケージを実際にインストールする経路でのみ、テスト起動の config として適用されます。既に最新などの理由でエンジン更新が不要ならテスト起動はありません。【`strata_control/updater.py:930-937`】
- テスト起動は一時的なサーバープロセスを起動し、モデルを読み込んで1 token を生成します。設定上のモデルファイルや実行条件に問題があれば更新は失敗し得ます。試験ログは component の `.updates/logs/test-start-<version>.log` に保持され、テスト用 sandbox は終了時に削除されます。【`strata_control/updater.py:825-839`, `strata_control/updater.py:852-896`】
- `--check` は feed を読むだけで、指定モデル設定を使いません。`--model-config` は feed や設定ファイルから自動補完される値ではありません。【`strata_cli/update_cmd.py:87-95`, `strata_cli/update_cmd.py:197-209`】

## 出力とエラー

テスト起動が失敗すると exit code 6 の更新エラーとなり、新エンジンは切り替えられず、既存エンジンが維持されます。失敗理由は人向けでは stderr の `strata: ...`、`--output json` / `jsonl` では JSON の error として出力されます。無効 JSON、読み取り不能、run config の必須項目不足などはテスト起動失敗として扱われます。【`strata_control/updater.py:79-123`, `strata_control/updater.py:852-889`, `strata_cli/update_cmd.py:163-172`, `strata_cli/update_cmd.py:225-234`】

## 根拠

- parser と既定値: `strata_cli/update_cmd.py:30-59`
- 値の Context への引き渡し、rollback / check の分岐、エラー出力: `strata_cli/update_cmd.py:163-234`
- 既定 config の探索: `strata_control/updater.py:701-717`
- テスト起動での config 使用、sandbox と上書き項目: `strata_control/updater.py:842-896`
- run config の検証: `strata_control/profiles.py:135-147`
- テスト失敗時のエンジン更新処理: `strata_control/updater.py:930-1027`

調査は上記 commit の checkout 内ソースに限定しました。CLI `--help` や Release 配布物との照合は行っていません。
