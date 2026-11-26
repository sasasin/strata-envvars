# `STRATA_NO_PATH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Windows 用 `tools/packaging/install.ps1` が、インストール後にユーザー PATH を更新するかを切り替える。値が文字列 `1` の場合、インストーラーは PATH の更新をスキップし、実行ファイル `strata.cmd` の場所を表示する。それ以外の場合はユーザー PATH に `bin` を追加し、インストーラー自身の `$env:Path` にも追加する。インストールや署名確認自体を無効にする設定ではない（`tools/packaging/install.ps1:184-224`）。

## 値と判定

PowerShell の `$env:STRATA_NO_PATH` を `-eq '1'` / `-ne '1'` で文字列比較する。数値変換、真偽値変換、空白除去はしない。`1` 以外なら PATH 更新側へ進む。

| 実行経路 | 未設定 | PATH 更新を抑止する値 | PATH 更新を抑止しない値 |
|---|---|---|---|
| Windows 用 `install.ps1` | 抑止しない | `1` | 空文字、`0`、`true`、`false`、`01`、`1 `、` 1`、`1anything` など |

判定は `tools/packaging/install.ps1:217-224`。値の大小文字はこの値 `1` では差を生じない。空文字と未設定はどちらも `1` と一致せず、更新側に進む。

## 有効になる条件

- Windows 用インストーラーの経路でのみ参照される。スクリプトは Windows 以外で停止する（`tools/packaging/install.ps1:1-3,103`）。
- `STRATA_NO_PATH` が文字列 `1` のときに PATH 変更を抑止する。それ以外の値では、ユーザー PATH 更新を試みる（`tools/packaging/install.ps1:217-224`）。
- インストールの前提となるリリース取得、署名確認、配置などはこの値に関係なく先に実行される（`tools/packaging/install.ps1:118-215`）。
- CLI 引数や別の環境変数による上書き分岐はない。`STRATA_NO_PATH` を読み取る実装はこのインストーラーだけで、エンジンやサーバー側での読み取りは確認できない。

## 実行時の詳細

インストーラーはインストール先の `current\bin` を `$bin` にした後で値を読み、PATH の分岐を行う。キャッシュや数値変換はなく、分岐箇所で PowerShell のプロセス環境から参照する（`tools/packaging/install.ps1:201-224`）。`1` の場合は `Add-ToUserPath` を呼ばず、`$env:Path` も変更しない。既存のユーザー PATH エントリーを削除する処理はない。最後に通常の完了表示 `Installed. Run: strata launch` と、実行ファイルの場所を示す `  (the program is $bin\strata.cmd)` を表示する（`tools/packaging/install.ps1:217-224`）。

`1` 以外の場合、`Add-ToUserPath` はユーザーの `Environment` レジストリキーから未展開の `Path` を読み、既に同じフォルダーがあれば重複追加せず、なければ末尾に追加する。更新失敗は捕捉され、`  (your user PATH could not be changed: $($_.Exception.Message). Run $bin\strata.cmd, or add that folder to PATH yourself.)` を表示する。その場合でもインストーラーの `$env:Path` には `$bin` を追加し、完了後は新しいターミナルを開く案内を表示する（`tools/packaging/install.ps1:77-97,217-224`）。

## ログと測定値

`STRATA_NO_PATH='1'` のとき、完了後に `Installed. Run: strata launch` と `  (the program is $bin\strata.cmd)` を標準出力へ表示する。それ以外では `Installed. Run: strata launch` と `  (open a new terminal window if the command is not found yet)` を表示する。PATH 更新失敗時の案内は上記のとおり。性能測定値は該当しない（`tools/packaging/install.ps1:217-224`）。

## 根拠

- `tools/packaging/install.ps1:1-3,17-20` — Windows 用インストーラーと変数の説明。
- `tools/packaging/install.ps1:73-98` — ユーザー PATH の読み書き、重複確認、更新通知。
- `tools/packaging/install.ps1:103` — Windows 以外で停止する条件。
- `tools/packaging/install.ps1:184-224` — PATH 分岐の前に行う署名確認・配置と、変数の判定、表示、失敗時の案内。
