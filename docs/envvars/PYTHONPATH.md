# `PYTHONPATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部 Python 実行環境の `PYTHONPATH` の意味・import 動作は対象外。

## 役割

Strata の本番コードには、`PYTHONPATH` を Strata 自身の設定値として読み、値に応じて機能を選ぶ処理は見当たりません。参照の大半は、同梱 Python や Control の起動時にこの変数を子プロセス環境から除く処理です。一方、モデル準備の子プロセスには、継承値を除去した後で Strata ソースディレクトリを明示的に設定します。また Linux AppImage から外部プログラムを起動するときは、AppImage 内のパスを含む `PYTHONPATH` を外部向け環境から除去します。

## 値と判定

`PYTHONPATH` 自体を真偽値や数値へ変換する Strata の読み取り箇所はありません。挙動は起動経路ごとに次のとおりです。

CLI 引数による `PYTHONPATH` 設定や優先順位はありません。Strata の Python/シェル側の処理は子プロセス用辞書または起動直前の環境を作る時点で行われ、変数値の static cache はありません。AppImage helper も外部プログラム向け環境を作る呼び出し時に渡された環境（既定では `process.env`）をコピーして処理し、親プロセスの環境自体は書き換えません。

| 経路 | 未設定・空文字 | 設定値 | 判定・変換 |
|---|---|---|---|
| バンドル Python の起動 | どちらも子プロセス環境から除去 | 値を問わず除去 | 値を parse せず `unset`、`Remove-Item`、`env_remove`、または `pop` |
| `strata launch` のモデル準備 | いったん環境から除去 | 継承値を使わない | 最後に `PYTHONPATH` を `cat.src` の文字列表現で上書き |
| Linux AppImage の外部プログラム向け環境 | 元環境の記録があれば記録値を使う。記録がなく `APPDIR` があれば空値は空要素として除かれ、結果の変数も削除 | `APPDIR` があり元環境記録がなければ、コロン区切り要素のうち `APPDIR` 内を指すものだけ除去。それ以外は維持 | `split(':')` 後に空要素と AppImage 内パスを filter。アプリ起動時の環境記録があればその値を復元 |
| その他の起動・環境継承 | その経路の親環境に従う | 原則としてその経路の親環境に従う | `PYTHONPATH` を設定として検査する分岐なし |

AppImage のパス処理は、パス文字列全体の正規化や Python の import 解決ではありません。`APPDIR` がない場合、`PYTHONPATH` の要素から AppImage 内のパスを除く処理は行われません。元環境記録があるときは、記録中の環境を優先して使い、`withoutAppImage` による要素除去は行いません（`apps/host/server/external-env.mjs:28-40,43-57,67-70`）。

## 有効になる条件

- `bin/strata` は、選択した Python が配布物内の `python/` 以下にある場合に限り `PYTHONHOME` と `PYTHONPATH` を除去します。通常のシステム Python や `STRATA_PYTHON` を選んだ場合、このラッパーは `PYTHONPATH` を変更しません（`bin/strata:31-49,128-133`）。
- `bin/strata.ps1`、`bin/strata.cmd`、`setup.sh`、`START-HERE.bat` も、バンドル Python を使う分岐だけで `PYTHONPATH` を空にします。Windows の `.cmd` とバッチでは `set "PYTHONPATH="`、PowerShell では環境項目の削除、シェルでは `unset` です（`bin/strata.ps1:25-42`、`bin/strata.cmd:29-43`、`setup.sh:7-12`、`START-HERE.bat:9-13,44-54`）。
- アプリがバンドル Control を起動・検査する経路では、継承環境から `PYTHONPATH` を除きます。これは desktop の Control 検査とエンジン不在確認、host の `controlEnvironment()`、Control handover、MCP の Control インストールで行われます（`apps/desktop/src-tauri/src/main.rs:625-653`、`apps/host/server/control-runtime.mjs:88-100`、`strata_cli/handover.py:117-123,148-158`、`tools/strata_mcp.py:2841-2852`）。
- `strata launch` がモデル準備のため `setup.py` を起動するときは、`ensure_model()` 内で継承環境の `PYTHONPATH` を除いた後、`cat.src` を設定します。したがってこの子プロセスでは、ユーザーの値ではなく対象ソースディレクトリが渡されます（`strata_cli/launch/runner.py:674-685,1119-1153`）。同じファイルのエンジン更新子プロセスは通常 `_env()` を使い、`PYTHONPATH` の削除・上書きはしていません（`strata_cli/launch/runner.py:674-679,739-748`）。
- `packaging/package_terminal.py` はビルド時に、バンドル依存をインストールする pip とバンドル Python の probe の環境から継承 `PYTHONPATH` を除きます（`packaging/package_terminal.py:199-211,434-440`）。これはパッケージ作成処理の環境清掃で、配布後の利用者向け設定ではありません。
- `apps/host/server/external-env.mjs` は、AppImage が起動したホストプロセスから外部プログラム用環境を組み立てます。元環境の記録がなければ `APPDIR` 配下のパス要素を削り、記録があれば記録値を使います。この環境をフォルダ選択、通知、ファイルを開く処理などが利用します（同 `:2-13,25-26,64-70`; 呼び出し例 `apps/host/server/folder-dialog.mjs:111,146`、`apps/host/server/app-ui.mjs:38,56`、`apps/host/server/artifacts.mjs:6`）。AppImage の起動条件外では、`externalEnvironment()` は受け取った環境をコピーしてそのまま返します（同 `:64-70`）。

## 実行時の詳細

通常の端末起動では、`bin/strata` は `STRATA_PYTHON`、バンドル Python、PATH 上の Python 等から実行ファイルを選びますが、`PYTHONPATH` は選択基準にしません。バンドル Python を選んだ場合にだけ、`strata.py` を実行する直前に親プロセス環境から `PYTHONPATH` を除去します。Windows と初回セットアップ用ラッパーも同様に、バンドル版を直接起動する分岐だけが対象です（`bin/strata:31-49,128-133`、`START-HERE.bat:11-13,44-54`、`bin/strata.ps1:28-42`、`bin/strata.cmd:29-43`）。値が無効という理由で警告・終了する処理は確認できません。

`strata_cli/handover.py` は `strata.py` の冒頭から呼ばれます。新しい Control への handover が行われるとき、その子環境を複製して `PYTHONPATH` を削除します。hand-over をしない場合に、この関数が現在のプロセス環境を変更することはありません（`strata.py:32-36`、`strata_cli/handover.py:117-123,126-158`）。

`strata launch` のモデル準備では、子環境を `os.environ` から作り、`PYTHONHOME`、`PYTHONPATH`、`VIRTUAL_ENV` を取り除き、`PYTHONPATH=cat.src` を設定して `setup.py` を起動します。子プロセスの出力は runner が読み取りますが、`PYTHONPATH` の値に起因する専用ログ、警告、終了コード分岐はありません（`strata_cli/launch/runner.py:1119-1153,1158-1178`）。

## 根拠

- 環境参照を行う汎用 AppImage helper と外部起動への適用: `apps/host/server/external-env.mjs:25-40,43-57,64-70`。
- バンドル Python ランチャーと初回セットアップ: `bin/strata:31-49,128-133`、`bin/strata.ps1:28-42`、`bin/strata.cmd:29-43`、`setup.sh:7-12`、`START-HERE.bat:9-13,44-54`。
- 子プロセスからの除去・上書き: `strata_cli/handover.py:117-123,126-158`、`strata_cli/launch/runner.py:674-685,1119-1153`、`tools/strata_mcp.py:2841-2852`、`apps/desktop/src-tauri/src/main.rs:625-653`、`apps/host/server/control-runtime.mjs:88-100`。
- パッケージ作成時の環境清掃: `packaging/package_terminal.py:199-211,434-440`。
