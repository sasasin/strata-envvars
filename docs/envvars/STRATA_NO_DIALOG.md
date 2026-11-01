# `STRATA_NO_DIALOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

デスクトップアプリが起動時の致命的な失敗を報告するとき、ユーザー向けエラー通知を抑制します。Windows ではメッセージボックス、macOS では `show_error` 経由の stderr 出力が対象です。失敗ログやクラッシュファイルの記録、失敗終了は抑制しません。

## 値と判定

値の文字列や数値は parse せず、Rust の `std::env::var_os(...).is_none()` で設定の有無だけを判定します（`apps/desktop/src-tauri/src/desktoplog.rs:363-370`）。

| 状態 | `dialog` に対する効果 |
|---|---|
| 未設定 | 呼び出し元が渡した `dialog` を維持 |
| 設定済み（空文字、`0`、`false`、その他を含む） | `dialog` を false にする |

設定値による fallback や境界値はありません。内部引数 `dialog` が false の場合も環境変数では true に戻りません。CLI 引数や別の環境変数との優先順位はなく、自己テストの内部判定が先に無効化した場合は、環境変数の有無にかかわらず無効です（`apps/desktop/src-tauri/src/main.rs:846-850`）。

## 有効になる条件

- `main` が `#[cfg(not(target_os = "linux"))]` の `desktoplog::init_startup(...)` を通る Windows / macOS のデスクトップ実行が対象です。Linux はこの関数を呼びません（`apps/desktop/src-tauri/src/main.rs:847-850,852-877`）。
- `--self-test[=path]` の自己テストでは `self_test_path(&args).is_none()` が false となり、引数 `dialog` が false になります。この経路では環境変数を設定しなくてもダイアログは出ません（`apps/desktop/src-tauri/src/main.rs:841-850,860-863`）。
- 環境変数が通知を抑えるのは `report_failure` が保存済み `run.dialog` を確認する箇所です。Windows の `show_error` はネイティブメッセージボックス、Windows 以外の実装は stderr 出力です。よって macOS でもフラグは `show_error` の stderr 通知を抑えます（`apps/desktop/src-tauri/src/desktoplog.rs:449-470,472-488`）。

## 実行時の詳細

`main` の起動時に `init_startup` が環境変数を読み、結果を `RUN` の `Run { log, dialog }` に保存します。通常の main 経路では起動時の一度だけ評価され、プロセス起動後の環境変更では保存済み状態は変わりません（`apps/desktop/src-tauri/src/main.rs:846-850`; `apps/desktop/src-tauri/src/desktoplog.rs:348-370`）。

起動失敗または panic の報告時、Strata は常に `START FAILED: ...` を run log に書き、可能ならクラッシュファイルを書き、そのパスもログに記録します。その後 `run.dialog` が true の場合に限り、初回の報告で `show_error` を呼びます。Windows では「Strata could not start.」などの本文を持つメッセージボックス、Windows 以外では `[strata] ...` の stderr 出力です。`STRATA_NO_DIALOG` が設定されていれば `show_error` 呼び出しはスキップされますが、ログとクラッシュファイルの処理は継続します（`apps/desktop/src-tauri/src/desktoplog.rs:472-488`）。

明示的な起動失敗 `startup_failed` は報告後に終了コード 1 で終了します。panic は panic hook から報告処理を行います（`apps/desktop/src-tauri/src/desktoplog.rs:491-513`）。この環境変数は終了や panic 自体を無効化しません。

## 根拠

- 唯一の値読み取り箇所と `dialog` 保存: `apps/desktop/src-tauri/src/desktoplog.rs:363-370`。
- 呼び出し時期、Linux 除外、自己テストの引数判定: `apps/desktop/src-tauri/src/main.rs:838-877`。
- 起動失敗時のログ、クラッシュファイル、条件付き表示: `apps/desktop/src-tauri/src/desktoplog.rs:472-495`。
- Windows のメッセージボックスと他 OS の stderr 経路: `apps/desktop/src-tauri/src/desktoplog.rs:449-470`。
- panic hook からの報告: `apps/desktop/src-tauri/src/desktoplog.rs:497-513`。
