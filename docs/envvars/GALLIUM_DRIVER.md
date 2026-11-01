# `GALLIUM_DRIVER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリ・GPU driver の動作は対象外。

## 役割

Strata の Linux desktop shell が、graphics session の診断情報として環境変数の値をクラッシュログと `--save-logs` の出力に記録します。Strata の描画 backend や GPU driver の選択をこの変数で制御する読み取りではありません。

## 値と判定

| 環境の状態 | Strata の処理 |
|---|---|
| 未設定 | 出力しない |
| 空文字 | `  GALLIUM_DRIVER=` を出力する |
| Unicode 文字列 | 値を変換せず `  GALLIUM_DRIVER=<値>` として出力する |
| Unicode として取得できない値 | `std::env::var` がエラーとなり、その項目を出力しない |

値の構文検証、大小文字変換、既定値、数値変換、無効値時の fallback はありません。CLI 引数や別の Strata 環境変数による値の上書きもありません。`--save-logs` は採取を実行する方法を選びますが、環境変数の値を変更しません。

## 有効になる条件

この参照は desktop 診断情報の採取に限られます。Linux ではウィンドウプロセスが異常終了したときに shell がクラッシュログを作り、また `--save-logs` の実行時にも graphics session 情報を保存します。通常の起動や描画処理で `GALLIUM_DRIVER` を読み、分岐する箇所はありません。Windows/macOS の起動時ログ経路は別であり、この graphics session 収集経路を呼びません。

## 実行時の詳細

`graphics_environment()` は固定名リストを順に走査し、呼び出すたびに `std::env::var()` で現在のプロセス環境を読みます。値を static cache する処理はありません。対象変数の値は、ウィンドウ異常終了時の `desktop-crash-*.log` の `Graphics session:` 節、および `--save-logs` が作る `strata-logs-*.txt` の同節に含まれます。

この変数に関する警告、エラー終了、値による挙動変更はありません。クラッシュログ自体が作れない場合の通知や `--save-logs` のファイル書き込み失敗は一般のログ処理であり、`GALLIUM_DRIVER` の値による失敗経路ではありません。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — graphics session の収集関数と固定名リスト。`std::env::var(n).ok()` が未設定・取得エラーを除外し、成功した値をそのまま `name=value` 形式へ整形します。
- `apps/desktop/src-tauri/src/desktoplog.rs:241-260,281-289` — ウィンドウクラッシュレポートへの記録と、クラッシュログファイルの作成。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-341` — `--save-logs` 用ファイルへの graphics session 情報の記録。
- `apps/desktop/src-tauri/src/supervisor.rs:303-313,316-332` — ウィンドウ異常終了時のログ生成、および `--save-logs` による保存経路。
- `apps/desktop/src-tauri/src/main.rs:865-877` — Linux は supervisor shell 経路、非 Linux は embedded 経路へ進むこと。
