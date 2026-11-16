# `STRATA_WINDOW_PORT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux デスクトップ版のウィンドウ子プロセスが、接続する App Host の loopback ポートを得るために読みます。値は `run_window_process` 内で `u16` に変換され、WebView の URL と、updater 登録・ファイルドロップ転送の HTTP 宛先に使われます（`apps/desktop/src-tauri/src/main.rs:1228-1231,1265-1279`; 同 `:969-972,1206-1214`）。

通常起動時にこの環境変数でポートを選ぶ設計ではありません。Linux supervisor は先に設定・優先ポートまたは空きポートを選び、App Host をそのポートで起動した後、`STRATA_WINDOW_PORT` を同じ値に設定してウィンドウ子プロセスを起動します。したがって、親プロセスに利用者が設定した値は子プロセス起動時に上書きされます（`apps/desktop/src-tauri/src/main.rs:254-278`; `apps/desktop/src-tauri/src/supervisor.rs:501-553`）。

## 値と判定

`std::env::var` で文字列を取得し、`parse::<u16>()` で文字列全体を符号なし 16-bit 整数として解析します。未設定、Unicode 文字列として取得できない値、解析できない値はすべて `47831` に fallback します。空文字、数字以外を含む文字列、`u16` の範囲外は解析失敗です。範囲内の `0` も解析としては有効で、クランプや追加検証はありません。数値の後ろに文字列を付けた値は全体の解析に失敗します（`apps/desktop/src-tauri/src/main.rs:258,1230`）。

| 条件 | unset / 取得・解析失敗 | 設定時に受理される値 | 無効になる値の例 |
|---|---|---|---|
| Linux のウィンドウ子プロセス | `47831` | `u16` の範囲 `0..=65535` に parse できる整数文字列（例 `47831`, `0`, `65535`） | 空文字、`65536`, `-1`, `47831x`, 前後に空白を含む値 |
| Windows / macOS | この環境変数の読み取り箇所なし | 該当なし | 該当なし |

## 有効になる条件

- 読み取り箇所は `#[cfg(target_os = "linux")]` の `run_window_process` に限られます。Windows/macOS の `run_embedded` 経路ではこの変数を読みません（`apps/desktop/src-tauri/src/main.rs:1225-1230,883-885`）。
- Linux の通常起動では supervisor が `pick_stable_port()` でポートを選び、その値を Host 起動とウィンドウ子プロセスの双方へ渡します。子プロセス起動時の `.env("STRATA_WINDOW_PORT", port.to_string())` が親環境の同名値を置き換えるため、通常の `STRATA_WINDOW_PORT` 設定は選択結果に影響しません（`apps/desktop/src-tauri/src/main.rs:264-278`; `apps/desktop/src-tauri/src/supervisor.rs:501-553`）。
- CLI にポート指定引数はなく、supervisor のポート選択は設定ファイル `shell-prefs.json` の選択値、なければ `47831` を基準にします。希望ポートが使用中なら別の空きポートに切り替えます（`apps/desktop/src-tauri/src/main.rs:254-278`; `apps/desktop/src-tauri/src/shell.rs:33-58`; `apps/desktop/src-tauri/src/supervisor.rs:43-55`）。
- `--browser` で起動した場合、supervisor はウィンドウ子プロセスを作成しないため、この読み取りも起きません（`apps/desktop/src-tauri/src/supervisor.rs:545-553`）。

## 実行時の詳細

環境変数は `run_window_process` の開始時に一度読み、ローカル変数 `port` に保持します。関数内で再読したり static cache したりしないため、起動後の環境変更はこのプロセスの当該ポート値に反映されません（`apps/desktop/src-tauri/src/main.rs:1228-1231`）。

通常の Linux 起動では supervisor が Host 用のポートを選択し、Host の起動・health check 後にそのポートをセッションへ保存してからウィンドウ子プロセスへ渡します。ウィンドウは `http://127.0.0.1:{port}` を開き、同じ `port` を updater bridge 登録およびドロップしたファイルの Host への POST に使います（`apps/desktop/src-tauri/src/supervisor.rs:501-553`; `apps/desktop/src-tauri/src/main.rs:1265-1279,969-972,1206-1214`）。

通常起動の選択元は `STRATA_WINDOW_PORT` ではなく `shell::wanted_port(&shell::read_prefs(), 47831)` です。ポートが使用中なら `pick_port()` で空きポートを取得し、通知情報を設定します（`apps/desktop/src-tauri/src/main.rs:254-278`）。

## ログと測定値

この変数の parse 失敗や fallback を知らせる専用ログはありません（読み取り式にログ分岐がありません: `apps/desktop/src-tauri/src/main.rs:1230`）。通常の supervisor 起動時に選択ポートを環境変数へ設定する処理もログ文言を出しません（`apps/desktop/src-tauri/src/supervisor.rs:388-398,550-553`）。ポートの競合時に選択したポートを通知する処理はありますが、これは設定済みポート候補と bind 結果に基づくもので、この環境変数の判定ログではありません（`apps/desktop/src-tauri/src/main.rs:260-278`）。測定値は該当しません。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:1225-1231` — Linux のウィンドウ子プロセスと変数の読み取り、`u16` 解析、fallback。
- `apps/desktop/src-tauri/src/main.rs:254-278` — 通常起動での優先ポート・設定値・競合時 fallback。
- `apps/desktop/src-tauri/src/supervisor.rs:501-553` — supervisor の Host 起動・health check と、子プロセスへのポート設定。
- `apps/desktop/src-tauri/src/shell.rs:33-58` — 設定ファイルの読取と通常起動で使うポートの決定。
- `apps/desktop/src-tauri/src/main.rs:969-972,1265-1279` — ウィンドウ origin と Host への updater 登録。
- `apps/desktop/src-tauri/src/main.rs:1206-1214` — ドロップ転送先。
