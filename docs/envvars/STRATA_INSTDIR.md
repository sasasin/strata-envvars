# `STRATA_INSTDIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows の NSIS アンインストーラーが、アプリのインストール先配下にある実行ファイルのプロセスを探して停止する処理で使います。アンインストーラーが現在のプロセス環境に値を設定し、起動する PowerShell に渡すための内部的な受け渡しです。Strata アプリ本体やサーバーの設定として読み取る箇所は、この commit のソース全体では見つかりませんでした。

## 値と判定

| 状態 | ソース上の扱い |
| --- | --- |
| アンインストーラー実行時 | `StrataStopOwnProcesses` マクロが `STRATA_INSTDIR` にマクロ引数 `${INSTALLDIR}` を設定します。呼び出し側は `"$INSTDIR"` を渡します。 |
| 値の変換 | NSIS / Windows API 側では `SetEnvironmentVariableW` に渡し、その後の PowerShell コマンドは値を `[IO.Path]::GetFullPath(...)` に渡して末尾の `\` を除去し、比較用に `\` を付けます。 |
| 未設定・空文字・無効値 | この処理は環境変数を読む前に設定しますが、API 呼び出しの成否や値の空・妥当性を調べる分岐、明示的な fallback はありません。値の変換エラーに対する Strata 側の処理もありません。 |

CLI 引数や他の環境変数との優先順位はありません。既存の同名環境変数を参照して設定値を決めるのではなく、アンインストーラーの `$INSTDIR` を設定します。

## 有効になる条件

- Windows 用 NSIS の `Section Uninstall` から `StrataStopOwnProcesses "$INSTDIR"` が実行されるときに限ります。
- OS/backend/build macro、モデル状態、CLI オプションによる条件はありません。この環境変数を読むアプリ本体の backend 条件もありません。
- インストーラーが 64-bit PowerShell の場所を優先し、存在しない場合は `powershell.exe` を選んで起動します。この選択は PowerShell の実行ファイルの場所に関するもので、`STRATA_INSTDIR` の値の優先順位ではありません。

## 実行時の詳細

アンインストーラーは環境変数に `$INSTDIR` を設定し、続けて自身の PID も `STRATA_SELFPID` に設定して PowerShell を起動します。PowerShell コマンドは、プロセスの実行ファイルパスがインストール先ディレクトリ配下にあるものを列挙し、同じ PID を重複排除した後、アンインストーラー自身を除外して `Stop-Process -Force` に渡します。比較は `OrdinalIgnoreCase` で、インストール先の末尾に区切り文字を付けてから prefix 判定します。CIM によるプロセス列挙は `try/catch` 内にあり、その失敗はコマンド中で無視されます。最後に PowerShell コマンドは 1500 ms 待機を指定しています。

環境変数の判定結果を cache する仕組みはありません。値はアンインストーラーから PowerShell を起動するときに設定・受け渡されます。`nsExec::Exec` の返り値をこのマクロは確認せず、成功・失敗に応じたログや終了分岐もありません。直後には通常の `CheckIfAppIsRunning` マクロが続きますが、その後の検出・表示動作は本変数自体の処理ではありません。

## 根拠

- `apps/desktop/src-tauri/nsis/installer.nsi:704-718`: マクロの目的、`STRATA_INSTDIR` と `STRATA_SELFPID` の設定、PowerShell の選択と起動、パスの比較・停止コマンド。
- `apps/desktop/src-tauri/nsis/installer.nsi:873-884`: アンインストールセクションでマクロを呼び、続けてアプリ実行ファイルの確認と削除を行う流れ。
- `apps/desktop/src-tauri/nsis/installer.nsi:725-730`: 後段のインストールフォルダー削除マクロ。
