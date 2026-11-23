# `__NV_PRIME_RENDER_OFFLOAD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のレンダリング設定を切り替える用途ではありません。デスクトップアプリの診断情報を組み立てる際、設定されていれば `__NV_PRIME_RENDER_OFFLOAD=<値>` という行を「Graphics session」欄へ加えます。Strata 側で値を判定したり、GPU 選択や描画処理を分岐させたりするコードは確認できません。環境変数名一覧から共通収集関数へ渡される診断用の読み取りです（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。

## 値と判定

`graphics_environment()` は名前の一覧を走査し、各名前について `std::env::var` が成功したときだけ、名前と返された文字列をそのまま出力項目にします。真偽値や数値への変換、空白除去、大文字小文字比較はありません（`app/desktop/src-tauri/src/desktoplog.rs:187-194`）。

| 条件 | 未設定 | 設定時に含まれる値 | 収集されない場合 |
|---|---|---|---|
| デスクトップ診断情報の生成時 | 該当項目を出力しない | 空文字を含め、Unicode 文字列として取得できる値をそのまま `__NV_PRIME_RENDER_OFFLOAD=<値>` として含める。例: `0`、`1`、`true`、`false`、`0anything` はすべて文字列のまま含む | 未設定、または Rust の `std::env::var` が文字列として取得できない値（非 Unicode 値など）は項目ごと省く |

値が「有効」「無効」になる設定判定はありません。したがって境界値や無効値としての fallback もありません。空文字は未設定と同じ扱いではなく、`__NV_PRIME_RENDER_OFFLOAD=` の行になります（同 `:193-194`）。

## 有効になる条件

- 値によって Strata の機能を有効化する条件はありません。Strata 内の直接参照は診断対象名リストであり、実値を取得するのはそのリストを走査する `graphics_environment()` です（`app/desktop/src-tauri/src/desktoplog.rs:187-194`）。
- この収集関数を呼ぶデスクトップ診断経路では、ウィンドウプロセス障害のクラッシュレポートと `--save-logs` のログ収集に Graphics session 欄が入ります（同 `:243-259`, `:310-320`; `app/desktop/src-tauri/src/supervisor.rs:465-475`, `:484-493`）。
- 起動失敗用レポート `startup_report()` はこの関数を呼ばず、同欄も作りません（`app/desktop/src-tauri/src/desktoplog.rs:426-446`）。
- OS、GPU backend、build macro、モデル状態、CLI 引数、他の環境変数によって、この変数を Strata の動作制御に使う分岐は確認できません。

## 実行時の詳細

値は起動時にキャッシュされません。クラッシュレポートを作るときは `crash_report()` の生成時に、`--save-logs` では `save_logs()` の実行中に `graphics_environment()` が呼ばれ、その時点のプロセス環境を読みます（`app/desktop/src-tauri/src/desktoplog.rs:243-259`, `:310-320`）。そのため関数呼び出し前にプロセス環境が変われば収集結果も変わります。診断用の文字列を子プロセスへ転送・上書きする処理はありません。

ウィンドウ障害時は supervisor がクラッシュレポートを書き、保存できた場合はログにパスを記録します（`app/desktop/src-tauri/src/supervisor.rs:465-475`; `app/desktop/src-tauri/src/desktoplog.rs:281-289`）。`--save-logs` は Graphics session を含むファイルを保存し、成功時は保存先を stdout に、失敗時はエラーを stderr に出して終了コード `1` を返します（`app/desktop/src-tauri/src/supervisor.rs:484-493`; `app/desktop/src-tauri/src/desktoplog.rs:310-320`, `:340-341`）。

## ログと測定値

クラッシュレポートと保存ログでは、値が取得できた場合に `Graphics session:` の下へ `__NV_PRIME_RENDER_OFFLOAD=<値>` が記録されます。未設定または文字列化できない値は行ごと現れません（`app/desktop/src-tauri/src/desktoplog.rs:187-194`, `:255-259`, `:315-320`）。Strata の資料に、この変数の値に応じた性能測定値はありません。

## 根拠

- `app/desktop/src-tauri/src/desktoplog.rs:186-194` — 診断環境変数名一覧、実際の `std::env::var` 読み取り、値の整形。
- `app/desktop/src-tauri/src/desktoplog.rs:243-259`, `:281-289` — クラッシュレポートへの収録と書き出し。
- `app/desktop/src-tauri/src/desktoplog.rs:310-320`, `:340-341` — `--save-logs` 用ファイルへの収録と保存。
- `app/desktop/src-tauri/src/desktoplog.rs:426-446` — 起動失敗レポートには収録しない経路。
- `app/desktop/src-tauri/src/supervisor.rs:465-475`, `:484-493` — クラッシュ時および `--save-logs` からの呼び出し。
