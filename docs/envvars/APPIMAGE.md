# `APPIMAGE`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`APPIMAGE` は推論エンジンの設定ではありません。Linux デスクトップでは、診断ログに現在の値を記録し、ユーザー向けの `--quit` / `--save-logs` 案内で実行ファイル名を組み立てます。AppImage 内のホストでは、システムのファイル選択・通知・ブラウザー等を起動するとき、AppImage 用の環境を外部プログラムへそのまま渡さないための判定にも使われます。

## 値と判定

| 読み取り箇所 | 未設定 | 設定時の扱い |
|---|---|---|
| Linux デスクトップの `command_name()` | `current_exe()` のファイル名を使い、それも得られなければ `strata-desktop` | Unicode 文字列として取得でき、パスにファイル名があれば `./<ファイル名>` を返す。値全体の比較や拡張子検査はしない。空文字や末尾が `/` の値など、ファイル名を取り出せない場合は未設定時と同じ fallback。非 Unicode 値も `std::env::var` が `Err` となり fallback。 |
| デスクトップ診断ログ | 記録されない | Unicode 文字列として取得できた場合、`APPIMAGE=<値>` の行を記録する。空文字は `APPIMAGE=` として記録される。非 Unicode 値は省かれる。 |
| ホストの `insideAppImage(env)` | `APPDIR` も falsy なら外部プログラム用の環境を変換しない | JavaScript の真偽値判定で `env.APPIMAGE` が truthy なら AppImage 内と判定する。`APPIMAGE` が空文字なら単独では該当しない。`APPDIR` が truthy なら `APPIMAGE` の有無にかかわらず AppImage 内と判定する。文字列比較・大文字小文字変換・数値変換はしない。 |

## 有効になる条件

- `command_name()` は Linux 専用の `supervisor` モジュールにあり、`--browser` で開いた案内文と、ウィンドウ異常終了後のログ収集案内に使われます。`--browser` と `STRATA_UI=browser` のどちらが選ばれたかを決める変数ではありません（`apps/desktop/src-tauri/src/main.rs:47-48,871-875`、`apps/desktop/src-tauri/src/supervisor.rs:43-55,75-79,303-313,316-338,385-400`）。
- `graphics_environment()` は指定された環境変数を列挙し、値が `std::env::var` で取得できるものだけ `APPIMAGE=<値>` として返します。異常終了時のクラッシュレポートと `--save-logs` のログに含まれます。これは診断情報であり、値によるウィンドウ描画設定の切り替えではありません（`apps/desktop/src-tauri/src/desktoplog.rs:186-194,245-259,310-329`）。
- ホストの外部環境処理では、`APPIMAGE` または `APPDIR` が truthy なら `externalEnvironment()` が記録済みの起動元環境を優先し、記録がなければ AppImage 専用変数を除去したコピーを使います。`APPIMAGE_ONLY` に `APPIMAGE` が含まれるため、後者ではこの変数も削除されます。`APPDIR` がある場合は、同じ fallback 経路でそのディレクトリ内を指す環境値やパス要素も除去します。`extra` は最後に適用されます。起動元環境の記録がない場合、`APPIMAGE` は存在判定に使われた後、外部プログラムの環境から除かれます（`apps/host/server/external-env.mjs:17-26,43-57,60-71`）。
- この変換は `xdg-open`、ファイル選択ダイアログ、通知、エージェント用ツール等の子プロセスに渡す環境に適用されます。呼び出し例は `apps/host/server/artifacts.mjs:5-6`、`apps/host/server/folder-dialog.mjs:112-126,135-145,153-164`、`apps/host/server/app-ui.mjs:38-59`、`apps/host/server/agent/harness-runtime.mjs:25-36` です。エージェント環境ではその後 `KEEP` に一致する名前だけが残るため、`APPIMAGE` は最終環境に含まれません。

## 実行時の詳細

Rust 側の `command_name()` は呼び出しごとに `std::env::var("APPIMAGE")` を実行し、結果をキャッシュしません。変数が取得できても `Path::file_name()` が返す名前だけを `./` の後ろに付けて表示し、起動や終了コードには使いません。表示先はブラウザー案内行、またはウィンドウ異常終了後の stderr と shell log です（`apps/desktop/src-tauri/src/supervisor.rs:65-79,303-313`）。

Rust の診断ログも呼び出しのたびに環境を列挙します。`--save-logs` では `Graphics session:` の項目として保存され、クラッシュ時はクラッシュレポートの同じ項目に入ります。`--save-logs` が成功すれば保存先を stdout に表示して終了コード 0、書き込みに失敗すれば `[strata] could not save the logs: ...` を stderr に出し、コード 1 を返します。これらの保存結果は `APPIMAGE` の値で分岐しません（`apps/desktop/src-tauri/src/desktoplog.rs:186-194,245-259,281-289,310-329`、`apps/desktop/src-tauri/src/supervisor.rs:316-332`）。

JavaScript 側の `insideAppImage()` と `externalEnvironment()` は呼び出し時の環境オブジェクトを評価し、値をキャッシュしません。子プロセス起動時に `externalEnvironment()` の返す環境を渡します。記録済み環境がなければ `withoutAppImage()` が `APPIMAGE` を削除します。記録がある場合はデコードされた元環境を使うため、その内容に `APPIMAGE` が含まれていれば保持されます。コード上、この環境選択に伴う `APPIMAGE` 固有の警告や終了経路はありません（`apps/host/server/external-env.mjs:28-40,43-71`）。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:47-48,871-875` — Linux のみ `supervisor` を組み込み、入口でオプションを解釈。
- `apps/desktop/src-tauri/src/supervisor.rs:65-79,303-313` — `APPIMAGE` から案内用コマンド名を作る処理と出力箇所。
- `apps/desktop/src-tauri/src/desktoplog.rs:186-194,245-259,310-329` — 値の取得・クラッシュレポートと `--save-logs` への記録。
- `apps/host/server/external-env.mjs:17-26,43-71` — AppImage 判定、専用変数の除去、起動元環境との選択。
- `apps/host/server/artifacts.mjs:5-6`、`apps/host/server/folder-dialog.mjs:112-126`、`apps/host/server/app-ui.mjs:38-59`、`apps/host/server/agent/harness-runtime.mjs:25-36` — 外部プログラム起動時の利用例。
