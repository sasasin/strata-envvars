# `STRATA_WINDOW_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Linux 版デスクトップアプリの window child が、App Host と通信し表示する loopback URL のポートを指定します。App Host 自身の待受ポートを選ぶ設定ではありません。通常起動時は shell が決めたポートを子プロセスへ渡すため、主に `--window-child` を直接起動した場合の入力値です。

## 値と判定

`run_window_process()` の開始時に `std::env::var("STRATA_WINDOW_PORT")` で一度読み、Rust の `u16` `parse()` で変換します（`apps/desktop/src-tauri/src/main.rs:1137-1140`）。

| 環境変数の状態 | 使用する値 |
|---|---|
| 未設定、または Unicode 文字列として取得できない値 | `PREFERRED_PORT` の `47831` |
| 空文字 | parse に失敗し、`47831` |
| 10 進 `u16` として parse できる値（`0`〜`65535`） | parse した値 |
| 不正な文字列、負数、範囲外など parse に失敗する値 | `47831` |

parse 失敗時の fallback は無言です。空白や余分な文字を取り除く処理はありません。設定値はプロセス開始時に一度評価され、その後の環境変更を再読しません。既定ポートの定義は `apps/desktop/src-tauri/src/main.rs:250-254` にあります。

## 有効になる条件

この読み取り関数は `#[cfg(target_os = "linux")]` で Linux 向けにだけコンパイルされ、Linux の起動処理で `--window-child` が指定された場合に呼ばれます（`apps/desktop/src-tauri/src/main.rs:1137-1139,865-874`）。Windows/macOS の embedded 起動経路では読み取られません（同 `:875-877,879-881`）。Linux でも `--browser` 起動は window child を作らず、値は使われません（`apps/desktop/src-tauri/src/supervisor.rs:385-393`）。

通常の Linux 起動では supervisor が App Host 用のポートを選び、その同じ数値を子プロセスの `STRATA_WINDOW_PORT` に設定します。既に起動中の Strata に接続するため別の window child を起動するときも、保存済み session のポートを明示設定します（`apps/desktop/src-tauri/src/supervisor.rs:229-238,267-276,341-365,385-394`）。したがって親環境に同名変数があっても通常起動ではこの明示値で上書きされます。shell が使うポートの選択は `pick_stable_port()` が設定ファイルと `PREFERRED_PORT` を使って行い、競合時は空きポートに切り替えます（`apps/desktop/src-tauri/src/main.rs:238-275`）。この選択に `STRATA_WINDOW_PORT` は関与しません。

## 実行時の詳細

読み取ったポートは `http://127.0.0.1:<port>` の WebView origin になり、ウィンドウが表示する Strata ページの接続先を決めます（`apps/desktop/src-tauri/src/main.rs:947-952,1179`）。また window child は同じポートの `/api/control/ui` に updater bridge を登録し、Linux のファイル drop 処理も同じホストへ要求します（同 `:1165-1179,1115-1127`）。つまり通常の supervisor が渡した App Host のポートと一致しない値では、表示やこれらの要求が正しい host に届かない可能性があります。

通常起動経路で child が終了コード 0 以外で終わると、supervisor は終了理由と crash log を知らせ、host を browser mode に切り替えます（`apps/desktop/src-tauri/src/supervisor.rs:303-314,420-431`）。updater bridge の登録要求に失敗した場合は stderr に `[strata] the app updater could not be registered with the host: ...` を出します（`apps/desktop/src-tauri/src/main.rs:1170-1177`）。一方、値が不正で既定値へ fallback したこと自体を示す Strata のログはありません。妥当な数値でも実際の host と異なる場合にどの表示エラーになるかは、WebView 等の外部実装に依存するため、Strata 固有の結果としては断定しません。

## 根拠

- 環境変数読み取り、parse、fallback: `apps/desktop/src-tauri/src/main.rs:1137-1140`
- Linux の window child 起動分岐: `apps/desktop/src-tauri/src/main.rs:865-877`
- 通常起動／既存 session からの child 起動時の環境設定: `apps/desktop/src-tauri/src/supervisor.rs:229-238,267-276,385-394`
- host port の独立した選択: `apps/desktop/src-tauri/src/main.rs:238-275`
- URL、updater 登録、drop 要求でのポート利用: `apps/desktop/src-tauri/src/main.rs:947-952,1115-1127,1165-1179`
- child 終了時の browser fallback: `apps/desktop/src-tauri/src/supervisor.rs:303-314,420-431`
