# `PIP_REQUIRE_VIRTUALENV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata の通常実行時にこの変数を読む処理は見つかりませんでした。Strata がこの名前を使うのは、Terminal 配布物の依存 wheel をビルド時にインストールする `packaging/package_terminal.py` です。親プロセスの環境をコピーした後、このキーを子プロセス用環境から削除し、同梱 Python で起動する pip の `install` と `check` に渡しません。したがって、ここでの Strata の動作は値による設定ではなく、ビルド時の環境変数の除去です。

## 値と判定

値の文字列・数値への変換や真偽判定はありません。`os.environ` のスナップショットを作り、キー名 `PIP_REQUIRE_VIRTUALENV` を `pop` しています。

| 呼び出し時の状態 | 子プロセス用環境での扱い |
|---|---|
| 未設定 | `pop` は何もせず、未設定のまま |
| 空文字、`0`、`1`、その他の文字列 | 値を問わずキーを削除 |

他の環境変数や CLI 引数との値の優先順位はありません。`install_locked()` の呼び出し自体が `--skip-deps` によって省かれる場合、この処理も行われません（`packaging/package_terminal.py:424-429`）。

## 有効になる条件

この処理は `packaging/package_terminal.py` が Terminal アーカイブを依存付きで作成するときだけ実行されます。スクリプトの説明では対象は Windows x64、Linux x86_64 / aarch64、macOS arm64 で、対象 OS 上でのビルドが必要とされています（`packaging/package_terminal.py:2,32-39`）。`--skip-deps` を指定すると依存導入を飛ばすため、この変数の除去もありません。

エンジン実行、サーバー起動、通常の CLI 起動でこの変数を参照・変更する Strata の箇所は、候補名の全参照検索では確認できませんでした。

## 実行時の詳細

`install_locked()` は関数呼び出し時点の `os.environ` を辞書にコピーし、`PIP_NO_INPUT=1`、`PIP_DISABLE_PIP_VERSION_CHECK=1`、`PYTHONNOUSERSITE=1`、`PIP_CONFIG_FILE=os.devnull` を設定します。その後、`PYTHONHOME`、`PYTHONPATH`、`PIP_REQUIRE_VIRTUALENV`、`PIP_INDEX_URL`、`PIP_EXTRA_INDEX_URL` を値に関係なく除きます。作られた辞書は同梱 Python による pip の `install` と `check` の `subprocess.run()` に渡されます（`packaging/package_terminal.py:199-211`）。

環境のコピーは `install_locked()` の呼び出し時に一度行われます。コピー後の親環境の変更はこの辞書に反映されません。pip 呼び出しは `check=True` なので、コマンドが失敗すれば `subprocess.run()` が例外を送出し、パッケージ作成処理はその先へ進みません。Strata 独自の `PIP_REQUIRE_VIRTUALENV` 警告や値別のエラー処理はありません（同 `:208-213`）。

## 根拠

- 候補一覧には名前があります（`docs/envvars/000_envvers.md:499`）。完全一致のソース参照は `packaging/package_terminal.py:205` のみで、値を読むのではなく子プロセス用環境からキーを削除しています。
- 同梱 CPython / pip のビルド時導入であることと、対象 platform: `packaging/package_terminal.py:2-7,32-39`。
- 環境辞書の作成、対象キーの削除、pip への引き渡し: `packaging/package_terminal.py:199-213`。
- `--skip-deps` による呼び出し条件: `packaging/package_terminal.py:424-429`。
