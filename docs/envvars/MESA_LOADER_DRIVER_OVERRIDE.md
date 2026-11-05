# `MESA_LOADER_DRIVER_OVERRIDE`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

Strata はこの変数を描画設定として解釈しません。Linux デスクトップの診断情報を作る際、現在のプロセス環境に設定されていれば、その名前と値を `Graphics session` 欄に記録します。クラッシュレポートと `--save-logs` の両方が対象です。レンダリング経路を変える処理、値の書き換え、専用の警告はありません。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| 未設定 | 出力しない。 |
| 空文字 | `  MESA_LOADER_DRIVER_OVERRIDE=` として出力する。 |
| Unicode 文字列 | 文字列全体を変換・検証せず、そのまま `  MESA_LOADER_DRIVER_OVERRIDE=<値>` として出力する。 |
| Unicode として取得できない値 | `std::env::var` がエラーとなり `.ok()` で `None` にされるため出力しない。 |

数値変換、真偽値判定、長さや値域の境界検査はありません。

## 有効になる条件

この参照は `desktoplog::graphics_environment()` の固定名リストにあります。Strata の通常の描画処理を有効化する条件ではなく、診断ログへの記録条件です。実際の呼び出し元は、Linux supervisor がウィンドウプロセスのクラッシュログを作る経路と、`--save-logs` 経路です。ほかの backend、CLI 引数、モデル状態、別の環境変数との優先関係はありません。

## 実行時の詳細

`graphics_environment()` が呼ばれるたびに `std::env::var` で現在のプロセス環境を読み、成功した値をリストへ追加します。結果をキャッシュしません。クラッシュレポートでは `Graphics session:` の後に一行ずつ含め、`--save-logs` では同じ一覧を保存ファイルの `Graphics session:` 欄に含めます。ログの保存に失敗した場合の結果は `--save-logs` 全体の保存エラー経路に従います。この変数固有の終了・失敗経路はありません。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — 固定名リスト、`std::env::var`、成功値の文字列化とエラー値の省略。
- `apps/desktop/src-tauri/src/desktoplog.rs:241-259` — クラッシュレポートの `Graphics session` 欄への追加。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-341` — `--save-logs` ファイルへの追加と保存時エラー。
- `apps/desktop/src-tauri/src/supervisor.rs:303-313,322-332` — ウィンドウクラッシュ時および `--save-logs` 時の呼び出しと観測可能な結果。
