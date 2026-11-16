# `APPIMAGE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`APPIMAGE` は Linux デスクトップアプリの AppImage 起動時に、アプリ自身の再起動先と利用者向けの再実行コマンドを決めるために参照される。また、App Host がシステム側プログラムを起動するとき、AppImage 専用環境を識別して子プロセスへ渡す環境から除外する判定にも使う。GPU engine の設定には使われない。

Linux の updater が起動した `--window-child` を通常起動へ切り替える場合、値が非空ならそのパスを再起動プログラムにする。通常の起動や `--browser` / `--quit` の選択はこの値で変わらない（`apps/desktop/src-tauri/src/main.rs:869-881`, `apps/desktop/src-tauri/src/supervisor.rs:319-327,330-383`）。

案内文字列では、Unicode の値からファイル名部分を取り `./<basename>` の形にする。クラッシュログと `--save-logs` の診断情報には、設定されていれば `APPIMAGE=<値>` が Graphics session の項目として記録される（`apps/desktop/src-tauri/src/supervisor.rs:65-79,467-470`, `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`）。

App Host の `external-env.mjs` は `APPIMAGE` または `APPDIR` が truthy かで AppImage 起動を判定する。該当する場合、元の環境記録がなければ `APPIMAGE` を含む AppImage 専用名を除去してから、フォルダ選択・ブラウザー・ファイル関連などの外部プログラムへ環境を渡す。記録があれば記録された元の環境を使う（`apps/host/server/external-env.mjs:17-24,43-71`; 呼び出し例: `apps/host/server/folder-dialog.mjs:117-126`, `apps/host/server/app-ui.mjs:38-46,56-59`, `apps/host/server/artifacts.mjs:5-6`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/open-text-file.mjs:26-29`, `apps/host/server/agent/harness-runtime.mjs:25-36`）。

## 値と判定

Strata では数値・真偽値への変換や文字列全体の特定値比較は行わない。各利用箇所で「環境変数が取得できるか」「空か」「JavaScript の truthy 値か」「パスとして解釈できるか」を別々に判定する。

| 条件（実行経路） | unset | 値の扱い | 空文字 | 無効値・境界 |
|---|---|---|---|---|
| Linux の更新後再起動先 | `current_exe()` を使う | `var_os` で取得し、非空なら値をそのまま `PathBuf` にする | `current_exe()` に fallback | 存在確認や形式検証をせず `Command::spawn` に渡す。起動失敗時はエラーをログに記録して終了コード 1（`supervisor.rs:319-327,352-383`） |
| Linux の再実行コマンド表示 | `current_exe()` のファイル名、さらに取れなければ `strata-desktop` | Unicode として取得できれば `Path::file_name()` の結果を `./` に続ける | ファイル名を得られず fallback | 非 Unicode 値は `std::env::var` が `Err` となり fallback。ディレクトリ部分を含む値も basename のみ表示（`supervisor.rs:65-73`） |
| App Host の外部環境 | `APPDIR` もなく、元環境記録もなければ環境をそのまま複製 | JavaScript の truthiness 判定。空でない文字列なら AppImage 扱い | 単独では偽。別途 `APPDIR` または `STRATA_ORIGINAL_ENV` が truthy なら別分岐 | `"0"` を含む任意の非空文字列も truthy。`APPIMAGE` がないときも `APPDIR` が truthy なら AppImage 扱い（`external-env.mjs:28-31,43-71`） |
| 診断情報 | `graphics_environment()` の出力に含めない | `std::env::var` で取得できれば `APPIMAGE=<値>` を記録 | 設定ありの空値なら `APPIMAGE=` として記録 | 非 Unicode 値は `var` が失敗するため含めない（`desktoplog.rs:186-194`） |

「無効値」は共通の値域として定義されていない。特に再起動先では空でない任意の値をパスとして起動しようとし、その成否は `spawn()` の結果で決まる。

## 有効になる条件

- Rust の再起動先選択は Linux のみでビルドされる supervisor 経路に属し、さらに `--window-child` が shell から起動されたものでない場合、すなわち updater による再起動経路で呼ばれる（`main.rs:47-48,869-881`）。
- この経路では旧 shell の終了待ちと二重起動確認を通過した後に `APPIMAGE` が評価される。待機時間切れや別の実行中 Strata があれば、再起動先を選ばず終了する（`supervisor.rs:330-355`）。
- 利用者向けコマンド名は Linux supervisor の案内文を作る場合にだけ参照される（`supervisor.rs:65-79,467-470`）。
- App Host 側の環境整理は `externalEnvironment()` を使う外部プログラム起動で有効。`APPIMAGE` が truthy、`APPDIR` が truthy、または `STRATA_ORIGINAL_ENV` が truthy なら AppImage 用分岐に入る。記録がある場合は記録値を基礎にし、なければ `APPIMAGE` と他の AppImage 専用変数を除去した環境を使う（`external-env.mjs:17-24,43-71`）。
- `externalEnvironment(env, extra)` の `extra` は最後に追加されるため、呼び出し元が明示的に `extra.APPIMAGE` を渡した場合は、整理後の環境に再び追加される（`external-env.mjs:64-71`）。
- macOS / Windows の main 起動分岐では Linux supervisor を通らない（`main.rs:871-884`）。App Host の環境 helper は共有 JavaScript 実装だが、ここでの判定対象は実行時に与えられる `env` であり、GPU backend 条件はない。

## 実行時の詳細

Rust 側に static cache はない。`command_name()` と `program_to_restart()` の呼び出し時に環境を読み、前者は UTF-8 変換可能性、後者は OS 文字列のまま取得する。通常の updater 再起動では `program_to_restart()` の戻り値を `Command::new` に渡し、`spawn()` 成功時は `started <path> again (process <pid>)` を shell log に書いて 0 を返す。失敗時は `could not start <path> again: <error>` を記録して 1 を返す（`supervisor.rs:319-327,352-383`）。

App Host 側は `externalEnvironment()` の既定引数で `process.env` を受け、呼び出しごとに判定する。AppImage でない場合は環境の複製を返す。AppImage の場合は `STRATA_ORIGINAL_ENV` の base64 記録を復元し、記録がなければ `withoutAppImage()` が `APPIMAGE` などの固定リストを削除する。呼び出し側はその結果を `spawn` / `execFile` の `env` として外部プログラムへ渡す。これは Strata が子プロセスに渡す環境の処理であり、外部プログラムが値をどう使うかは対象外（`external-env.mjs:28-71`）。

同じ名前への本番コード上の参照は、Linux supervisor の `command_name()` と再起動先選択、デスクトップ診断の `graphics_environment()`、App Host の外部環境 helper である。テスト、tester 用テンプレート、スクリプト中の `APPIMAGE` は実行時の環境読み取り実装として扱っていない。

## ログと測定値

測定値は該当しない。Strata が出す結果として、診断情報には `APPIMAGE=<値>` が含まれ得る。再起動成功時は `started ... again (process ...)`、再起動に失敗した場合は `could not start ... again: ...` が shell log に記録される。コマンド表示用文字列自体は `browser_chosen_line()` や crash log の案内文に埋め込まれる（`supervisor.rs:65-79,352-383,467-470`; `desktoplog.rs:186-194,241-259`）。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:47-48,869-884` — Linux 専用 supervisor と main 起動分岐。
- `apps/desktop/src-tauri/src/supervisor.rs:65-79,319-383,467-470` — コマンド名、更新後の再起動先、ログと案内。
- `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320` — 診断情報への収録。
- `apps/host/server/external-env.mjs:17-24,28-71` — AppImage 判定、専用変数の除去、元環境記録と追加環境。
- `apps/host/server/folder-dialog.mjs:117-126`, `apps/host/server/app-ui.mjs:38-59`, `apps/host/server/artifacts.mjs:5-6`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/open-text-file.mjs:26-29`, `apps/host/server/agent/harness-runtime.mjs:25-36` — helper の外部プログラムへの適用箇所。
