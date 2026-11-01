# `GDK_BACKEND`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のデスクトップシェルは、この変数をグラフィックス環境の診断情報として読み取り、Linux のウィンドウクラッシュログと `--save-logs` のログ収集ファイルに記録します。Strata のコードは値を見てウィンドウの backend を選択・変更したり、値に応じて分岐したりしません。

## 値と判定

`desktoplog::graphics_environment()` は `GDK_BACKEND` を含む固定名リストを順に走査し、各名前について `std::env::var(n)` を呼びます。値の parse、比較、正規化、範囲検査はありません（`apps/desktop/src-tauri/src/desktoplog.rs:186-194`）。

| 状態 | Strata の記録 |
|---|---|
| 未設定 | `std::env::var` が値を返さないため項目を出力しない |
| 空文字 | 取得成功し、`  GDK_BACKEND=` と出力する |
| Unicode 文字列 | `  GDK_BACKEND=<値>` と値をそのまま埋め込む。特定の値だけを有効扱いする判定はない |
| Unicode として取得できない OS 文字列 | `std::env::var` がエラーとなり、`.ok()` により項目を出力しない |

## 有効になる条件

この変数による Strata 内の機能切り替えはありません。読み取りは診断情報を組み立てる場合に限られます。

- Linux でウィンドウプロセスが異常終了または起動できず、シェルがクラッシュログを作成するとき、`crash_report()` が graphics environment を含めます（`apps/desktop/src-tauri/src/supervisor.rs:303-313`; `apps/desktop/src-tauri/src/desktoplog.rs:245-260,281-288`）。
- Linux の `--save-logs` では、ログ収集ファイルの `Graphics session:` 欄に含めます（`apps/desktop/src-tauri/src/supervisor.rs:316-332`; `apps/desktop/src-tauri/src/desktoplog.rs:310-320`）。
- 普通の起動時にこの値を読み取る処理は確認できません。ログ作成時に関数が呼ばれるたびに環境から読み直し、値をキャッシュしません。

## 実行時の詳細

クラッシュログでは `crash_report()` が `graphics_environment()` を呼び、`GDK_BACKEND` を含む取得可能な項目を `Graphics session:` の下に一行ずつ追加します。Linux シェルはウィンドウプロセスが停止した場合、`window_failed()` からこのログ作成を試みます。ログ作成に成功すれば端末にクラッシュログの保存先を表示し、失敗すれば「The crash log could not be written.」を表示します。その後、Strata はブラウザ表示へ切り替えます。`--save-logs` は同じ環境情報を収集ファイルに追加し、保存成功時は保存先を表示、失敗時は `[strata] could not save the logs: ...` を stderr に出して終了コード 1 を返します（`apps/desktop/src-tauri/src/supervisor.rs:303-332`）。

`GDK_BACKEND` の値は Strata が別プロセスへ明示設定する値ではありません。Linux のウィンドウプロセス起動では `Command` に `STRATA_WINDOW_PORT` と `STRATA_SHUTDOWN_TOKEN` を追加し、環境を消去する処理はありません（`apps/desktop/src-tauri/src/supervisor.rs:229-239,390-394`）。この文書では、Strata が外部 GTK/WebKit 等での値の解釈や backend 選択を行うとは扱いません。

同梱の Linux トラブルシュート文書は、空白・白画面時に `GDK_BACKEND=x11 ./@APPIMAGE@` を試すよう案内しています（`apps/desktop/tester/common-troubleshoot.txt:19-24`）。これは利用者向けの起動例であり、Strata 自身が `GDK_BACKEND` を解釈する実装ではありません。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — 環境変数名一覧と `std::env::var` による動的な読み取り、出力形式。
- `apps/desktop/src-tauri/src/desktoplog.rs:245-260,281-288` — クラッシュログへの挿入と作成処理。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-340` — `--save-logs` ファイルへの挿入と保存。
- `apps/desktop/src-tauri/src/supervisor.rs:303-332` — Linux のクラッシュ経路、端末表示、`--save-logs` の成否と終了コード。
- `apps/desktop/src-tauri/src/supervisor.rs:229-239,390-394` — ウィンドウ子プロセスの起動時に追加する環境設定。
- `apps/desktop/tester/common-troubleshoot.txt:19-24` — `GDK_BACKEND=x11` の利用者向け案内。
