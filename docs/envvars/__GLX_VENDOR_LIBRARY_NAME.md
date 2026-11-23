# `__GLX_VENDOR_LIBRARY_NAME`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のデスクトップ診断ログに、この環境変数の現在値を記録する。描画 backend や vendor の選択に使う分岐は Strata 内に見つからず、この値を読み取る実装は `desktoplog.rs` のグラフィックス環境収集関数だけである。同関数は環境変数名の一覧を走査して値を文字列として記録する（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。

## 値と判定

`graphics_environment()` は一覧中の名前を `std::env::var(n)` に渡し、成功した値を `  __GLX_VENDOR_LIBRARY_NAME=<値>` の形で出力する。値の比較・数値変換・空白除去・有効値判定はしない。未設定、または Rust の `std::env::var` が値を `String` に変換できない場合は `.ok()` により記録対象から外れる。空文字列は取得に成功するため `  __GLX_VENDOR_LIBRARY_NAME=` と記録される。その他の Unicode 文字列は内容を問わず記録される（`app/desktop/src-tauri/src/desktoplog.rs:187-194`）。

| 条件 | 未設定 | 記録される値 | 記録されない値 |
|---|---|---|---|
| デスクトップ診断ログで収集関数を呼ぶ場合 | 行を出さない | 空文字列を含む、取得可能な Unicode 文字列。`0`、`1`、`true`、`false`、`0anything` もすべてそのまま記録 | Unicode 文字列として取得できない値。値の内容による無効判定はない |

## 有効になる条件

- Strata のデスクトップ診断ログがグラフィックス環境を収集する経路を通ること。ウィンドウプロセスのクラッシュレポート作成時、および `--save-logs` の実行時に呼ばれる（`app/desktop/src-tauri/src/desktoplog.rs:241-259`, `310-320`; `app/desktop/src-tauri/src/supervisor.rs:484-495`）。
- backend、ビルド macro、モデル状態、別の環境変数、CLI 引数による値の優先順位や上書きは、この変数の読み取り処理にはない。ログ収集経路を通らない通常の実行では、この箇所による読み取りは行われない。

## 実行時の詳細

値は `graphics_environment()` が呼ばれるたびに環境から取得され、関数内で cache されない。呼び出しはウィンドウクラッシュのレポート生成時と `--save-logs` のログファイル生成時に限られるため、その収集時点のプロセス環境値が記録される（`app/desktop/src-tauri/src/desktoplog.rs:187-194`, `243-259`, `310-320`）。この関数は値を設定したり子プロセスへ転送したりしない。値の違いによる Strata の描画動作、生成結果、終了・fallback の変更も確認できない。

## ログと測定値

クラッシュレポートでは `Graphics session:` の下に環境変数の行が加わり、`--save-logs` では同じ見出しの下に記録される（`app/desktop/src-tauri/src/desktoplog.rs:255-259`, `319`）。`--save-logs` は保存に成功すると `Saved to <path>. Please send this file to us.` を標準出力に出して終了コード 0、保存に失敗すると `[strata] could not save the logs: <error>` を標準エラーに出して終了コード 1 を返す（`app/desktop/src-tauri/src/supervisor.rs:484-495`）。クラッシュレポートは `desktop-crash-<時刻>.log` に保存され、書き込みに失敗した場合は収集した値を含むレポートファイルを作れない（`app/desktop/src-tauri/src/desktoplog.rs:281-289`）。性能・正確性の測定値は該当しない。

## 根拠

- `app/desktop/src-tauri/src/desktoplog.rs:186-194` — 対象名を含む一覧と、`std::env::var` による取得・文字列化。
- `app/desktop/src-tauri/src/desktoplog.rs:241-259` — クラッシュレポートの `Graphics session` 欄への追加。
- `app/desktop/src-tauri/src/desktoplog.rs:281-289` — クラッシュレポートのファイル保存。
- `app/desktop/src-tauri/src/desktoplog.rs:310-320` — `--save-logs` 用ファイルの生成と環境値の追加。
- `app/desktop/src-tauri/src/supervisor.rs:484-495` — `--save-logs` 分岐、成功・失敗時の出力と終了コード。
