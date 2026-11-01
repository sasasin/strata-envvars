# `APPIMAGE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

デスクトップ版では、起動に使われた AppImage のパスから利用者向けの再実行コマンドを組み立てます。また、ホストが外部プログラム用の環境を作る際、AppImage 内で動作しているかを判定する手掛かりの一つとして使います。クラッシュ時の診断ログにも値を記録します。

これはデスクトップ／ホスト側の処理です。Strata の C++/CUDA/HIP/SYCL エンジンが `APPIMAGE` を読む箇所は確認できませんでした。

## 値と判定

| 読み取り箇所 | 未設定 | 設定時の判定・変換 |
|---|---|---|
| デスクトップの `command_name()` | `current_exe()` のファイル名を使用し、得られなければ `strata-desktop` | Rust の `std::env::var` が Unicode 文字列として取得できた場合、パスの `file_name()` を取り、`./<ファイル名>` を返す。値の形式や数値は検証しない。空文字やファイル名のないパス、Unicode でない値ではこの分岐から名前を得られず、実行ファイル名側へ fallback する。 |
| ホストの `insideAppImage(env)` | `APPDIR` も falsy なら false | JavaScript の `!!(env.APPIMAGE || env.APPDIR)`。空文字は false、空でない文字列は true。値のパス検証はしない。 |
| ホストの `withoutAppImage(env)` | 既定引数は `process.env` | `APPDIR` は `env.APPDIR || ''` として使用。コピーから `APPIMAGE` と AppImage 関連変数を削除する。`APPDIR` が truthy の場合は、PATH 系リストからそのディレクトリ以下の要素も除く。 |
| デスクトップの診断ログ | `std::env::var` が値を得られなければ項目を出さない | 環境値をそのまま `APPIMAGE=<値>` として記録する。 |

いずれも `APPIMAGE=1` のような特定値を要求しません。`command_name()` は環境変数を読み取るたびに評価し、結果をキャッシュしません。ホスト側も `process.env` を使う既定経路では `externalEnvironment()` の呼び出しごとに環境を組み立てます。

根拠: `apps/desktop/src-tauri/src/supervisor.rs:65-73`, `apps/desktop/src-tauri/src/desktoplog.rs:186-194`, `apps/host/server/external-env.mjs:43-70`。

## 有効になる条件

- `command_name()` の値は、ブラウザモード選択時の案内と、ウィンドウプロセスの失敗後に表示するログ収集案内で使われます。`--browser` または `STRATA_UI=browser` はブラウザモードを選ぶ別条件であり、`APPIMAGE` 自体はモード選択に使われません。
- 外部プログラム用環境の整理は、`APPIMAGE` または `APPDIR` が truthy の場合、または `STRATA_ORIGINAL_ENV` が truthy の場合に適用されます。`APPIMAGE` が空文字で `APPDIR` も空、記録環境もなければ、環境はそのままコピーされます。
- `STRATA_ORIGINAL_ENV` が truthy で base64 から元環境を復元できる場合は、その復元環境を使います。復元できない場合は現在の環境から AppImage 関連値を除く fallback を使います。どちらの場合も `extra` 引数は最後にマージされ、同名値を上書きできます。
- `withoutAppImage()` の fallback では `APPIMAGE` を削除します。`APPDIR` が空なら AppImage 内ディレクトリを使った path-list 要素の除去は行いません。

Strata の AppImage 再パッケージ用スクリプトは、AppImage の `AppRun` に `STRATA_ORIGINAL_ENV` を記録するフックを追加します（`apps/desktop/scripts/repack-appimage.sh:52-58`）。これは復元環境を使う経路を用意するもので、ホストが外部プログラムへ渡す具体的な変数は復元された環境の内容に依存します。

## 実行時の詳細

`command_name()` は `APPIMAGE` の値からディレクトリ部分を落としたファイル名を `./` 付きで返し、ブラウザ案内やクラッシュ後の `--save-logs` 案内に埋め込みます。この値でプログラムを起動する処理はなく、表示するコマンド文字列だけを変えます。`APPIMAGE` を取得できない場合は現在の実行ファイル名を使います（`apps/desktop/src-tauri/src/supervisor.rs:65-79,303-313,382-393`）。

ホスト側の `externalEnvironment()` は、AppImage 起動中または `STRATA_ORIGINAL_ENV` があるときに外部プログラム用の環境を選びます。復元記録がない場合は `APPIMAGE` などの AppImage 専用変数を除去します。この helper はブラウザ起動・通知、ファイル／フォルダーを開く処理、フォルダーダイアログ、および assistant のシェル環境を作る処理で呼ばれます（`apps/host/server/external-env.mjs:17-26,43-70`; `apps/host/server/app-ui.mjs:38-58`; `apps/host/server/artifacts.mjs:5-6`; `apps/host/server/folder-dialog.mjs:105-119,146-157`; `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/open-text-file.mjs:26-29`; `apps/host/server/agent/harness-runtime.mjs:25-36`）。外部プログラムや GPU driver が `APPIMAGE` をどう解釈するかはここでは扱いません。

診断ログでは `APPIMAGE` が得られたときに現在値を `Graphics session` 欄へ記録します。これは `--save-logs` で作るログにも含まれ、クラッシュログにも含まれます。値による終了・警告・エラー分岐はありません（`apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-260,310-324`）。

## 根拠

- 候補一覧の `APPIMAGE` は `docs/envvars/000_envvers.md:46`。
- 再実行コマンドの生成と案内への挿入: `apps/desktop/src-tauri/src/supervisor.rs:65-79,303-313,382-393`。
- クラッシュ／保存ログへの環境値の記録: `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-260,310-324`。
- 外部プログラム用環境の判定・復元・削除規則: `apps/host/server/external-env.mjs:15-26,28-40,43-70`。元環境記録を AppRun に加える処理: `apps/desktop/scripts/repack-appimage.sh:52-58`。
- helper の利用箇所: `apps/host/server/app-ui.mjs:38-58`, `apps/host/server/artifacts.mjs:5-6`, `apps/host/server/folder-dialog.mjs:105-119,146-157`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/open-text-file.mjs:26-29`, `apps/host/server/agent/harness-runtime.mjs:25-36`。

`APPIMAGE` の全参照を `rg` で確認しました。README テンプレート等の置換文字列、コメント、テスト上の値は環境読み取りの根拠に含めていません。ビルド、テスト、GPU 実行は行っていません。
