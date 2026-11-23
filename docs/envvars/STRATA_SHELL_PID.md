# `STRATA_SHELL_PID`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux デスクトップアプリのウィンドウ子プロセスに、そのプロセスを起動した Strata shell の PID を渡す変数。`--window-child` とともに起動したプロセスが環境変数の PID と実際の親 PID が一致するかを調べ、shell からの通常起動か、アプリ updater による再起動かを判定する。一致すればウィンドウ処理を続け、不一致なら旧 Strata の終了を待って通常起動をやり直す。shell はウィンドウ子プロセスを起動する際に自分の PID を設定する（`app/desktop/src-tauri/src/main.rs:929-941`、`app/desktop/src-tauri/src/supervisor.rs:231-238,390-400,544-555`）。

この判定は Linux 専用で、Windows/macOS の `run_embedded()` 経路はこの環境変数を読まない（`app/desktop/src-tauri/src/main.rs:931-944`）。また、`--window-child` でない起動ではこの値による起動元判定を行わない。

## 値と判定

Rust の `std::env::var(...).ok()` で文字列を取得し、`started_by_shell` は前後の空白を `trim()` してから `u32` として parse する。parse 後の値が 0 でなく、現在のプロセスの親 PID と等しい場合だけ shell 起動と判定する。文字列全体を数値として parse するため、空文字、空白だけ、負数、数値以外を含む文字列、`u32` の範囲外は一致判定に使えない。先頭のゼロを含む十進表記は数値として比較される。未設定や UTF-8 でない環境値も `.ok()` により値なしとして扱われる（`app/desktop/src-tauri/src/main.rs:938`、`app/desktop/src-tauri/src/supervisor.rs:235-238`）。

| 条件 | unset / 取得不能 | 有効になる値 | 一致判定に使えない値 |
|---|---|---|---|
| Linux で `--window-child` を起動 | `started_by_shell` は `false`。更新後の再起動経路へ進む | trim 後に parse できる `u32` が 1〜`u32::MAX` で、現在の親 PID と一致する。例: `4242`, ` 4242\n`（実際の親 PID が 4242 の場合）。`1` も親 PID が 1 の場合は一致する | `""`, `"   "`, `"0"`, `"-1"`, `"true"`, `"false"`, `"0anything"`, `"x"`, `"4242tail"`, `"4294967296"`、または親 PID と異なる数値 |
| Linux で `--window-child` ではない起動 | 起動元判定で参照しない | 該当なし | 該当なし |
| Windows/macOS のデスクトップ起動 | このコード経路では参照しない | 該当なし | 該当なし |

上表の「有効」は親プロセス一致の意味であり、環境変数の存在だけでは shell 起動と判定されない。実装上のテスト例も、PID 一致と前後空白を受理し、親 PID 不一致・未設定・不正文字列・ゼロを拒否している（`app/desktop/src-tauri/src/supervisor.rs:653-663`）。

## 有効になる条件

- Strata デスクトップの Linux ビルドであること。`main()` の Linux 条件付きブロックだけが `SHELL_PID_ENV` を起動元判定へ渡す（`app/desktop/src-tauri/src/main.rs:931-941`）。
- コマンドラインに `--window-child` があること。なければ shell の `supervisor::run()` に進み、起動元判定をしない（`app/desktop/src-tauri/src/main.rs:933-939`）。
- 通常の shell 起動では、`spawn_window()` とウィンドウ起動処理が子プロセスへ shell の PID を設定する。ブラウザー起動 (`opts.browser`) ではウィンドウ子プロセスを起動しない（`app/desktop/src-tauri/src/supervisor.rs:390-400,547-555`）。
- 値が未設定・不正・ゼロ、または実際の親 PID と異なる場合は `started_by_shell` が `false` となり、`restart_after_update()` へ進む。この関数は `STRATA_SHELL_PID` を再取得し、trim 後に非ゼロの `u32` として parse できれば旧 shell PID に使う。取得・parse できない場合は session ファイルの PID に fallback する（`app/desktop/src-tauri/src/main.rs:937-940`、`app/desktop/src-tauri/src/supervisor.rs:336-340`）。
- 有効な shell PID が現在のプロセス PID と異なり、その PID が生存中なら、旧 shell が終了するまで最大 `HOST_STOP_SECONDS + 20` 秒待つ（現行値は 80 秒）。期限までに終了しない場合は二重起動を避けて再起動せず終了コード 0 で戻る（`app/desktop/src-tauri/src/supervisor.rs:240-243,340-348`、`app/desktop/src-tauri/src/main.rs:605`）。
- 待機後にも live session があれば、二つ目の Strata を起動せず終了コード 0 で戻る（`app/desktop/src-tauri/src/supervisor.rs:350-353`）。

## 実行時の詳細

値の読み取りはプロセス起動時の Linux `main()` で一度行われ、関数内 static などの cache はない。起動元と判定されなかった場合に限り、`restart_after_update()` の入口でもう一度環境から読み直す（`app/desktop/src-tauri/src/main.rs:938-940`、`app/desktop/src-tauri/src/supervisor.rs:336-340`）。

通常の shell は `--window-child` を付けて子プロセスを起動し、`std::process::id()` を `STRATA_SHELL_PID` に設定する。従って値は親 shell の PID として引き継がれ、別の `STRATA_SHELL_PID` があってもこの子起動時には上書きされる（`app/desktop/src-tauri/src/supervisor.rs:390-400,544-555`）。

updater による再起動では、まず環境値から旧 PID を得て、無効なら session ファイルから補う。旧 PID が自分自身なら待機しない。旧 shell の終了を確認した後、既に別の Strata が稼働中なら再起動を抑止する。再起動用プロセスには、`STRATA_ORIGINAL_ENV` が復元できればその環境を設定し、復元できなければ `STRATA_WINDOW_PORT`、`STRATA_SHUTDOWN_TOKEN`、`STRATA_SHELL_PID` を継承環境から除去する。再起動した shell が次のウィンドウ子プロセスを作る際には、自身の PID で `STRATA_SHELL_PID` を設定し直す（`app/desktop/src-tauri/src/supervisor.rs:274-299,358-375,390-400`）。

## ログと測定値

この環境変数の再起動経路は標準出力・標準エラーへ説明を出さず、`Log::open()` が作る desktop log に記録する。記録される文言には `started as the app window by the app updater, not by Strata (old app process ...)`、旧 shell が期限内に終了しない場合の `the old Strata (process ...) did not stop within ... s: not starting a second one`、稼働中 session がある場合の `another Strata is already running: not starting a second one` がある。再起動対象の特定・spawn が失敗した場合はそれぞれ `could not tell which program to start again`、`could not start ... again: ...` を記録する（`app/desktop/src-tauri/src/supervisor.rs:336-356,358-383`、`app/desktop/src-tauri/src/desktoplog.rs:115-140`）。この環境変数に関する測定値は該当しない。

## 根拠

- Linux の起動分岐、CLI フラグ確認、PID と親 PID の照合: `app/desktop/src-tauri/src/main.rs:929-944`、`app/desktop/src-tauri/src/supervisor.rs:43-55,231-238`
- 起動時の子プロセスへの PID 設定: `app/desktop/src-tauri/src/supervisor.rs:390-400,544-555`
- updater 再起動、PID fallback、待機、重複起動抑止、環境の設定: `app/desktop/src-tauri/src/supervisor.rs:274-299,336-400`
- ログ出力先: `app/desktop/src-tauri/src/desktoplog.rs:115-148`
