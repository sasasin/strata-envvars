# `STRATA_WINDOW_PORT`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象は Strata 所有ソース。外部ライブラリの環境変数の動作は対象外。

## 役割

Linux Desktop のウィンドウ専用子プロセスが、App Host のページを開き、ホストへの UI updater 登録やファイルドロップ転送を行うときに接続先ポートを決めます。ホストを起動する親プロセスは別にポートを選び、子プロセス起動時にその値をこの環境変数として渡します。したがって通常の Desktop 起動では、利用者の親プロセス環境にある値でホストの待受ポートを選ぶ設定ではありません。

## 値と判定

Linux の `run_window_process()` が `std::env::var()` で Unicode 文字列を取得し、Rust の `str::parse::<u16>()` で文字列全体を unsigned 16-bit 整数として parse します。

| 環境変数の状態 | 子プロセスが使うポート |
|---|---|
| 未設定、または Unicode 文字列として取得できない | `PREFERRED_PORT` の `47831` |
| 空文字、数値以外、前後に空白がある文字列、`u16` 範囲外 | parse 失敗となり `47831` |
| `0`〜`65535` の十進整数として全体を parse できる文字列 | parse された値 |

負の表記や末尾の文字を含む値は `u16` 全体 parse に失敗します。明示的な空文字にも特別扱いはありません。親プロセスが通常の起動フローで生成するポートは `pick_stable_port()` 由来で、環境変数が示す任意値ではありません。

`0` も `u16` としては parse できますが、通常の親プロセスは `pick_stable_port()` で実際に使えるポートを選ぶため、子プロセスへ `0` を渡しません。

## 有効になる条件

- `run_window_process()` は `#[cfg(target_os = "linux")]` の Linux 専用実装です。Windows/macOS ではこの変数を読みません。
- Linux で通常起動すると、親の supervisor がポートを選んで `--window-child` 子プロセスに `STRATA_WINDOW_PORT` を設定します。既存セッションへウィンドウを再表示する子プロセスにも、保存済みセッションポートを設定します。
- `--browser` 起動ではウィンドウ子プロセスを作らないため、この変数を使うプロセスは起動されません。
- 子プロセスを直接 `--window-child` 付きで起動した場合は、継承された環境値を読みます。無効値や未設定なら固定値 `47831` へ fallback します。ホストが別ポートで動作中なら接続先が一致しない可能性があります。

## 実行時の詳細

Linux supervisor は `pick_stable_port()` で `127.0.0.1:47831` を bind して空きを確認し、使用中なら `127.0.0.1:0` で取得した空きポートへ fallback します。このポートで App Host を起動し、ホストの health check 後に、同じポートを `STRATA_WINDOW_PORT` としてウィンドウ子プロセスへ渡します。再起動・再表示の経路でも supervisor が保存済みセッションのポートを子へ設定します。

子プロセスは起動時に一度この値を読み、`open_window()` の URL を `http://127.0.0.1:<port>` にします。同じ値は updater 登録先 `/api/control/ui` と、Linux のファイルドロップ転送先 `/api/app/drop` にも使われます。プロセス起動後の環境変更を再読するコードはありません。値が無効で fallback した子プロセスは、親が起動した Host の実際のポートと異なる接続先を使い得ます。

`docs/DETAILS.md` は Desktop アプリの API アドレスについて、通常は `47831`、使用中なら次の空きポートと記しています。この説明は supervisor のポート選択と整合します。そこで説明されるポート選択は `STRATA_WINDOW_PORT` によるものではなく、親側の `pick_stable_port()` です。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:249-263`: 優先ポート `47831` と、競合時に空きポートを取得する `pick_stable_port()`。
- `apps/desktop/src-tauri/src/supervisor.rs:337-365,372-383,390-399`: 親がポートを選び、Host を起動し、初回ウィンドウ子プロセスへ同じポートを渡す流れ。
- `apps/desktop/src-tauri/src/supervisor.rs:229-238,267-287`: 既存セッションのウィンドウを再表示する場合にもセッションポートを子へ渡す。
- `apps/desktop/src-tauri/src/main.rs:1104-1150`: Linux 専用ウィンドウプロセスでの環境変数の parse と、updater 登録・ウィンドウ起動。
- `apps/desktop/src-tauri/src/main.rs:919-922,1085-1093`: ポートから loopback のウィンドウ URL とファイルドロップ転送 URL を作る処理。
- `docs/DETAILS.md:1110-1112`: Desktop の API アドレスが通常 `47831` または次の空きポートであるという説明。
