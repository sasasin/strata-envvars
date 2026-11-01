# `XDG_CURRENT_DESKTOP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata デスクトップアプリが、Linux のウィンドウプロセス障害レポートと `--save-logs` の診断ファイルに、現在のグラフィックスセッション情報の一項目として値を記録します。Strata のウィンドウ描画や backend 選択をこの値で切り替える処理はありません。ソース中の `graphics_environment()` は複数の環境変数名を列挙し、値を診断用の文字列に集めます（`apps/desktop/src-tauri/src/desktoplog.rs:186-194`）。

## 値と判定

`graphics_environment()` は列挙された名前ごとに `std::env::var(name)` を呼び、成功した場合だけ `  NAME=value` 形式の行を作ります。値の parse、trim、大小文字変換、既定値設定はありません（`apps/desktop/src-tauri/src/desktoplog.rs:187-194`）。

| 状態 | Strata の診断出力 |
|---|---|
| 未設定 | `std::env::var` が失敗するため、この項目の行を出力しない |
| 空文字 | 成功し、`  XDG_CURRENT_DESKTOP=` と出力する |
| Unicode の値 | 文字列をそのまま `  XDG_CURRENT_DESKTOP=<値>` として出力する |
| Unicode 文字列にできない値 | `std::env::var` がエラーとなり、この項目の行を出力しない |

Strata 独自の有効値・無効値、数値境界、fallback はありません。この値を CLI 引数や別の Strata 環境変数と比較する処理もありません。

## 有効になる条件

この読み取りが起きるのは診断情報を組み立てる経路です。

- Linux でウィンドウプロセスが起動できない、または起動後に異常終了すると、shell が `window_failed()` から crash log を作成します。レポートには `Graphics session:` と `graphics_environment()` の行が含まれます（`apps/desktop/src-tauri/src/supervisor.rs:303-313`; `apps/desktop/src-tauri/src/desktoplog.rs:241-259`）。
- Linux デスクトップ実行ファイルに `--save-logs` を渡すと、ログ収集処理が `save_logs()` を呼びます。その出力の `Graphics session:` 欄にも同じ環境情報が含まれます（`apps/desktop/src-tauri/src/main.rs:865-873`; `apps/desktop/src-tauri/src/supervisor.rs:316-333`; `apps/desktop/src-tauri/src/desktoplog.rs:310-340`）。

通常の起動時にこの値を読んで表示動作を変える分岐はありません。`--browser`、`STRATA_UI`、モデル状態、GPU backend との優先順位や相互作用も、この読み取り箇所にはありません。

## 実行時の詳細

`XDG_CURRENT_DESKTOP` の直接参照は `desktoplog.rs:189` の名前一覧だけです。値は同ファイルの `graphics_environment()` が名前を引数にして `std::env::var` を呼ぶことで読み取られます（同 `:187-194`）。helper は `static` cache を持たず、診断レポートを作るたびに現在のプロセス環境から読みます。読み取り値を変更・転送する処理もありません。

ウィンドウ障害時の crash log は `desktop-crash-...log` に書かれ、shell は障害を知らせた後にブラウザーへ切り替えます。この値が欠けていても値の取得自体から警告や失敗は発生しません（`apps/desktop/src-tauri/src/supervisor.rs:303-313`; `apps/desktop/src-tauri/src/desktoplog.rs:281-289`）。`--save-logs` は成功時に保存先を stdout に表示し、保存に失敗した場合は `[strata] could not save the logs: ...` を stderr に出して終了コード 1 を返しますが、これはファイル保存の失敗経路です（`apps/desktop/src-tauri/src/supervisor.rs:322-332`）。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — 環境変数名一覧と動的な `std::env::var` 読み取り。
- `apps/desktop/src-tauri/src/desktoplog.rs:241-259` — crash report の `Graphics session` への追加。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-340` — `--save-logs` 用ファイルへの追加。
- `apps/desktop/src-tauri/src/supervisor.rs:303-313,316-333` — Linux の障害時および CLI ログ収集経路。
- `apps/desktop/src-tauri/src/main.rs:865-873` — Linux shell が CLI オプションを処理する経路。
