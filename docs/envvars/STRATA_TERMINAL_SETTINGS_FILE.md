# `STRATA_TERMINAL_SETTINGS_FILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されていなかった。外部ライブラリの環境変数は対象外。

## 役割

Strata デスクトップアプリが、Terminal（コマンドライン Strata）の `settings.json` の場所を決めるために使います。ここで同期されるのはモデルのデータフォルダー設定です。変数自体が Terminal やモデル実行エンジンに渡される処理は確認できません。

本番コードでの名前の参照・環境値の読み取りは `apps/host/server/model-folder.mjs:68-72` のみです。呼び出し元は `apps/host/server/native-control.mjs:96` です。`apps/host/server/native-control.mjs:53` の `packaged = !!control` が真でないソース checkout モードでは同期処理が直ちに戻るため、この変数は使われません。

この変数だけではコマンドライン側が読む設定ファイルの場所は変わりません。`setup.py` と `strata_control/discovery.py` は `STRATA_SETTINGS_FILE` があればそれを使い、なければ `APPDATA` / `XDG_CONFIG_HOME` に基づく既定パスを使います。`STRATA_TERMINAL_SETTINGS_FILE` はそれらの読み取り箇所にはありません（`setup.py:6238-6248`; `strata_control/discovery.py:123-131`）。したがって、この変数に既定場所以外を指定するとデスクトップ側の同期先だけが変わり、コマンドライン側が自動で同じファイルを使うことはありません。

## 値と判定

| 状態 | 選ばれる設定ファイルのパス |
|---|---|
| `STRATA_TERMINAL_SETTINGS_FILE` が空でない | 値をそのまま使用 |
| 未設定または空文字 | Windows (`win32`) では `APPDATA/Strata/settings.json`。`APPDATA` が空または未設定なら `<home>/AppData/Roaming/Strata/settings.json` |
| 未設定または空文字、Windows 以外 | `XDG_CONFIG_HOME/strata/settings.json`。`XDG_CONFIG_HOME` が空または未設定なら `<home>/.config/strata/settings.json` |

判定は JavaScript の `if (env.STRATA_TERMINAL_SETTINGS_FILE)` です。値を trim、parse、絶対パス化する処理はなく、空文字は既定パスを選びます。空白だけの値など truthy な値はそのままファイルパスとして使われます。パスの存在や有効性はこの関数では検証されません。既定パス側の `APPDATA` と `XDG_CONFIG_HOME` も truthiness で選択されます。根拠: `apps/host/server/model-folder.mjs:68-72`。

## 有効になる条件

- `createNativeControl` が packaged モードで作られていること（`control` が truthy）。ソース checkout モードでは `shareDataFolder()` が何もしません（`apps/host/server/native-control.mjs:50-53,96`）。
- packaged アプリでモデルのダウンロード先フォルダーを設定する経路が実行されること。公開 API `POST /api/native/directory` が設定処理を呼び（`apps/host/server/index.mjs:999`）、インストール完了時にも同じ処理を呼びます（`apps/host/server/native-control.mjs:555`）。

環境値は `terminalSettingsFile()` の呼び出し時に `process.env` から取得されます。モジュール読み込み時の固定値やキャッシュはなく、プロセス内で環境値を変更した場合は次の同期呼び出しで再評価されます。ただし実運用での呼び出しはフォルダー設定時です（`apps/host/server/native-control.mjs:96,147`）。

## 実行時の詳細

フォルダー設定時、packaged モードではまず Strata Control 側の設定ファイルに選択フォルダーと変更時刻を記録し、その後 `shareDataFolder()` が `terminalSettingsFile()` で得たパスと同期します（`apps/host/server/native-control.mjs:94-96,147`）。同期処理は両ファイルの `data_dir` と時刻を比べ、端末側の有効なフォルダー設定の方が新しければアプリ側へ採用し、それ以外では必要に応じて端末側の設定を更新します。フォルダーが存在しない端末側の値は採用せず、アプリ側の設定があれば端末側へ戻そうとします（`apps/host/server/model-folder.mjs:57-64,74-86,89-111`）。

対象ファイルは JSON として読まれ、読み取り不能・不正 JSON・トップレベルが配列などの場合は空設定として扱われます。`data_dir` が空文字または文字列以外ならフォルダー指定なしです。`data_dir_at` が有限な正数でなければ、ファイル更新時刻を秒単位で代用し、それも取得できなければ 0 とします（`apps/host/server/model-folder.mjs:53-64`）。

明示パスが存在しない、読み取り不能、または書き込み不能でも、環境変数についての警告やエラーは出ません。設定読み込みは空設定にフォールバックし、書き込み処理は `false` を返して失敗を隠します。また `shareDataFolder()` 自体も例外を catch して何も出さず、アプリを止めない仕様です（`apps/host/server/model-folder.mjs:53-55,76-87`; `apps/host/server/native-control.mjs:96`）。このため、同期に失敗した場合に観測できる専用ログ、終了、またはエラー応答はありません。

## 根拠

- 環境値と OS 別既定値の選択: `apps/host/server/model-folder.mjs:67-72`
- 設定ファイルの読み取り・更新、`data_dir` と時刻の判定: `apps/host/server/model-folder.mjs:53-64,74-111`
- コマンドライン側の設定ファイル選択（対象変数は参照せず `STRATA_SETTINGS_FILE` と OS 既定値を使う）: `setup.py:6238-6248`; `strata_control/discovery.py:123-131`
- packaged 判定、同期呼び出し、例外の扱い: `apps/host/server/native-control.mjs:50-53,93-96`
- 選択したモデルフォルダーの保存と同期呼び出し: `apps/host/server/native-control.mjs:147,538,555`; HTTP API: `apps/host/server/index.mjs:999`
