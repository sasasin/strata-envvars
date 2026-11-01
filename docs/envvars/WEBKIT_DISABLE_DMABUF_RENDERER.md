# `WEBKIT_DISABLE_DMABUF_RENDERER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の Linux デスクトップ起動処理は、この変数が未設定なら値 `1` を設定します。コードコメントでは、NVIDIA + Wayland の一部環境や仮想 GPU で WebKitGTK の DMA-BUF renderer により空白ウィンドウになる問題への対策として説明されています。Strata 自身が行う処理として確認できるのは環境変数の設定と、診断資料への記録です。WebKitGTK や GPU driver が設定値をどう解釈するかは、この調査の対象外です。

## 値と判定

| 起動時の状態 | Strata の処理 |
|---|---|
| 未設定 | Linux のデスクトップ実行ファイルが `"1"` を設定する |
| 空文字を含む設定済みの値 | 変更せず、その値を残す |
| その他の設定済みの値 | 内容を parse・検証せず、変更せず残す |

`std::env::var_os(...).is_none()` による存在確認であり、`1` との文字列比較ではありません。空文字や Unicode でない値も「設定済み」と判定されるため、Strata はそれらを `"1"` で置き換えません。Strata による無効値エラー、fallback、範囲制限はありません。

## 有効になる条件

この既定値設定は `#[cfg(target_os = "linux")]` のブロック内にあり、Linux 向けデスクトップ実行ファイルでだけ実行されます。設定処理は `main` の引数分岐より前にあるため、通常の起動に加え、`--browser` / `STRATA_UI=browser`、`--save-logs`、`--self-test` の経路でも実行されます。Linux の `--window-child` も同じ実行ファイルの `main` を通ります。Windows と macOS にはこの既定値設定のコードはありません。

設定済みの値を尊重するため、環境変数の値で Strata が既定値を上書きする経路はありません。CLI 引数や他の環境変数によるこの変数の優先順位・無効化も実装されていません。ブラウザ表示を選んだときにも設定処理自体は通りますが、Strata のコードはその選択に応じて変数を別の値にしません。

## 実行時の詳細

変数は `main` の引数処理および Linux supervisor 起動より前に一度だけ存在確認されます。値の parse や Strata 内の cache はありません。Linux supervisor が `--window-child` を起動するときは `std::process::Command` で同じ実行ファイルを起動し、環境を消去していないため、親プロセスの環境を継承します。子の `main` も変数を確認しますが、継承された値があるので既定値を再設定しません。

通常起動時にこの変数専用のログや警告は出ません。Linux の `--save-logs` で作られるログ、またはウィンドウプロセスのクラッシュログには `graphics_environment()` が読み取った設定値が含まれます。ログへの収集は `std::env::var` で行うため、Unicode 文字列として読める設定だけが `WEBKIT_DISABLE_DMABUF_RENDERER=<値>` の行になります。未設定、または Unicode として取得できない値はこの一覧に出ません。クラッシュ時は supervisor がウィンドウの異常終了を通知してクラッシュログを作成し、ブラウザ表示へ切り替えますが、この変数自体についての警告はありません。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:838-877` — Linux 条件で未設定なら `"1"` を設定する位置、および CLI・self-test・supervisor への分岐順。
- `apps/desktop/src-tauri/src/supervisor.rs:229-239` — Linux の window child を起動する `Command`。環境を消去せず子プロセスを起動する。
- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — 診断対象の graphics 環境変数として列挙し、値を取得する処理。
- `apps/desktop/src-tauri/src/desktoplog.rs:241-268,281-289` — クラッシュログに graphics environment を含める経路。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-320`、`apps/desktop/src-tauri/src/supervisor.rs:316-332` — `--save-logs` の収集と、成功・失敗時の出力・終了コード。
- `apps/desktop/tester/common-troubleshoot.txt:19-24` — トラブルシューティング文書での手動指定例。これは診断手順であり、実装の値判定根拠ではない。
