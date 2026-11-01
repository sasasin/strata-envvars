# `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のデスクトップ診断コードが、この環境変数の現在値をグラフィックス環境情報として記録します。Strata がこの値を判定してウィンドウの描画・sandbox 設定を変える実装は見つかりませんでした。候補名の Strata 内参照は `desktoplog.rs` の環境変数名リストだけです（`apps/desktop/src-tauri/src/desktoplog.rs:186-194`）。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| 未設定 | 診断情報に項目を出さない。 |
| 空文字 | 設定値として取得され、`WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=` と記録する。 |
| その他の Unicode 文字列 | 内容の parse、真偽判定、大小文字変換をせず、`WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=<値>` と記録する。 |
| Unicode として取得できない値 | `std::env::var` がエラーとなり、`.ok()` により項目を出さない。 |

この変数について既定値、数値変換、値域・境界、無効値時の fallback はありません。CLI 引数や別の環境変数との優先順位もありません。値は Strata の描画設定に転送されず、診断テキストに文字列として書き込まれます（`apps/desktop/src-tauri/src/desktoplog.rs:188-194`）。

## 有効になる条件

環境変数の値で機能を有効化する条件はありません。読み取り結果が使われるのは Linux デスクトップの診断経路です。

- Linux のウィンドウプロセスが異常終了すると、shell がクラッシュログを作る際に graphics session の一部として値を加えます（`apps/desktop/src-tauri/src/supervisor.rs:303-313`、`apps/desktop/src-tauri/src/desktoplog.rs:241-259,282-289`）。
- Linux デスクトップを `--save-logs` で起動すると、保存するログ集約ファイルの graphics session に値を加えます（`apps/desktop/src-tauri/src/supervisor.rs:43-51,317-332`、`apps/desktop/src-tauri/src/desktoplog.rs:310-320`）。

通常の起動時にはこの変数を読んで分岐しません。Linux 起動時に `WEBKIT_DISABLE_DMABUF_RENDERER` が未設定なら `1` を設定する処理はありますが、対象変数とは別の名前です（`apps/desktop/src-tauri/src/main.rs:852-858`）。

## 実行時の詳細

`graphics_environment()` はリスト内の各名前について `std::env::var` を呼び、取得できた値だけを整形して返します。対象変数専用のキャッシュはなく、クラッシュログ生成時または `--save-logs` による集約時に呼び出されるたび、その時点のプロセス環境を読みます（`apps/desktop/src-tauri/src/desktoplog.rs:187-194,256,319`）。このコードに、値を別プロセスへ渡す処理や、対象変数について警告・終了コードを変える処理はありません。

観測されるのは診断ファイル内の `Graphics session:` 欄です。`--save-logs` は保存成功時に保存先を stdout へ表示して終了コード 0、保存失敗時は `[strata] could not save the logs: ...` を stderr に出して 1 を返しますが、いずれもこの環境変数の値による分岐ではありません（`apps/desktop/src-tauri/src/supervisor.rs:322-331`）。クラッシュログ経路では、ウィンドウ異常終了を shell が報告し、クラッシュログにグラフィックス環境情報を含めます（`apps/desktop/src-tauri/src/supervisor.rs:303-313`）。

## 根拠

- 候補名を含む唯一の Strata 参照と、値を環境から取得して項目化する共通処理: `apps/desktop/src-tauri/src/desktoplog.rs:186-194`。
- クラッシュログへの記録: `apps/desktop/src-tauri/src/desktoplog.rs:241-259,282-289`。
- `--save-logs` の受付・結果と集約ファイルへの記録: `apps/desktop/src-tauri/src/supervisor.rs:43-51,317-332`、`apps/desktop/src-tauri/src/desktoplog.rs:310-320`。
- Linux 起動時に設定される別の WebKit 環境変数: `apps/desktop/src-tauri/src/main.rs:852-858`。
