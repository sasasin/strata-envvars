# `STRATA_APP_SESSION_FILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Linux 版 Strata Desktop supervisor が、起動中インスタンスを特定する session file のパスを指定します。このファイルには shell の PID、host の port、token、window/browser mode が保存され、次の起動や `--quit` が既存インスタンスを見つけるために使います。Linux 以外では supervisor モジュールが組み込まれず、この変数を読むコードはありません。

## 値と判定

`std::env::var_os` で取得し、設定されていれば値を `PathBuf` にそのまま渡します。Unicode 文字列への変換、数値化、内容検証、空文字の特別扱いはありません。

| 状態 | パスの決定 |
|---|---|
| 未設定 | `HOME` があれば `$HOME/.strata/app-session.json`。`HOME` も未設定なら `std::env::temp_dir().join(".strata").join("app-session.json")` |
| 設定あり | 環境変数の値を `PathBuf` として使用。空文字も設定ありとして既定パスに fallback しない |

設定値が相対パスならプロセスの current working directory からの相対パスです。`~` の展開や既定パスとの併用は行いません。CLI 引数によるパス上書きもありません。空文字や不正なパスを事前に拒否する分岐はなく、ファイル操作の成否に委ねられます。

## 有効になる条件

- `main.rs` で `supervisor` モジュールを `#[cfg(target_os = "linux")]` として組み込み、Linux の起動時に window child でないプロセスから supervisor の `run()` を呼びます。したがってこの変数は Linux デスクトップアプリの supervisor 経路で使われます。
- `--browser`、`STRATA_UI=browser` は起動 mode を変えますが、session file のパス選択は変えません。`--quit` も同じ session file を参照します。
- Windows/macOS の embedded 起動経路はこの supervisor を使いません。

## 実行時の詳細

パス選択関数は呼ばれるたびに `var_os` を実行し、static cache はありません。通常起動では既存の live session を探すため `run()` の冒頭で `live_session()` が呼ばれ、その後 host の health check 成功時に session を書きます。window の起動失敗や window crash 後に browser mode へ切り替える場合も同じ場所へ更新します。終了時は保存 session の PID が自プロセスと一致する場合に削除します。

`read_session()` は選択されたファイルを読み、JSON の `pid`、`port`、`token`、`mode` を取り出します。ファイル読み込み・JSON decode・必須値の取得に失敗すると `None` を返し、その失敗自体のログは出しません。`live_session()` はさらに PID の生存（Linux では `/proc/<pid>` の存在）と `http://127.0.0.1:<port>/api/health` の応答を確認し、条件を満たさなければ既存 instance として扱いません。通常起動ではその後新しい host を開始し、health check が通ると同じパスへ session を書きます。`--quit` では live session がなければ `Strata is not running.` を出して session file の削除を試み、終了コード 0 を返します。

書き込み時は親ディレクトリの作成を試みますが、その失敗は無視します。ファイルは create/truncate で開き、Unix では新規作成時の mode に `0600` を指定します（既存ファイルの mode を変更する処理ではありません）。open に失敗すると stderr に `[strata] could not write <path>: <error>` を出します。書き込み自体の失敗は無視されます。読み取り・削除のファイル操作エラーも表に出さず、session 判定や削除が失敗しても専用の警告・終了コードにはなりません。

## 根拠

- Linux のみ supervisor を組み込み、Linux 起動時に window child 以外を supervisor に渡す: `apps/desktop/src-tauri/src/main.rs:40-44,865-876`。
- 値を取得して既定パスを選ぶ処理: `apps/desktop/src-tauri/src/supervisor.rs:96-102`。
- session の書き込み、親ディレクトリ作成、JSON、Unix mode、open failure の stderr: `apps/desktop/src-tauri/src/supervisor.rs:104-122`。
- session の読み取りと parse 失敗時の `None`: `apps/desktop/src-tauri/src/supervisor.rs:125-134`。
- PID・health check による live 判定: `apps/desktop/src-tauri/src/supervisor.rs:142-162`。
- `--quit` の no-session 出力、削除試行、終了コード: `apps/desktop/src-tauri/src/supervisor.rs:241-264,316-339`。
- 通常起動の session 確認、host health 成功後の書き込み、window crash 時の更新、終了時削除: `apps/desktop/src-tauri/src/supervisor.rs:337-383,395-400,404-434`。
