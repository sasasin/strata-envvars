# `XDG_SESSION_TYPE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のデスクトップシェルが、グラフィックスセッションの診断情報として値を収集します。ウィンドウの描画方式やセッションの選択を Strata が切り替えるための設定ではありません。`graphics_environment()` はこの変数を含む環境変数の一覧を走査し、取得できた値を `  XDG_SESSION_TYPE=<値>` という行にします（`apps/desktop/src-tauri/src/desktoplog.rs:186-194`）。

この情報は Linux デスクトップのウィンドウクラッシュ報告と `--save-logs` の収集ファイルに含まれます（`apps/desktop/src-tauri/src/desktoplog.rs:241-259,310-320`）。

## 値と判定

Strata は値の内容を比較・parse しません。環境変数名を `std::env::var` に渡し、成功した文字列をそのまま診断行へ追加します（`apps/desktop/src-tauri/src/desktoplog.rs:187-194`）。

| 状態 | Strata の処理 |
|---|---|
| 未設定 | `std::env::var` が `Err` となり、該当行を出力しない |
| 設定値が空文字 | 取得できれば `  XDG_SESSION_TYPE=` を出力する |
| 任意の文字列 | 値を解釈せず、そのまま出力する。値による有効・無効判定や境界はない |
| `std::env::var` がエラー | `.ok()` でエラーを捨て、該当行を出力しない。たとえば Unix で値が有効な Unicode 文字列でない場合は取得に失敗する |

## 有効になる条件

値は診断出力の生成時にのみ参照されます。ウィンドウプロセスが異常終了すると supervisor がクラッシュログを書き、クラッシュ報告には「Graphics session:」の下に取得できた環境変数行を含めます（`apps/desktop/src-tauri/src/supervisor.rs:303-310`, `apps/desktop/src-tauri/src/desktoplog.rs:241-259,281-289`）。`--save-logs` は診断ファイルに同じ環境情報を含めます（`apps/desktop/src-tauri/src/supervisor.rs:322-331`, `apps/desktop/src-tauri/src/desktoplog.rs:310-320`）。

この値を使った OS / backend / build 条件の判定、CLI 引数との優先順位、別環境変数による上書きはありません。Strata のソース上、この変数が描画挙動、実行経路、終了状態を変える処理は確認できません。

## 実行時の詳細

`graphics_environment()` は関数が呼ばれるたびに環境変数一覧を走査するため、値を保存する `static` cache はありません。ウィンドウクラッシュ時はクラッシュ報告生成時に読み取り、ログ保存時は保存ファイル生成時に読み取ります（`apps/desktop/src-tauri/src/desktoplog.rs:187-194,243-259,310-320`）。

環境変数が未設定または取得不能でも、Strata は警告・エラーを出さず、その環境変数の行を省略します。設定値はログ本文に出る以外の用途がありません。クラッシュログが書けない場合などの処理は一般のログ保存経路に従い、この変数の値による分岐はありません（`apps/desktop/src-tauri/src/desktoplog.rs:281-289`; ログ保存 CLI の成功・失敗表示は `apps/desktop/src-tauri/src/supervisor.rs:322-331`）。

## 根拠

- 候補名を含む唯一の直接参照は `apps/desktop/src-tauri/src/desktoplog.rs:189`。同ファイル `:193-194` で、名前一覧の各項目を `std::env::var` で読み、取得できた値を文字列化しています。
- クラッシュ報告への挿入: `apps/desktop/src-tauri/src/desktoplog.rs:241-259`; 報告の書き出し: `:281-289`; ウィンドウ異常終了時の呼び出し: `apps/desktop/src-tauri/src/supervisor.rs:303-310`。
- `--save-logs` の診断ファイルへの挿入: `apps/desktop/src-tauri/src/desktoplog.rs:310-320`; CLI 分岐: `apps/desktop/src-tauri/src/supervisor.rs:322-331`。
