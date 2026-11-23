# `PYTHONPATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `PYTHONPATH` を設定値として読み解かず、実行経路ごとにプロセス環境から削除するか、子プロセス向けの値を明示的に設定する。システム Python やユーザー指定 Python を選んだ通常の Terminal 起動では、この変数を Strata の起動スクリプト自身が変更する処理はない。実装はセットアップ用シェル／バッチ、Terminal ランチャー、Control の子プロセス起動、AppImage の外部プログラム用環境に分かれる（`setup.sh:12-17`, `terminal/bin/strata:142-145`, `terminal/strata_cli/launch/runner.py:1650-1661`, `app/host/server/external-env.mjs:25-26,43-55,64-70`）。

## 値と判定

Strata の実行時コードに、`PYTHONPATH` の値をパースして真偽値や設定値にする箇所はない。空文字・数値・区切り文字・大文字小文字を判定しない。対象経路では環境変数の有無に関係なく削除し、Control のモデル準備では固定の `cat.src` に置き換える。AppImage の外部プログラム用処理だけは、文字列を `:` で分割して AppImage 内の要素を除く（`terminal/strata_cli/launch/runner.py:1658-1661`, `app/host/server/external-env.mjs:25-26,47-55`）。

| 条件 | unset | 設定値の扱い | Strata 側の判定 |
|---|---|---|---|
| Linux/macOS セットアップで `terminal/python/bin/python3` がある | 変更なし | 値を問わず `unset` してから同梱 Python で `setup.py` を実行 | 削除 |
| Windows `START-HERE.bat` の bundled 分岐 | 変更なし | 値を問わず空にする | 削除 |
| Terminal Unix ランチャーで `$PY` が `$HERE/../python/*` または `$HERE/python/*` に一致 | 変更なし | 値を問わず `unset` | 削除 |
| Terminal Windows `.cmd` / `.ps1` の bundled 分岐 | 変更なし | 値を問わず空にする／環境から削除 | 削除 |
| Control がセットアップを起動 | 値を問わず、子環境に `cat.src` を設定 | ユーザー値を除去した後に上書き | ソースディレクトリで上書き |
| Control が pack 準備を起動 | 値を問わず、子環境に `cat.src` を設定 | ユーザー値を除去した後に上書き | ソースディレクトリで上書き |
| AppImage 内から Strata が外部プログラムを起動 | 元環境の記録があれば記録値をそのまま使う。記録がなければ現在値を対象にする | 元環境の記録がない場合だけ、空要素と `APPDIR` 配下の要素を除去し、残りがなければ変数自体を削除 | 記録なしの場合に条件付きのパス要素除去 |
| 上記以外の経路（例: ソース checkout の server 起動環境） | 通常の環境をコピー | `PYTHONPATH` はそのままコピー | 対象名による変更なし |

（根拠: `START-HERE.bat:49-55`, `terminal/bin/strata:142-145`, `terminal/bin/strata.cmd:34-43`, `terminal/bin/strata-direct.ps1:30-41`, `terminal/strata_cli/launch/runner.py:1650-1661,1798-1805`, `app/host/server/control-runtime.mjs:82-95`, `app/host/server/external-env.mjs:25-26,43-55,64-70`, `app/host/server/native-control.mjs:689`。）

## 有効になる条件

- Terminal Unix ランチャーで削除されるのは、選ばれた `$PY` のパスがランチャー同梱の Python ディレクトリに一致する場合だけ。ソースではこの条件を外れた Python では `PYTHONPATH` を消していない（`terminal/bin/strata:142-145`）。
- Windows の `.cmd` / `.ps1` は bundled Python 分岐で削除する。`.cmd` の `%STRATA_PYTHON%` を使う分岐は bundled 分岐を通らない（`terminal/bin/strata.cmd:29-43`, `terminal/bin/strata-direct.ps1:30-45`）。
- Control のセットアップ・pack 準備では、入力環境に値があっても `cat.src` で置き換わる。Control を実行しない経路にはこの上書きは適用されない（`terminal/strata_cli/launch/runner.py:1650-1661,1798-1805`）。
- AppImage 外部プログラム用の処理は `APPDIR` または記録環境があるときだけ環境の復元・掃除を行う。記録環境があればその `PYTHONPATH` をそのまま採用する。記録がない場合は `:` 区切りとし、空要素、および `APPDIR` に一致するか `APPDIR/` または `APPDIR//` で始まる要素を除去する。Windows の `;` 区切り等を解釈するコードではない（`app/host/server/external-env.mjs:43-55,60-70`）。
- `sourceServerEnvironment()` は環境を複製して Python 関連変数を変更しない。Control の `controlEnvironment()` は `PYTHONPATH` を含むユーザー Python 環境変数を削除する（`app/host/server/control-runtime.mjs:82-95`）。

## 実行時の詳細

この変数専用の cache や数値変換はない。セットアップ／ランチャーでは子プロセス起動前に環境変数を変更し、その子プロセスにだけ影響する。Control のモデル準備と pack 準備は `_env()` の環境から `PYTHONHOME`・`PYTHONPATH`・`VIRTUAL_ENV` を除去し、`PYTHONPATH=cat.src` を設定して `setup.py` を起動する（`terminal/strata_cli/launch/runner.py:1650-1661,1798-1805`）。Control の引き継ぎでは `_child_env()` が `PYTHONPATH` を除去する（`terminal/strata_cli/handover.py:117-123`）。MCP 経由の Control install も同名変数を子環境から除去するが、値を再設定しない（`terminal/tools/strata_mcp.py:3151-3162`）。

パッケージ作成ツールは、bundled Python の import probe と pip インストールの子プロセス環境からこの変数を除去する（`tools/packaging/package_terminal.py:146-156,218-229`）。アプリの Control 実行環境でも削除し、Desktop self-test の `strata.py` 起動でも削除する（`app/host/server/control-runtime.mjs:88-95`, `app/desktop/src-tauri/src/main.rs:688-716`）。これらの処理は変数値を読み取って保持・キャッシュするものではない。

## ログと測定値

`PYTHONPATH` の値や有無だけを理由に Strata が出すログ、警告、終了コードは確認できない。該当コードは環境を削除・上書きするだけで、変数専用の失敗経路を持たない。

## 根拠

- `setup.sh:12-17`, `START-HERE.bat:49-55`: bundled Python のセットアップ起動前に削除。
- `terminal/bin/strata:142-145`, `terminal/bin/strata.cmd:29-43`, `terminal/bin/strata-direct.ps1:30-45`: Terminal ランチャーの bundled 分岐とその条件。
- `terminal/strata_cli/launch/runner.py:1650-1661,1798-1805`: Control の子プロセスでソースパスに設定。
- `terminal/strata_cli/handover.py:117-123`, `terminal/tools/strata_mcp.py:3151-3162`: Control handover / MCP install 環境からの除去。
- `tools/packaging/package_terminal.py:146-156,218-229`: パッケージ作成時の子プロセスからの除去。
- `app/host/server/control-runtime.mjs:82-95`, `app/desktop/src-tauri/src/main.rs:688-716`: アプリの server / Control / self-test 環境。
- `app/host/server/external-env.mjs:25-26,43-55,60-70`, `app/host/server/native-control.mjs:689`: AppImage の外部環境掃除とソース server 環境の呼び出し。

