# `CARGO_PKG_VERSION`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

デスクトップ shell をビルドするとき Cargo が与えるパッケージ版を、Rust の `env!` マクロでコンパイル時に文字列として埋め込む。`app/desktop/src-tauri/Cargo.toml` の `version` はこの commit で `0.2.21`。shell はその文字列を起動ログ、クラッシュレポート、保存ログに記録し、App Host 子プロセスには `STRATA_APP_VERSION` として渡す。実行中の利用者が `CARGO_PKG_VERSION` を設定しても、ビルド済み shell の値は切り替わらない。

## 値と判定

実装での参照は `std::env::var` 等の実行時読み取りではなく `env!("CARGO_PKG_VERSION")`。Cargo package metadata 由来の値をビルド時に取り込み、文字列として使う。数値変換、文字列比較、空文字判定、範囲制限は Strata 側にない。Cargo がこの変数を供給しない状態でコンパイルすると `env!` の展開が成立しない。通常の Cargo package build では manifest の版 `0.2.21` が埋め込まれる。

| 条件 | 未設定 | 値の扱い | 無効値 |
|---|---|---|---|
| `app/desktop/src-tauri` の Cargo build | Cargo が package variable を供給しないと `env!` 展開時にビルドエラー | Cargo が与えた文字列をそのまま埋め込む（この commit の manifest では `0.2.21`） | Strata の shell 側に追加検証なし。実行時の空文字・`0`・`true` は読み取られない |

## 有効になる条件

- デスクトップ shell を Cargo でビルドし、`env!` のコンパイル時展開を行うこと。ソース checkout の他の実行経路がこの値を実行時に読み取るわけではない。
- 起動ログへの記録は `supervisor::run` が通常の起動経路へ進み `Log::open` が呼ばれる場合に行われる。ログファイルを開けなかった場合、`Log::line` はファイルがない状態を許容するため、版の行も保存されない。
- クラッシュレポートと `--save-logs` のファイルは、それぞれ該当する失敗処理または保存処理が呼ばれたときだけ作られる。
- App Host への転送は supervisor が Host を起動する経路で行われる。shell の browser/window モードにかかわらず `STRATA_APP_VERSION` を設定し、browser 経路では別途 `STRATA_UI_REASON` も設定する。

## 実行時の詳細

この値はコンパイル時に埋め込まれ、プロセス起動後の環境変更では変わらない。通常起動では `Log::open` が `Strata desktop <version> starting (pid <pid>)` をログファイルへ書く。クラッシュログには `crash_report` または `startup_report` の版欄として使われ、`--save-logs` が作るテキストにも `App <version>` として含まれる。ログ書き込み結果は無視される箇所があり、版情報の記録失敗だけで起動を失敗させる処理は確認できない。

App Host の起動コマンドには埋め込み値を `STRATA_APP_VERSION` として設定する。Host 側はこの別名を読み、アプリ版表示や更新確認に使う。Host の `appVersionFrom` は値を trim したうえで `数字.数字.数字` と任意の `-`/`+` suffix の形式に合う場合だけ採用し、不適合なら checkout の Cargo.toml を読み、そこから有効版を得られなければ `dev` にする。これは転送先 `STRATA_APP_VERSION` の処理であり、`CARGO_PKG_VERSION` を実行時に読み直す処理ではない。

## 根拠

- `app/desktop/src-tauri/Cargo.toml:1-4` — package 名と manifest version `0.2.21`。
- `app/desktop/src-tauri/src/desktoplog.rs:122-140` — 起動ログへの埋め込み値の記録とファイル書き込み。
- `app/desktop/src-tauri/src/desktoplog.rs:281-289` — 通常のクラッシュログへの埋め込み値の使用。
- `app/desktop/src-tauri/src/desktoplog.rs:310-319` — 保存ログの `App` 行への埋め込み値。
- `app/desktop/src-tauri/src/desktoplog.rs:440-446` — 起動失敗レポートへの埋め込み値。
- `app/desktop/src-tauri/src/supervisor.rs:479-485, 503-530` — `--save-logs` の分岐、起動ログ生成、Host 起動時の `STRATA_APP_VERSION` 設定。
- `app/host/server/app-version.mjs:8-18` — Host が転送先環境変数を検証し、checkout manifest または `dev` に fallback する処理。
- `app/host/server/index.mjs:149-151, 1513-1514` — Host の app version 組み立てと更新確認への適用。
