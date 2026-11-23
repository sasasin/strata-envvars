# `STRATA_DEVTOOLS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Tauri デスクトップアプリのメインウィンドウを作るとき、開発者ツールを有効にするかを指定する。`open_window` が値を読み、`devtools_wanted` が判定した bool をウィンドウビルダーへ渡す。これはデスクトップ UI の設定であり、同じソース内で CLI、サーバー、エンジンの挙動を切り替える読み取りはない（`app/desktop/src-tauri/src/main.rs:1032-1042`）。候補一覧には `STRATA_DEVTOOLS` が載っている（`docs/envvars/000_envvers.md:910`）。

## 値と判定

`std::env::var("STRATA_DEVTOOLS").ok()` で Unicode 文字列を読み、取得失敗は `None` として扱う。`devtools_wanted` は文字列の前後を `str::trim` で除き、残り全体が `"1"` と一致する場合だけ `true` を返す。先頭文字判定や数値変換ではない（`app/desktop/src-tauri/src/main.rs:1032-1034,1042`）。

| 条件 | unset / 読み取り失敗 | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| 全デスクトップ target の判定 | `false` | `1`、前後に空白を含む ` 1 ` | 空文字、`0`、`true`、`yes`、`on`、`11`、`1anything` |

値全体を trim した後に比較するため、大文字小文字の違いは受け付けず、空白を除いた値が厳密に `1` でなければ無効。数値としての妥当性検査や範囲変換はない。別の環境変数、CLI 引数、設定ファイルによる優先・上書き経路はこの設定にはない（`app/desktop/src-tauri/src/main.rs:1032-1042`）。

## 有効になる条件

- Strata の Tauri デスクトップアプリがメインウィンドウを作成し、読み取った値が有効であること。Linux ではウィンドウ用プロセスが `run_window_process` から `open_window` を呼び、Windows/macOS では `run_embedded` の setup から呼ぶ（`app/desktop/src-tauri/src/main.rs:931-945,982-996,1324-1350`）。
- macOS 以外の target では Cargo が Tauri の `devtools` feature を有効にする。macOS target ではこの feature を有効にする依存定義がないため、この環境変数でその feature を追加することはない（`app/desktop/src-tauri/Cargo.toml:32-35`）。
- 端末版 CLI、サーバー、エンジンがこの値を読む実装は見つからない。したがって、それらだけを起動してもこの判定は行われない。

## 実行時の詳細

値は `open_window` がメインウィンドウを構築する時点で `std::env::var` により読み取られ、結果は `.devtools(bool)` に渡される。値を保持する static や他のキャッシュはなく、設定変更を監視するコードもない。よって既に作成されたウィンドウへの実行中の変更適用は行われず、次のウィンドウ作成時にそのプロセス環境から再評価される（`app/desktop/src-tauri/src/main.rs:1032-1042`）。

この分岐は開発者ツールのフラグだけをウィンドウビルダーへ渡す。環境変数を理由にした Strata 独自の追加処理、CLI 優先順位、モデル状態による切り替えはない（`app/desktop/src-tauri/src/main.rs:1038-1042`）。

## ログと測定値

`STRATA_DEVTOOLS` の値が有効／無効であることを示す専用ログはない。ウィンドウ構築自体が失敗した場合は通常の起動失敗経路に入り、Windows/macOS 側は `the Strata window could not be opened: {e}` を起動失敗処理へ渡し、Linux のウィンドウプロセス側は `open_window` のエラーを Tauri の `expect` に渡す。この経路は値の判定結果を示すものではない（`app/desktop/src-tauri/src/main.rs:993-996,1349-1357`）。性能や正確性に関する測定値は該当しない。

## 根拠

- `app/desktop/src-tauri/src/main.rs:1030-1042` — 値判定、環境からの読み取り、ウィンドウビルダーへの引き渡し。
- `app/desktop/src-tauri/src/main.rs:931-945,982-996,1324-1357` — Linux と Windows/macOS のウィンドウ起動経路、および構築失敗時の処理。
- `app/desktop/src-tauri/Cargo.toml:32-35` — macOS 以外での `devtools` feature 依存設定。
- `docs/TROUBLESHOOTING.md:368` — Windows/Linux アプリでこの変数を使う手順の記載（挙動の根拠は上記ソース）。
