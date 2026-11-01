# `STRATA_DESKTOP_TEST_PANIC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata Desktop の起動時失敗処理（panic hook、ログ、クラッシュ記録、エラーダイアログ）を、正常に起動する環境でも意図的な panic で確認するためのテスト用スイッチです。値に応じた通常機能の設定ではなく、設定されているとアプリ起動を中断します。候補一覧の名前どおり、Strata が実際に環境から読み取る変数です。

## 値と判定

`std::env::var_os(...).is_some()` で設定の有無だけを判定し、値の文字列化・parse・比較はしません（`apps/desktop/src-tauri/src/main.rs:897-901`）。

| 状態 | 判定と結果 |
|---|---|
| 未設定 | 条件は false。意図的な panic は起きず、通常の setup 処理へ進む |
| 設定あり | 条件は true。空文字や `0` を含め、値の内容によらず意図的に panic する |

値は Tauri の setup callback が実行される時点で読み取られます。static cache はなく、環境変数を読むのはこの箇所だけです。起動後に値を変えても、既に発生した判定には影響しません。CLI 引数や他の環境変数による値の上書き・優先順位はありません。

## 有効になる条件

- `run_embedded()` が呼ばれる非 Linux の Desktop 起動経路で有効です。同関数は `#[cfg(not(target_os = "linux"))]` で定義され、`main()` の同じ条件の分岐から呼ばれます（`apps/desktop/src-tauri/src/main.rs:875-881`）。実際の対象は Windows/macOS の通常の組み込みアプリ起動です。
- Linux では `main()` が Linux supervisor / window-process 経路へ進み、非 Linux 専用の `run_embedded()` およびこの判定は使われません（`apps/desktop/src-tauri/src/main.rs:865-876`）。
- `--self-test` または `--self-test=<path>` が指定されると、`main()` は `run_self_test()` の後にプロセスを終了するため、`run_embedded()` の setup に到達せず、この変数による panic は起きません（`apps/desktop/src-tauri/src/main.rs:607-623,860-863`）。
- ビルド設定用の専用 macro や feature gate はこの判定にありません。値が設定されていても、上記の実行経路を通らない場合は作用しません。

## 実行時の詳細

通常の非 Linux 起動では `main()` が先に `desktoplog::init_startup(...)` を呼び、run log を開いて panic hook を登録します。その後 `run_embedded()` が Tauri アプリを構築し、setup callback の先頭で環境変数を確認します。設定ありなら `panic!("STRATA_DESKTOP_TEST_PANIC is set: the app panics on purpose")` が実行され、App Host の起動処理より前に失敗します。従ってこの経路では、環境変数を子プロセスへ渡す処理はなく、App Host も起動されません（`apps/desktop/src-tauri/src/main.rs:849-851,879-905`）。

panic hook は panic の本文と発生位置を `the app stopped unexpectedly: ...` の形式にして `report_failure()` へ渡します。そこでは run log に `START FAILED: ...` を記録し、起動失敗ファイルの作成を試みます。通常起動ではダイアログも表示します（`apps/desktop/src-tauri/src/desktoplog.rs:363-371,472-488,499-513`）。macOS では `show_error()` が stderr に `[strata] ...` を出し、Windows ではエラーダイアログを表示します（同 `desktoplog.rs:452-470`）。release profile は `panic = "abort"` であり、hook の処理後に panic によってプロセスが中断されます（`apps/desktop/src-tauri/Cargo.toml:27-31`）。終了コードはこの変数の分岐では明示的に設定されていません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:691`。
- 唯一の完全一致参照と値判定、panic 本文: `apps/desktop/src-tauri/src/main.rs:897-901`。
- 起動時の分岐、self-test の先行終了、OS 条件: `apps/desktop/src-tauri/src/main.rs:849-876`、`apps/desktop/src-tauri/src/main.rs:607-623`。
- run log・panic hook・失敗記録: `apps/desktop/src-tauri/src/desktoplog.rs:363-371,472-488,499-513`。
- release の panic 設定: `apps/desktop/src-tauri/Cargo.toml:27-31`。
