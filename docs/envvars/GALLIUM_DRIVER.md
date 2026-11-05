# `GALLIUM_DRIVER`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。調査対象 checkout は `main` で、作業ツリーは clean（`## main...origin/main`）。

## 役割

Strata の Linux デスクトップアプリが、診断用の graphics session 情報としてこの環境変数の現在値を記録します。アプリウィンドウの異常終了時に作成する crash log と、`--save-logs` が作るログ収集ファイルに `GALLIUM_DRIVER=<値>` の行が含まれます。GPU backend や engine の動作を選ぶために Strata が読む設定ではありません。

## 値と判定

Strata は値を parse・検証・変換しません。`std::env::var` で Unicode 文字列として取得できれば、値をそのまま `GALLIUM_DRIVER=<値>` の形式にします。

| 環境の状態 | 診断出力 |
|---|---|
| 未設定 | `GALLIUM_DRIVER` の行を出力しない |
| 空文字で設定 | `GALLIUM_DRIVER=` の行を出力する |
| Unicode 文字列で設定 | 値をそのまま出力する。大小文字、数値、空白、値域の検査はない |
| Unicode でない値 | `std::env::var` がエラーとなるため、その行を出力しない |

有効値・無効値の区別、既定値、fallback、CLI 引数や他の環境変数との優先順位はありません。診断文字列に補間されるだけです。

## 有効になる条件

この処理はデスクトップアプリの診断経路に限られます。Linux では、別プロセスのウィンドウが異常終了した場合の crash log に graphics session を記録し、`--save-logs` で保存するログにも記録します。`--save-logs` は Linux supervisor の引数処理です。通常の起動や正常なウィンドウ終了だけでは、この変数を記録する出力経路は呼ばれません。

Strata のソースで `GALLIUM_DRIVER` を設定・上書きしたり、別のプロセスへこの値を明示的に渡したりする箇所は見つかりませんでした。CUDA/HIP/SYCL engine やサーバーの機能をこの値で切り替える Strata 所有コードも見つかりません。

## 実行時の詳細

`graphics_environment()` は名前の固定リストを順に調べ、`std::env::var(n).ok()` で取得できたものだけを一覧にします。この関数は値を読むたびに実行され、`GALLIUM_DRIVER` 専用の static cache はありません。従って診断生成時点のプロセス環境が対象になります。環境値を読み取ることによる警告・終了・失敗経路はありません。

ウィンドウプロセスの異常終了では、Linux supervisor が `window_failed()` から crash log を作成し、同じ報告に graphics session を追加します。`--save-logs` は保存ファイルの冒頭にも graphics session を追加します。ログの書き込みに成功した場合の結果や失敗時のメッセージは、ログ収集全体の経路によるもので、この環境変数の値によって変化しません。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — 固定名リストに `GALLIUM_DRIVER` を含め、`std::env::var` で取得できた値を `  NAME=value` 形式にして返す。
- `apps/desktop/src-tauri/src/desktoplog.rs:243-259` — crash report の `Graphics session` に一覧を出力する。
- `apps/desktop/src-tauri/src/desktoplog.rs:281-289` — `write_crash_log()` が crash report を生成してファイルへ保存する。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-320` — `save_logs()` が収集ファイルに `Graphics session` を含める。
- `apps/desktop/src-tauri/src/supervisor.rs:303-313,322-332` — Linux のウィンドウ異常終了時と `--save-logs` 時に上記のログ関数を呼ぶ。
- `apps/desktop/src-tauri/src/main.rs:44-48,869-880` — supervisor は Linux のみでコンパイルされ、Linux では shell と window process の経路を使う。

候補一覧 `docs/envvars/000_envvers.md:614` に名前があります。調査した Strata checkout 全体で完全一致の参照は `desktoplog.rs:191` のみでした。従って候補としては実際に環境を読む名前ですが、その用途はデスクトップ診断ログへの記録に限定されます。
