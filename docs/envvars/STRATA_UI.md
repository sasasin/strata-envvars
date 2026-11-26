# `STRATA_UI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Linux 版デスクトップアプリの起動時に、アプリ window の代わりに既定ブラウザーで App Host のページを開くかを選ぶ。Strata の shell が `browser` を選んだ場合は Host を browser mode として起動し、UI 制御 API 経由でページを開く。`STRATA_UI` はこの mode の選択だけを行い、エンジンやモデル設定は変えない。読み取りは Linux 専用の `main` 分岐にあり、Windows/macOS の埋め込み UI 起動経路では読まれない（`app/desktop/src-tauri/src/main.rs:929-945`、`app/desktop/src-tauri/src/supervisor.rs:43-55,515-550`）。

## 値と判定

起動時に `std::env::var("STRATA_UI").ok()` で Unicode 文字列を取得し、その値を `trim()` してから `to_ascii_lowercase()` を適用し、結果が文字列 `browser` と完全一致するか判定する（`app/desktop/src-tauri/src/main.rs:931-935`、`app/desktop/src-tauri/src/supervisor.rs:43-55`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux デスクトップ shell | window mode（通常のアプリ window） | `browser`、` Browser `、前後に空白を含む `BROWSER` | 空文字、`window`、`1`、`true`、`browser extra` |
| Windows/macOS 埋め込み UI | この変数は読み取られず、埋め込み window を起動 | 該当なし | 設定値はこの経路では無視される |

大文字小文字は ASCII の範囲で区別されず、前後の Unicode 空白は `trim()` で取り除かれる。中間の空白や余分な文字は許されず、真偽値・数値への変換もない。環境文字列が Unicode として取得できない場合、`.ok()` により未設定と同じ `None` 扱いになる。`--browser` は判定後の `browser` flag を true にするだけなので環境値を上書きして無効化する引数はない（`app/desktop/src-tauri/src/supervisor.rs:43-55`）。

## 有効になる条件

- `target_os = "linux"` のデスクトップアプリ起動経路であること。self-test は引数処理より先に終了し、`--window-child` は shell 起動処理を通らない（`app/desktop/src-tauri/src/main.rs:924-945`）。
- `STRATA_UI` が上表の値であるか、`--browser` を指定すること。どちらも満たさなければ通常は window mode になる（`app/desktop/src-tauri/src/supervisor.rs:43-55,515-555`）。
- `--help`、`--save-logs`、`--quit` は `run` 内で browser 起動より先に処理されるため、それぞれヘルプ表示、ログ保存、既存 Strata の終了が優先される（`app/desktop/src-tauri/src/supervisor.rs:478-501`）。
- すでに Strata が起動中の場合、新しい browser 指定は既存セッションの mode を変更しない。browser 指定または既存 session の mode が browser ならページを開き、それ以外では既存 window を前面化する経路になる（`app/desktop/src-tauri/src/supervisor.rs:430-449,499-501`）。

## 実行時の詳細

Linux の `main` が引数を解析する時に環境を一度読み、同じ呼び出しで `supervisor::parse_args` に渡す。関数内 cache はなく、この起動プロセスでの後からの環境変更を再評価しない（`app/desktop/src-tauri/src/main.rs:929-935`、`app/desktop/src-tauri/src/supervisor.rs:43-55`）。

新しい session では browser mode を `STRATA_UI_MODE=browser` として Host 子プロセスへ渡し、health check 後に session を記録する。続いて端末と desktop log に browser 用の案内文を出し、Host の `/api/control/ui` に `mode: browser` と `open: true` を送る。window mode では代わりに `--window-child` を起動する（`app/desktop/src-tauri/src/supervisor.rs:503-555`）。Host の `createAppUi` は `STRATA_UI_MODE` を読んで UI mode を決める。browser mode では app updater が利用不可とされ、ページを閉じても engine は止まらず、ページの Quit Strata または `--quit` が必要になる（`app/host/server/app-ui.mjs:64-86`、`app/desktop/src-tauri/src/supervisor.rs:58-63`）。

## ログと測定値

browser mode を選んだ場合は `Strata is open in your browser at http://127.0.0.1:<port>/. Closing the tab does not stop Strata: choose Quit Strata in the menu, or run <command> --quit.` を出す（`app/desktop/src-tauri/src/supervisor.rs:75-80,547-550`）。Host から開けたという応答がない場合は `[strata] No browser could be opened. Open http://127.0.0.1:<port>/ in your browser.` を stderr に出す。Host への制御要求自体が失敗した場合は `[strata] could not tell the host to open your browser (<error>). Open http://127.0.0.1:<port>/ in your browser.` を出す（`app/desktop/src-tauri/src/supervisor.rs:178-193`）。この環境変数による性能測定値は該当しない。

## 根拠

- `app/desktop/src-tauri/src/main.rs:929-945` — Linux のみ `STRATA_UI` を読み、self-test と window-child 経路を除いて supervisor を呼ぶ。
- `app/desktop/src-tauri/src/supervisor.rs:43-55` — 値の trim・ASCII 小文字化・完全一致判定と `--browser` の加算。
- `app/desktop/src-tauri/src/supervisor.rs:478-555` — help / logs / quit / 既存 session の優先、Host 子プロセスへの mode 伝達と browser 起動。
- `app/desktop/src-tauri/src/supervisor.rs:75-83,178-193` — browser 起動時の案内文と手動で URL を開くよう求める失敗経路。
- `app/host/server/app-ui.mjs:64-86` — Host が受け取った `STRATA_UI_MODE` の扱いと UI 状態。
