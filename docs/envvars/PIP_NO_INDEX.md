# `PIP_NO_INDEX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata サーバーは、strict offline モードで起動したとき、エンジンなどの子プロセスへ渡す環境に `PIP_NO_INDEX=1` を設定します。Strata 自身は親プロセスの `PIP_NO_INDEX` を読み取って分岐せず、値の意味を解釈もしません。これは Strata が子プロセス環境へ設定・転送する変数です。

## 値と判定

Strata による入力値の parse はありません。未設定、空文字、その他の値を Strata が判定する箇所は見つかりませんでした。`strata_control/offline.py` の `OFFLINE_ENV` 辞書に値が文字列 `"1"` として固定されています（`strata_control/offline.py:44-61`）。

サーバーの `child_env()` は親環境をコピーし、設定ファイルの `env` を反映した後、`offline=True` の場合にこの辞書を最後に適用します。そのため、親環境やプロファイルに別の `PIP_NO_INDEX` 値があっても、通常の offline 経路では子プロセス向けの値は `"1"` になります（`serve/server.py:3747-3771`）。

`offline=False` の `serve.server.child_env()` はこのキーを削除も上書きもしません。従って親環境からコピーされた値、または設定ファイルの `env` による値が子環境に残ります。別の `strata_control.offline.child_environment()` helper は offline でない場合に `OFFLINE_ENV` のキーを削除する実装ですが、調査対象内に本番コードからの呼び出しはありません。サーバー本体は `serve.server.child_env()` を使います（`strata_control/offline.py:122-136`、`serve/server.py:9191-9194`）。

## 有効になる条件

- `serve/server.py` の `--offline` CLI フラグが指定されることが条件です。`PIP_NO_INDEX` 自体を CLI 引数や別の環境変数から選ぶ機能はありません（`serve/server.py:9000-9001,9175-9194`）。
- offline モードでは設定済み MCP サーバー、`before_load` コマンド、またはプロファイルが許可するリモート画像ソースがあると、サーバーは起動前に拒否します（`serve/server.py:9172-9184`; 判定対象は `strata_control/offline.py:139-166`）。
- 単一エンジン、replica、split serve のいずれの起動経路でも、子エンジンの環境作成に `offline` 状態が渡されます（`serve/server.py:8704-8711,8768-8777,9273-9279`）。OS、GPU backend、モデル状態による `PIP_NO_INDEX` 固有の分岐はありません。
- offline policy module の import が失敗する例外経路では、`child_env()` は `STRATA_OFFLINE`、`HF_HUB_OFFLINE`、`TRANSFORMERS_OFFLINE` のみ設定し、`PIP_NO_INDEX` は設定しません（`serve/server.py:3768-3777`）。

## 実行時の詳細

`--offline` は `argparse` がサーバー起動時に読み、設定値は `child_env()` の呼び出しごとに子環境へ反映されます。`PIP_NO_INDEX` の親環境値を読む処理や、その値を cache する処理はありません。`--offline` の有効時には、エンジンの初回起動、replica、split serve の各子起動へ生成した環境が渡されます（`serve/server.py:3747-3771,8704-8711,8768-8777,9191-9194,9273-9279`）。

`--offline` による起動前拒否は argparse のエラー経路で、メッセージに理由を含めます（`serve/server.py:9173-9184`）。`PIP_NO_INDEX` の値を個別にログ出力、警告、終了コードへ結び付ける処理は見つかりませんでした。offline 時の子環境への設定は、`docs/work/IMPLEMENTATION_STATUS.md:849-858` にも記載されており、実装の方針と一致します。

## 根拠

- 候補名のコード全体検索で、実装上の設定箇所は `strata_control/offline.py:52`、サーバーからの適用箇所は `serve/server.py:3768-3771` でした。`strata_control/offline.py:122-136` に別の子環境 helper がありますが、本番コードの呼び出しはありません。
- `tests/tuning/test_offline.py:72-80` は helper が offline 時に `PIP_NO_INDEX` を `"1"` にすることを確認し、`packaging/smoke_terminal.py:78-81` はテスト用環境に同値を設定しています。これらはテスト・診断コードであり、独立した実行時の読み取り箇所ではありません。
- `packaging/acceptance_matrix.py:397` と `docs/work/ACCEPTANCE-EVIDENCE.md:103` にも strict offline の子環境変数として名前が記載されています。いずれも説明資料であり、動作の根拠は上記の実装箇所です。
