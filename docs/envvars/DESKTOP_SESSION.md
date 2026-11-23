# `DESKTOP_SESSION`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Linux デスクトップアプリがクラッシュ情報をまとめるとき、`DESKTOP_SESSION` の現在値を診断ログへ含める。値によってウィンドウ描画やセッション選択を変える処理はこの環境変数の参照箇所にはなく、設定用スイッチではない。`desktoplog::graphics_environment` が環境名の配列を走査して値を記録する（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。

この記録は Linux のウィンドウプロセス異常終了時に作るクラッシュログ、および `--save-logs` で作る収集ファイルに入る。Windows/macOS の起動失敗レポートは別の `startup_report` 経路で作られ、`graphics_environment` を呼ばない（`app/desktop/src-tauri/src/desktoplog.rs:241-259,310-320,425-446`）。

## 値と判定

`graphics_environment` は名前の配列にある各名前を `std::env::var(n)` へ渡し、成功した文字列を `  {名前}={値}` の形でそのまま記録する。値の解析・真偽判定・数値変換はしない（`app/desktop/src-tauri/src/desktoplog.rs:187-194`）。

| 条件 | unset | 記録される値 | 記録されない例 |
|---|---|---|---|
| Linux デスクトップの診断生成時 | `std::env::var` が値を取得できなければ `DESKTOP_SESSION` の行を省略 | 空文字、`0`、`1`、`true`、`false`、その他の取得可能な文字列を変更せず記録 | 環境変数が未設定、または `std::env::var` がエラーとなる値（例: Unix の非 UTF-8 値） |

空文字は設定済みの値として `  DESKTOP_SESSION=` と出力される。大文字小文字、前後の空白、`0anything` などを判定するコードはなく、どの値も機能の有効・無効を切り替えない（同 `desktoplog.rs:193-194`）。

## 有効になる条件

- Linux でウィンドウプロセスが予期せず終了し、shell が `window_failed` からクラッシュログを生成する場合に値が読み取られる（`app/desktop/src-tauri/src/supervisor.rs:465-475`）。そのログ本文では `Graphics session:` の直下に、取得できた環境値の一つとして並ぶ（`app/desktop/src-tauri/src/desktoplog.rs:243-259`）。
- Linux で `--save-logs` が指定され、shell が `save_logs` を実行する場合にも読み取られる。CLI 引数は収集処理を呼ぶ条件であり、`DESKTOP_SESSION` の値自体に優先順位はない（`app/desktop/src-tauri/src/supervisor.rs:43-54,484-494`; `app/desktop/src-tauri/src/main.rs:929-945`）。
- 値が未設定でも診断生成は続き、その行だけが出ない。OS 描画設定、backend、build macro、サーバーモード、モデル状態、別の環境変数との組み合わせによってこの値の解釈が変わる処理はない。

## 実行時の詳細

`graphics_environment` の呼び出しごとに配列を走査して環境を読み、結果をベクターにする。関数内キャッシュはなく、起動時の設定値や CLI 引数から値を決めていない（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。クラッシュレポートの生成時と `--save-logs` の実行時にそれぞれ呼ばれる（同 `desktoplog.rs:243-259,310-320`）。Strata 内に `DESKTOP_SESSION` を変更する参照箇所はなく、子プロセスへこの値を転送・上書きする処理も見つからない。

Linux のクラッシュログ書き込みに失敗しても、`window_failed` は「The crash log could not be written. To collect the logs for us: ... --save-logs」と記録して browser mode へ移る。書き込み成功時はログパスを記録してから同じく browser mode へ移る。`--save-logs` で収集ファイルの作成に失敗すると `[strata] could not save the logs: {e}` を stderr に出して終了コード 1 を返す（`app/desktop/src-tauri/src/supervisor.rs:465-475,484-494`）。これらの失敗条件は `DESKTOP_SESSION` の値によるものではない。

## ログと測定値

値はクラッシュログの `Graphics session:` 節、および `--save-logs` のファイルの同節へそのまま含まれる。取得できた値に応じた専用の stdout/stderr メッセージや警告はない（`app/desktop/src-tauri/src/desktoplog.rs:243-259,310-320`）。該当する測定値はない。

## 根拠

- `app/desktop/src-tauri/src/desktoplog.rs:186-194` — `DESKTOP_SESSION` を含む名前一覧と、値の動的読み取り・行整形。
- `app/desktop/src-tauri/src/desktoplog.rs:243-259,281-289` — クラッシュレポートへの挿入とファイル書き込み。
- `app/desktop/src-tauri/src/desktoplog.rs:310-320,340-341` — `--save-logs` ファイルへの挿入と保存。
- `app/desktop/src-tauri/src/supervisor.rs:465-475,484-494` — Linux のウィンドウ障害および `--save-logs` からの呼び出しと失敗時の出力・戻り値。
- `app/desktop/src-tauri/src/main.rs:929-945` — Linux では supervisor を通り、非 Linux では別経路へ進む条件。
- `app/desktop/src-tauri/src/desktoplog.rs:425-446` — 起動失敗レポートが別形式で、グラフィック環境一覧を含まないこと。
