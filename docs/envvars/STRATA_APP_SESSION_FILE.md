# `STRATA_APP_SESSION_FILE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux 版 Strata Desktop の supervisor が、起動中インスタンスを見つけるために使うセッション JSON ファイルのパスを差し替える。ファイルには supervisor PID、ホストのポート、認証 token、window/browser mode が保存される。既存インスタンスの検出、`--quit`、アップデーター再起動時の PID 引き継ぎに使われる。モデルの推論設定や Terminal のモデルサーバー設定は変えない。`supervisor` モジュール自体が `target_os = "linux"` のときだけ組み込まれるため、Windows/macOS ではこの変数を読む実行経路がない（`app/desktop/src-tauri/src/main.rs:45-51,929-944`, `app/desktop/src-tauri/src/supervisor.rs:16-18,96-102`）。

## 値と判定

`std::env::var_os` で設定の有無を調べ、設定されていれば値をそのまま `PathBuf` にする。値の文字列比較、数値変換、正規化、空文字の除外はない。未設定の場合だけ `HOME/.strata/app-session.json` を使い、`HOME` も未設定なら `std::env::temp_dir()/.strata/app-session.json` を使う。`HOME` が空文字なら空のパスを起点にした相対パスになる（`app/desktop/src-tauri/src/supervisor.rs:96-102`）。

| 条件 | unset | 設定時に使われる値 | 不正・利用不能な場合 |
|---|---|---|---|
| Linux Desktop supervisor | `HOME/.strata/app-session.json`。`HOME` 未設定なら temp dir 配下 | 例: `/tmp/strata/session.json` をそのまま使用。空文字も「設定あり」で空の `PathBuf` になる | パス内容の検証・値域はない。読み取りに失敗すると session なしとして扱い、書き込みの open に失敗するとエラーを stderr に出す |
| Windows/macOS、および Terminal | この変数の読み取り箇所なし | 効果なし | 該当なし |

空文字は既定値への fallback ではなく、ファイル名のないパスとしてファイル操作に渡る。`0`、`1`、`true`、`false` も真偽値ではなく、相対ファイル名として扱われる。相対パス、非 UTF-8 の OS パスも `var_os` / `PathBuf` で受け取る。パスの存在・権限・JSON 内容は値判定時には検証しない。たとえば親ディレクトリを作成できない `/no/such-parent/s.json` は書き込みに失敗し得るが、パス文字列自体の拒否分岐はない（`app/desktop/src-tauri/src/supervisor.rs:96-102,104-123,125-139`）。

## 有効になる条件

- Linux 用 Desktop バイナリの supervisor 経路であること。`main` は Linux でのみ `supervisor::run` または更新再起動処理に入る（`app/desktop/src-tauri/src/main.rs:50-51,929-942`）。
- `--browser` / `STRATA_UI=browser` は JSON の mode を変えるが、セッションファイルのパス選択には関与しない。`--quit` は同じパスからセッションを探す（`app/desktop/src-tauri/src/supervisor.rs:43-55,403-408,496-500,515-545`）。
- 値が有効なパスでも、読める JSON と必要な `pid` / `port` / `token` がなければ既存セッションとして認識されない。既存起動の検出にはさらに PID 生存と App Host の health identity 判定が必要（`app/desktop/src-tauri/src/supervisor.rs:125-164,499-501`）。
- `--help` と `--save-logs` は `run` 内でセッション処理より先に終了する（`app/desktop/src-tauri/src/supervisor.rs:478-498`）。

## 実行時の詳細

`session_path()` は環境変数を呼び出しごとに評価し、static cache はない。起動時の `live_session()` が `read_session()` を呼び、既存インスタンスがなければ App Host の health check 成功後に `write_session()` が JSON を保存する。window 起動失敗や window の異常終了から browser mode に切り替える際にも同じファイルを更新し、supervisor 終了時には PID が一致する場合だけ削除する（`app/desktop/src-tauri/src/supervisor.rs:96-139,155-164,499-545,559-595`）。

`read_session()` は毎回ファイルを読み直し、I/O エラーまたは JSON/必須フィールドの不正を `None` にする。`--quit` では有効な稼働セッションが見つからないと `Strata is not running.` を stdout に出し、そのパスのファイル削除を試みて終了コード 0 を返す。通常起動で読めない・無効なセッションは既存インスタンスなしとして扱われ、新しい host 起動へ進む。書き込みでは親ディレクトリ作成の失敗と `write_all` の失敗は無視され、ファイル open の失敗だけ `[strata] could not write {path}: {error}` を stderr に出す。Unix では作成ファイルに mode `0600` を指定する（`app/desktop/src-tauri/src/supervisor.rs:104-139,403-408,499-545`）。

セッションファイルのパスは子プロセスへ個別に引数として渡されず、window child 起動では通常の環境継承により変数も継承される。ただし path を読む処理は Linux supervisor 側にあり、環境変数を実行中に変更した場合でも次回の `session_path()` 呼び出しから再評価される。設定変更の同期やファイル移動は行わない（`app/desktop/src-tauri/src/supervisor.rs:96-102,390-400`）。

## ログと測定値

測定値は該当しない。観測可能な失敗は、session ファイルの open 失敗時の stderr `[strata] could not write {path}: {error}`。読み込み失敗、JSON parse/フィールド不正、親ディレクトリ作成、書き込み後の `write_all` 失敗は、このコードではログに出さない。`--quit` で session を見つけられない場合の stdout は `Strata is not running.`（`app/desktop/src-tauri/src/supervisor.rs:117-122,125-134,403-408`）。

## 根拠

- Linux 限定のモジュール登録と起動経路: `app/desktop/src-tauri/src/main.rs:45-51,929-944`
- 環境変数の読み取りと既定パス: `app/desktop/src-tauri/src/supervisor.rs:96-102`
- session JSON の読み書き・削除・失敗扱い: `app/desktop/src-tauri/src/supervisor.rs:104-139`
- 稼働中インスタンス判定: `app/desktop/src-tauri/src/supervisor.rs:142-164`
- `--quit`、通常起動時の参照と書き込み、終了時の削除: `app/desktop/src-tauri/src/supervisor.rs:403-408,478-545,559-595`
- window child 起動: `app/desktop/src-tauri/src/supervisor.rs:390-400`
