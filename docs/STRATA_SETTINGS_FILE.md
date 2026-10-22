# `STRATA_SETTINGS_FILE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata の Python setup、Control discovery、MCP installer が使う設定 JSON ファイルのパスを指定します。主な用途はデスクトップアプリの専用 `app-settings.json` を指定し、アプリがコマンドライン版 Strata のユーザー設定（保存済み install 一覧など）を誤って採用しないようにすることです。Strata engine の推論設定を直接変える環境変数ではありません。

## 値と判定

値は文字列としてパスに渡され、数値や真偽値への parse はありません。Python 側では `os.environ.get(...)` の結果が truthy かを判定し、truthy なら `Path(raw)` をそのまま使います。空文字と未設定は同じく専用パスなしとして扱われます。空白だけの文字列は truthy なので、その文字列が指すパスを使います。絶対パス検査、`~` の展開、正規化はこの変数の読み取り箇所では行われません。

| 状態 | setup / discovery / MCP installer の選択 |
|---|---|
| 未設定または空文字 | 通常のユーザー設定ファイルへ fallback。Windows は `%APPDATA%/Strata/settings.json`（`APPDATA` も未設定/空なら `~/AppData/Roaming/Strata/settings.json`）、それ以外は `$XDG_CONFIG_HOME/strata/settings.json`（`XDG_CONFIG_HOME` も未設定/空なら `~/.config/strata/settings.json`）。 |
| 空でない値 | 指定文字列をそのまま設定ファイルのパスとして使用。 |

指定先が存在しない、読めない、または有効な JSON でない場合、setup の `load_settings()` は空の設定 `{}` を返します。Control discovery の JSON 読み込みも失敗時は空データとして扱います。setup が設定を保存するときは親ディレクトリを作成してから JSON を書き、失敗時は `could not save ...` 警告を出します。

## 有効になる条件

- `setup.py` の設定読み書き、`strata_control.discovery` の install/data-folder 探索、`strata_control.models` の保存済み install 読み出し、`tools/strata_mcp.py` のデータフォルダー取得で参照されます。
- 設定値が truthy のプロセスは `in_app_mode` と判定されます。install 探索ではその設定ファイルに記録された install とアプリの install を使い、別のアプリ設定ファイルにある旧 install 一覧を追加で探索しません。データフォルダーの同期はアプリ内プロセスでは行わず、データフォルダー候補からも別のアプリ設定ファイルと Documents 候補を除外します。
- デスクトップアプリの `controlEnvironment()` は、components の場所が決まっている場合、継承環境に空でない `STRATA_SETTINGS_FILE` があればそれを保ち、そうでなければ components の親にある `app-settings.json` を子プロセス用環境に設定します。Control の installer 環境もこの環境を引き継ぎます。components がない場合はこのコードによる上書きはありません。

## 実行時の詳細

Python の各関数は呼び出し時に `os.environ` を参照し、値をモジュール初期化時の static cache に保存しません。したがって、同一プロセスで環境辞書が変更されれば、その後の関数呼び出しでは新しい値が使われます。アプリホストは Control/installer を起動する際に環境を複製・補正して渡します。MCP installer は選ばれた設定ファイルから `data_dir` を読み、値がなければ `<Strata repo の親>/Strata-data` を返します。

設定ファイルは用途別に読み書きされます。setup はファイル全体を JSON として読み書きします。Control discovery は install 一覧や `data_dir` を探索し、必要なデータフォルダー同期では更新時刻を比較して古い側のファイルへ値を書き戻します。MCP installer は `data_dir` の読み取りを使って Strata repo とデータフォルダーを許可ルートにします。

## 根拠

- `setup.py:5728-5758` — truthy 判定、通常設定パスの fallback、設定 JSON の読込・保存と保存失敗時の警告。
- `strata_control/discovery.py:54-61,123-131,160-175,238-270` — app mode 判定、設定パス、install 探索とデータフォルダー同期・候補の制御。
- `strata_control/models.py:42-52` — discovery の設定ファイルから保存済み install を読み込む経路。
- `tools/strata_mcp.py:572-588` — MCP installer の設定パス、`data_dir` 読み取り、fallback と許可ルート。
- `apps/host/server/control-runtime.mjs:77-100` — Control/installer 子プロセスへ渡す環境と既定のアプリ専用設定ファイル。
- `apps/host/server/native-control.mjs:78-81` — ホスト側が同じ app 設定ファイルを参照し、アプリと Terminal の data folder を同期する箇所。
- `docs/DETAILS.md:543-544,2266` — 通常のユーザー設定ファイルと `data_dir` の説明。デスクトップアプリ専用ファイルとの分離は上記の現行コードを根拠とした。
