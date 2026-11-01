# `STRATA_WINDOW_TEST_CRASH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Linux デスクトップ版のウィンドウ子プロセスを意図的に abort させ、ウィンドウがクラッシュしたときの supervisor の退避処理を確認するためのテスト用フックです。通常の設定用環境変数ではなく、設定されているとウィンドウを表示する前にプロセスを終了させます。

## 値と判定

値の内容は読みません。`std::env::var_os(...).is_some()` による存在判定なので、未設定ならフックは動かず、空文字を含め何らかの値が設定されていれば abort します。`1` など特定の値や数値形式を指定する必要はありません。無効値や境界値の検査、fallback、値の変換はありません。

## 有効になる条件

- Linux でビルドされたデスクトップ実行ファイルであること。読み取り関数 `run_window_process()` は `#[cfg(target_os = "linux")]` で限定され、Windows/macOS の埋め込みウィンドウ経路からは読み取られません。
- 実行が Linux のウィンドウ子プロセス経路に入ること。通常は supervisor が `--window-child` を付けて起動します。直接 `--window-child` を指定した場合も同じ経路です。
- `--self-test` は Linux の supervisor/子プロセス振り分けより先に実行して終了するため、このフックを読みません。通常の `--browser` または `STRATA_UI=browser` 経路もウィンドウ子プロセスを起動しないため読みません（同時に `--window-child` を指定した場合は子プロセス側へ進みます）。

CLI 引数でこの環境変数を無効化する仕組みはありません。supervisor が起動する子プロセスには親の環境が継承され、ポートと shutdown token のみ追加設定されるため、親プロセスに設定した値も子プロセスの判定対象になります。

## 実行時の詳細

子プロセス起動時に一度だけ判定し、設定されていれば stderr に `[strata] STRATA_WINDOW_TEST_CRASH is set: the window process aborts on purpose.` を出して `std::process::abort()` を呼びます。判定結果をキャッシュしたり、起動後に再評価したりする処理はありません。abort は Tauri のウィンドウ構築より前に起きます。

通常起動では Linux supervisor がウィンドウ子プロセスの stderr を端末・ログへ転送して監視します。子プロセスの終了を検出すると `The app window crashed (signal 6 (abort)).` を記録し、クラッシュログを書き、ブラウザー表示へ切り替えます。ホストはこのウィンドウ終了だけでは停止せず、ユーザーが終了するまで動作を続けます。クラッシュログを書けない場合はその旨のメッセージを出します。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:865-876` — Linux で `--window-child` の有無により supervisor とウィンドウ子プロセスを振り分ける箇所。`:860-863` は self-test の先行終了。
- `apps/desktop/src-tauri/src/main.rs:1137-1145` — Linux 限定の子プロセス関数、設定有無の判定、ログ出力、abort。
- `apps/desktop/src-tauri/src/supervisor.rs:43-53,386-393` — `STRATA_UI=browser` / `--browser` と `--window-child` の引数解析、および子プロセス起動。子起動時に crash 変数を消去せず、ポートと token を設定する。
- `apps/desktop/src-tauri/src/supervisor.rs:203-217` — Unix の signal 6 を `signal 6 (abort)` と説明する処理。
- `apps/desktop/src-tauri/src/supervisor.rs:303-314,404-431` — 失敗したウィンドウの検出、ログ・クラッシュログ、ブラウザーモードへの切り替えとホストの継続。
