# `LIBGL_ALWAYS_SOFTWARE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata desktop はこの変数で描画方式を切り替えず、Linux desktop の診断情報「Graphics session」に現在の値を記録する。対象名は `graphics_environment()` の一覧に含まれ、一覧内の名前を使って環境から値を読み取る（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。この関数はウィンドウプロセスのクラッシュレポートと `--save-logs` の出力から呼ばれる（同 `:243-259`, `:310-320`）。

## 値と判定

値を真偽値や数値として判定しない。`std::env::var(n).ok()` が Unicode 文字列として読めた値をそのまま `  {name}={value}` の行にし、読めない場合は行を省く（`app/desktop/src-tauri/src/desktoplog.rs:188-194`）。

| 条件 | unset | 記録される値 | 行が省かれる値 |
|---|---|---|---|
| `graphics_environment()` の呼び出し | 環境変数が無い場合は記録なし | 空文字は `  LIBGL_ALWAYS_SOFTWARE=`。`0`、`1`、`true`、空白を含む文字列なども変換せずそのまま記録 | 値が OS 文字列から Unicode に変換できず `std::env::var` がエラーになる場合 |

大文字小文字比較、空白除去、数値変換、値域検証、無効値時の fallback はない。Strata は `LIBGL_ALWAYS_SOFTWARE` の設定有無に応じて処理を分岐しない（同 `:190-194`）。

## 有効になる条件

- 値が動作を切り替える条件はない。診断リストに存在するため、`graphics_environment()` が呼ばれたときだけレポートへの記録対象になる（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。
- Linux の desktop shell は、ウィンドウプロセスの異常終了時にクラッシュレポートを作り（`app/desktop/src-tauri/src/supervisor.rs:465-475`）、`--save-logs` では統合ログを保存する（同 `:478-494`）。メイン関数は Linux でこの supervisor 経路に入る（`app/desktop/src-tauri/src/main.rs:929-942`）。
- CLI 引数、他の環境変数、モデル状態、backend、build macro による値の優先順位や上書きはない。

## 実行時の詳細

読み取りは起動時の設定キャッシュではなく、各 `graphics_environment()` 呼び出し時に行われる。関数内に保存用の cache はないため、レポート生成時点の環境を列挙する（`app/desktop/src-tauri/src/desktoplog.rs:187-194`, `:243-259`, `:310-320`）。Strata 内でこの名前に対する `set_var`、`remove_var`、子プロセスへの個別転送は見つからなかった。

クラッシュレポートは `Graphics session:` に続けて値を含む行を入れ、`desktop-crash-<時刻>.log` に書く（`app/desktop/src-tauri/src/desktoplog.rs:254-259`, `:281-289`）。`--save-logs` は同じ診断行を `strata-logs-<時刻>.txt` に含める（同 `:310-320`, `:340-341`）。値が Strata の描画方法や通常のログ出力を変える処理はない。

## ログと測定値

この変数自体について有効・無効のログ、警告、終了・失敗経路はない。記録される場所は前節のクラッシュレポートまたは `--save-logs` ファイルである。`--save-logs` の保存成功時は `Saved to {}. Please send this file to us.` を stdout に出し、保存失敗時は `[strata] could not save the logs: {e}` を stderr に出して終了コード 1 を返す（`app/desktop/src-tauri/src/supervisor.rs:484-494`）。関連する Strata 資料にこの変数の測定値や別の動作説明はない。

## 根拠

- `app/desktop/src-tauri/src/desktoplog.rs:186-194` — 描画環境の名前一覧と `std::env::var` による読み取り・文字列化。
- `app/desktop/src-tauri/src/desktoplog.rs:243-259`, `:281-289` — クラッシュレポートへの挿入とファイル保存。
- `app/desktop/src-tauri/src/desktoplog.rs:310-320`, `:340-341` — `--save-logs` レポートへの挿入と保存。
- `app/desktop/src-tauri/src/supervisor.rs:465-475`, `:478-494`; `app/desktop/src-tauri/src/main.rs:929-942` — Linux desktop におけるレポートの呼び出し経路と保存結果。
