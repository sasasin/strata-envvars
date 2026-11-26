# `STRATA_ORIGINAL_ENV`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AppImage の `AppRun` が、Strata を起動した時点の環境全体を `env -0 | base64 -w0` で記録するための内部記録値です。Strata は主に、同梱ライブラリや GTK 設定が混ざった AppImage 環境をシステムの外部プログラムへそのまま渡さず、記録があれば起動元環境を復元します。対象はフォルダ選択、ファイル・URL opener、通知、assistant shell などの外部プロセス用環境です（`app/desktop/scripts/repack-appimage.sh:79-85`; `app/host/server/external-env.mjs:1-13,64-71`; 呼び出し例 `app/host/server/folder-dialog.mjs:112-126`, `app/host/server/app-ui.mjs:39-47,57-60`, `app/host/server/agent/harness-runtime.mjs:25-36`）。

もう一つの読み取り経路は Linux デスクトップアプリの更新後再起動です。shell が起動した通常の window child ではなく、updater から再起動された `--window-child` が Strata を再起動するときに、Rust supervisor が元環境を復元して新プロセスへ渡します（`app/desktop/src-tauri/src/main.rs:929-941`; `app/desktop/src-tauri/src/supervisor.rs:332-368`）。この変数自体は推論設定やモデル・GPU の選択を変えません。

## 値と判定

この値は真偽値や数値としては解釈されず、環境変数群を NUL 区切りにした Base64 記録として処理されます。作成側は AppImage の `AppRun` に hook がまだ無い場合に限り、`this_dir=` の後へ `export STRATA_ORIGINAL_ENV="$(env -0 | base64 -w0)"` を追加します（`app/desktop/scripts/repack-appimage.sh:79-85`）。

| 読み取り経路 | unset | 空文字 | 非空値・無効値 |
|---|---|---|---|
| Node `externalEnvironment` | `APPIMAGE` / `APPDIR` もなければ環境を複製して返す。どちらかがあれば復元を試し、失敗時は AppImage 用項目を除去した環境へ fallback | JavaScript の falsy 判定で記録なし。AppImage 外なら環境を複製し、AppImage 内なら除去 fallback | Node `Buffer.from(raw, 'base64')` で復号し UTF-8 化する。NUL 区切りの各項目のうち、`=` があり、その前の名前が空でないものを復元する。少なくとも一つ復元できればその環境を採用し、できなければ `null` として fallback。Node の Base64 decoder に渡す前の厳密な文字列・padding 検証はない（`app/host/server/external-env.mjs:28-40,60-70`） |
| Rust `original_environment`（更新再起動） | `std::env::var(...).ok()` が `None` となり、現在環境を引き継ぐ fallback | 空文字も `Some("")` として decoder に渡る。空バイト列を復号でき、空の環境 `Some(vec![])` になるため、新プロセスの環境を空にする | decoder は ASCII whitespace を除去し、末尾の `=` または `==` を取り除いてから Base64 alphabet 外の文字があれば失敗する。padding 形式や残り bit の妥当性までは検査しない。復号後は UTF-8 loss replacement を使い、NUL 区切りの `NAME=value` 項目を復元する。Base64 不正なら `None` となり fallback（`app/desktop/src-tauri/src/supervisor.rs:245-271,277-299,359-367`） |

Node 経路では `=` より後ろの値は追加の `=` を含めそのまま値にし、同じ名前が複数あれば後の項目が先の値を上書きします。Rust 経路は `split_once('=')` で名前と値に分け、復元した項目をベクターで保持します。どちらも各値に boolean・数値・大小文字の検査はありません（`app/host/server/external-env.mjs:33-39`; `app/desktop/src-tauri/src/supervisor.rs:282-291`）。

## 有効になる条件

- `repack-appimage.sh` で AppImage を再パックするとき、`AppRun` に名前がまだ現れない場合に記録用 export が挿入されます。既に名前があればこの hook は追加されません（`app/desktop/scripts/repack-appimage.sh:79-85`）。
- Node 側で外部プロセス用環境を作るとき、`APPIMAGE` または `APPDIR` が truthy、あるいは記録値が truthy なら復元・除去処理へ入ります。復元できれば記録環境を丸ごと元にし、復元できなければ現在環境から AppImage 専用名を削除し、`APPDIR` 配下の GTK/GDK/GIO/GST/GI/GSETTINGS/WEBKIT 値と path-list 項目を清掃します（`app/host/server/external-env.mjs:17-26,43-57,60-71`）。この条件は GPU backend や model state に依存しません。
- Node 経路は helper 呼び出し時に渡された環境を使います（引数省略時はその時点の `process.env`）。`extra` が指定される場合は復元・清掃結果より優先して最後にマージされます。すでに起動した子プロセスには後から反映されません（`app/host/server/external-env.mjs:28-30,44-46,64-70`）。
- Rust 側の読み取りは Linux の `--window-child` が shell から起動されたものではないと判定され、`restart_after_update()` に入ったときだけ行います。Linux 以外や通常の shell 起動経路ではこの読み取りに進みません（`app/desktop/src-tauri/src/main.rs:929-944`; `app/desktop/src-tauri/src/supervisor.rs:232-237,336-359`）。
- Rust で記録中に `STRATA_ORIGINAL_ENV` 自体が入れ子で見つかると最大 8 回までその記録をたどります。各階層の記録キーは復元結果から除外されます。8 回の上限まで到達した場合、それ以上の内側記録は読まれません（`app/desktop/src-tauri/src/supervisor.rs:277-299`）。

## 実行時の詳細

Node の `recordedOriginal(env)` は呼び出しごとに `env.STRATA_ORIGINAL_ENV` を読み、値を保存する cache はありません。復元した元環境が一項目以上あれば現在の AppImage 環境とマージせず置き換えます。復元に失敗した場合の `withoutAppImage()` は `APPIMAGE_ONLY` の固定名から `STRATA_ORIGINAL_ENV` も削除します。環境の生成結果は複数の外部プロセス起動経路に渡されますが、Strata 同梱の Node/Python/engine 自身の環境を書き換える処理ではありません（`app/host/server/external-env.mjs:17-26,28-57,67-71`; caller: `app/host/server/chat-files.mjs:92`, `app/host/server/artifacts.mjs:6`, `app/host/server/open-text-file.mjs:28`）。

Rust の `restart_after_update()` はこの変数を一度読みます。復元成功時は `env_clear().envs(vars)` で再起動先の環境を復元値に置き換えます。変数が unset、非 Unicode で `std::env::var` が失敗、または decoder が失敗した場合は現在環境を引き継ぎ、`STRATA_WINDOW_PORT`、`STRATA_SHUTDOWN_TOKEN`、`STRATA_SHELL_PID` を取り除きます。この fallback 分岐では `STRATA_ORIGINAL_ENV` 自身は削除対象に含まれません（`app/desktop/src-tauri/src/supervisor.rs:359-367`）。

Rust decoder が Base64 として受理した内容に `=` を含む NUL 区切り項目がない場合も、失敗ではなく空の復元環境になります。したがって空文字は Node 経路では復元不能扱い、Rust の更新再起動経路では空環境として成功扱いになり、両経路で異なります（`app/host/server/external-env.mjs:30-40,69-70`; `app/desktop/src-tauri/src/supervisor.rs:277-299,359-367`）。

## ログと測定値

Node 側にこの記録値の復元成功・失敗を出す専用ログはありません。Rust の更新再起動は、処理開始時に `started as the app window by the app updater, not by Strata (old app process {old:?}): restarting Strata` を記録し、成功時は `started {program} again (process {id})`、spawn 失敗時は `could not start {program} again: {error}` を記録します。記録値の有無や decode 結果だけを示すログはありません（`app/desktop/src-tauri/src/supervisor.rs:336-339,358-384`）。

元 shell の停止待ちが期限を超える場合は `the old Strata (process {pid}) did not stop within {seconds} s: not starting a second one` を記録して終了コード 0、別の live session がある場合もログを記録してコード 0 で戻ります。再起動先の特定に失敗した場合、または spawn に失敗した場合はコード 1 です（`app/desktop/src-tauri/src/supervisor.rs:340-356,376-384`）。この環境変数に関する性能測定値はありません。

## 根拠

- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage 起動元環境の記録を launcher に追加。
- `app/host/server/external-env.mjs:15-26,28-40,43-57,60-71` — 記録名、復元処理、AppImage 環境判定、外部環境の選択。
- `app/host/server/folder-dialog.mjs:112-126`, `app/host/server/app-ui.mjs:39-47,57-60`, `app/host/server/agent/harness-runtime.mjs:25-36` — 外部プロセス環境への適用例。
- `app/desktop/src-tauri/src/main.rs:929-944` — Linux window-child と updater 再起動の分岐。
- `app/desktop/src-tauri/src/supervisor.rs:245-271,274-299,336-384` — Rust decoder、最大 8 階層の復元、子プロセス環境と観測可能な結果。
