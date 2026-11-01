# `STRATA_UI`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの状態は `main...origin/main` で、未コミット変更はありません。

## 役割

Linux のデスクトップ版で、Strata の画面をアプリ内ウィンドウで表示するか、既定のブラウザーで開くかを選びます。`STRATA_UI=browser` は `--browser` と同じ扱いで、ブラウザー表示を要求します。それ以外の値は通常のウィンドウ表示を選びます。Linux 以外のデスクトップ起動経路ではこの変数を読みません。

ブラウザー表示を選ぶと、Linux supervisor は App Host に `STRATA_UI_MODE=browser` と `STRATA_UI_REASON=chosen` を設定します。ページはブラウザーで開き、タブを閉じてもホストとエンジンは終了しません。アプリ内ウィンドウ専用のアプリ更新機能は使えず、終了には画面の「Quit Strata」または `--quit` を使います（`apps/desktop/src-tauri/src/supervisor.rs:353-388`、`apps/host/server/app-ui.mjs:63-85`）。

## 値と判定

起動時に `std::env::var("STRATA_UI").ok()` で文字列を取得します。値は前後の空白を `trim()` で除き、ASCII 小文字化した後、文字列全体が `browser` と一致する場合だけブラウザー表示になります（`apps/desktop/src-tauri/src/main.rs:869`、`apps/desktop/src-tauri/src/supervisor.rs:43-55`）。

| 値 | 判定 |
|---|---|
| 未設定 | ウィンドウ表示 |
| 空文字または空白のみ | ウィンドウ表示 |
| `browser`（大小文字を問わない） | ブラウザー表示 |
| 前後に空白を含む `browser` | ブラウザー表示 |
| `window`、`1`、`true`、`browser-extra` など、正規化後に `browser` と完全一致しない値 | ウィンドウ表示 |
| Unicode 文字列として取得できない値 | `.ok()` により `None` となり、ウィンドウ表示 |

無効値への警告やエラーはありません。数値変換や範囲判定もありません。

## 有効になる条件

- `main.rs` の `#[cfg(target_os = "linux")]` ブロック内だけで読み取られ、Linux の supervisor 経路に適用されます。Windows と macOS は `run_embedded()` へ進み、この変数を参照しません（`apps/desktop/src-tauri/src/main.rs:43-44,867-876`）。
- 起動引数 `--browser` は `browser` フラグを `true` にします。環境変数からすでに `true` になっている場合に、それを戻す CLI 引数はありません。したがって環境変数と CLI のどちらかがブラウザー表示を要求すれば有効です（`apps/desktop/src-tauri/src/supervisor.rs:43-55`）。
- `--help`、`--save-logs`、`--quit` は `run()` の先行分岐で処理され、通常の新規起動モード選択には進みません。既存セッションが見つかった場合、ブラウザー指定は新しいホストを起動せず、その既存ホストのページをブラウザーで開く要求として使われます（`apps/desktop/src-tauri/src/supervisor.rs:317-339`）。
- `--window-child` では supervisor を起動せず、ウィンドウプロセスへ進みます。この経路では `STRATA_UI` の判定結果は表示モード選択に使われません（`apps/desktop/src-tauri/src/main.rs:869-874`）。

## 実行時の詳細

環境変数は各 Linux プロセスの起動経路で `parse_args()` に渡され、その呼び出し時に一度判定されます。値をキャッシュする static 変数はなく、同じプロセス内で後から環境を変更して再評価する経路もありません。ウィンドウ子プロセスでは環境変数を再び解析しますが、`--window-child` によって supervisor を迂回します（`apps/desktop/src-tauri/src/main.rs:869-874`）。

新規起動では判定結果から `window` / `browser` の mode を決め、App Host 起動時に `STRATA_UI_MODE` を設定します。ブラウザー指定時だけ `STRATA_UI_REASON=chosen` も設定し、端末とログにブラウザーの URL と終了方法を出して、ホストにブラウザー表示を依頼します（`apps/desktop/src-tauri/src/supervisor.rs:341-388`）。`STRATA_UI` 自体を App Host に渡してはいません。ホスト側は `STRATA_UI_MODE` を読み、UI 状態に `mode=browser`、`canQuit=true`、`appUpdate=unavailable` を反映します（`apps/host/server/app-ui.mjs:63-85`）。

ブラウザー起動に失敗すると、端末に手動で開く URL を案内します。既定のウィンドウ起動を選んだ後でウィンドウプロセスが開始できない、または異常終了した場合もホストは維持され、supervisor がブラウザーへ切り替えて理由を記録し、異常終了メッセージとクラッシュログの案内を出します（`apps/desktop/src-tauri/src/supervisor.rs:182-192,303-313,385-431`）。これらは `STRATA_UI` の値判定エラーではなく、ウィンドウ起動後の fallback です。

## 根拠

- 唯一の実コード上の `STRATA_UI` 読み取り: `apps/desktop/src-tauri/src/main.rs:867-874`。
- 値の正規化、CLI フラグ、ヘルプ: `apps/desktop/src-tauri/src/supervisor.rs:43-63`。
- Linux 限定の supervisor 選択: `apps/desktop/src-tauri/src/main.rs:43-44,865-876`。
- モード決定、App Host への派生環境変数設定、既存セッションと先行 CLI 分岐: `apps/desktop/src-tauri/src/supervisor.rs:317-388`。
- ホストでのモード反映: `apps/host/server/app-ui.mjs:63-85`。

候補一覧 `000_envvers.md` にある `STRATA_UI` はこの Linux デスクトップ実装で実際に読み取られています。リポジトリ全体の完全一致検索では、その他の出現はコメント、トラブルシューティング文書、または別名の `STRATA_UI_BASE` / `STRATA_UI_MODE` / `STRATA_UI_PREVIEW` / `STRATA_UI_REASON` でした。外部ライブラリの挙動は対象にしていません。
