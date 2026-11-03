# `STRATA_SELFPID`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows NSIS アンインストーラーが、自身のプロセス ID を PowerShell 子プロセスへ渡すための内部用環境変数です。子コマンドはインストール先配下のプロセスを停止する候補から、この ID を除外します。Strata の通常実行時に利用者が設定して機能を切り替える変数ではありません。

## 値と判定

アンインストーラーは `GetCurrentProcessId()` の戻り値を NSIS 変数 `$9` に受け取り、その値で `STRATA_SELFPID` を設定してから PowerShell を起動します。したがって、起動前から同名変数が未設定・空文字・任意の値であっても、その値を設定用途には使わず、アンインストーラー自身の PID で上書きします。PowerShell コマンド内では環境変数を `[int]` に変換し、プロセス ID と比較します。Strata 側にユーザー入力値のパース、無効値時の既定値、数値境界の検証はありません。

## 有効になる条件

- `apps/desktop/src-tauri/tauri.conf.json:21,52-56` で Windows の `nsis` バンドルにこのテンプレートが指定されています。
- アンインストール節で `StrataStopOwnProcesses` マクロが呼ばれた場合に実行されます。通常のアプリ起動やエンジンの CLI / サーバー経路では読み書きされません。
- `STRATA_SELFPID` の値を選ぶ CLI 引数や他の環境変数との優先順位はありません。マクロが現在の NSIS プロセス ID を設定します。

## 実行時の詳細

アンインストール節は、ファイル削除前にマクロを呼び出します。マクロはインストール先も `STRATA_INSTDIR` に設定し、NSIS プロセス ID を `STRATA_SELFPID` に設定した後、PowerShell を起動します。32-bit の NSIS から 64-bit プロセスのイメージパスを扱えるよう、`Sysnative` 配下の PowerShell があればそちらを選び、なければ `powershell.exe` を使います。

PowerShell コマンドは、インストール先配下にあるプロセス ID を列挙し、重複を除いてから `STRATA_SELFPID` と異なる ID に `Stop-Process -Force` を実行します。`Get-Process` の失敗と CIM 列挙の例外、停止時のエラーはコマンド上で抑制され、最後に 1500 ms 待機します。その後 NSIS は `CheckIfAppIsRunning` を呼び、続いてインストールファイルの削除に進みます。マクロ内にこの処理の明示的なログ出力はありません。

## 根拠

- `apps/desktop/src-tauri/tauri.conf.json:21,52-56` — Windows NSIS バンドルとテンプレートの指定。
- `apps/desktop/src-tauri/nsis/installer.nsi:708-718` — インストール先と現在の PID の設定、PowerShell 起動、環境変数の参照、PID 除外、プロセス停止と待機。
- `apps/desktop/src-tauri/nsis/installer.nsi:873-884` — アンインストール時にマクロをファイル削除前に呼び出す流れ。
