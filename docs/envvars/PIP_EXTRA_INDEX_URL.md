# `PIP_EXTRA_INDEX_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の実行時機能を制御する設定ではありません。同梱 Terminal の依存 wheel をビルド時に導入する `packaging/package_terminal.py` は、呼び出し元の環境から子プロセス用の環境辞書を作った後、`PIP_EXTRA_INDEX_URL` を必ず削除します。その辞書で起動する pip の subprocess にこの変数を引き継がないための処理です（`packaging/package_terminal.py:199-210`）。

## 値と判定

Strata は値を文字列として読み取ったり parse したりしません。`dict(os.environ)` による環境の複製後、キー名を指定して `env.pop(name, None)` を実行します（`packaging/package_terminal.py:203-206`）。

| 呼び出し元での状態 | Strata の処理 |
|---|---|
| 未設定 | `pop(..., None)` がキー不在のまま終了する。 |
| 空文字 | 値を検査せずキーごと削除する。 |
| その他の値（無効な文字列を含む） | 値を検査・変換せずキーごと削除する。 |

値の境界、無効値時の fallback はありません。`env` の他の項目は継承されますが、同じ処理で `PYTHONHOME`、`PYTHONPATH`、`PIP_REQUIRE_VIRTUALENV`、`PIP_INDEX_URL` も削除されます。また、`PIP_NO_INPUT=1`、`PIP_DISABLE_PIP_VERSION_CHECK=1`、`PYTHONNOUSERSITE=1`、`PIP_CONFIG_FILE=os.devnull` はこの辞書に設定されます（同:203-206）。

## 有効になる条件

- `packaging/package_terminal.py` の依存導入処理で有効です。`main()` は `--skip-deps` が指定されていない場合に `install_locked()` を呼びます。`--skip-deps` ではこの変数の削除も pip の依存導入も行いません（`packaging/package_terminal.py:424-429`）。
- 依存を導入する通常のビルドでは、対象プラットフォーム上でビルドする条件があります。対象と現在の host が異なると、`--skip-deps` がない場合は `SystemExit` になります（`packaging/package_terminal.py:359-362`）。
- `--wheelhouse` の有無で変数の削除は変わりません。指定時は wheelhouse を pip install の引数に加え、未指定時は加えません（`packaging/package_terminal.py:205-210,355-356,428`）。
- アーカイブの利用時ではなく、同梱 Python への依存導入を行うビルド時の処理です（`packaging/package_terminal.py:2-7,199-210`）。

## 実行時の詳細

`install_locked()` の呼び出しごとに現在の `os.environ` を辞書へ複製し、上記のキーを除去します。静的キャッシュはなく、その呼び出し時点の環境が使われます。作った辞書は `pip install`、続く `pip check`、`pip list` の各 subprocess に渡されます。最初の二つは `check=True` で起動されるため、非ゼロ終了なら `subprocess.run` が例外を送出して後続処理へ進みません。インストール開始前には `installing the locked runtime wheels into the bundled interpreter (build time only)` が標準出力へ表示されます（`packaging/package_terminal.py:207-213,424-429`）。

ここで確認できる Strata の動作は、ビルド用 subprocess の環境からこのキーを取り除くことです。pip の index 選択やネットワーク動作については本書では扱いません。

## 根拠

- `packaging/package_terminal.py:199-210` — 環境辞書の作成、対象キーの削除、pip install への環境引き渡し。
- `packaging/package_terminal.py:211-213` — 後続の pip subprocess にも同じ辞書を渡す。
- `packaging/package_terminal.py:339-362,424-429` — CLI 条件、対象 platform の制約、`--skip-deps` と helper 呼び出し。
- `packaging/package_terminal.py:2-7` — スクリプトが Terminal の自己完結配布物をビルドする用途であること。
