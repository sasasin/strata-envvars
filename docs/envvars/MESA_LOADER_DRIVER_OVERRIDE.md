# `MESA_LOADER_DRIVER_OVERRIDE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Strata はこの名前を描画設定として解釈せず、Linux デスクトップの診断情報「Graphics session」の一項目として、環境に設定されていれば値をログへ記録します。候補一覧には名前がありますが、コード上で確認できる Strata の用途は診断情報の採取です。Strata が描画 driver を選択したり、値を検証・変更したりする処理はありません。

## 値と判定

| 環境の状態 | Strata の処理 |
|---|---|
| 未設定 | `std::env::var` がエラーとなり、項目を出力しない |
| 空文字 | 読み取り成功として `  MESA_LOADER_DRIVER_OVERRIDE=` を出力する |
| Unicode の値 | 値を変換・比較せず、`  MESA_LOADER_DRIVER_OVERRIDE=<値>` の形で記録する |
| 非 Unicode の値 | `std::env::var` がエラーとなり、項目を出力しない |

許容値、大小文字、数値変換、境界値、無効値の判定はありません。読み取った Unicode 文字列はそのまま `format!` に渡されます。

## 有効になる条件

Strata の挙動を切り替える条件はありません。Linux 版デスクトップシェルで、診断情報を含むログを作るときだけ値が採取されます。具体的には、ウィンドウプロセスの異常終了時にクラッシュログを作る経路と、`--save-logs` で診断ログを保存する経路です。通常の起動時にこの値を読んで描画設定を変更するコードは確認できません。

CLI の `--save-logs` は診断ログ生成を開始するスイッチですが、環境変数の値を上書きしたり優先したりはしません。別の環境変数との優先順位もありません。

## 実行時の詳細

`graphics_environment()` は環境変数名の一覧を順に処理し、`std::env::var(n).ok()` で読み取れたものだけを文字列化します。対象名は一覧中の一つです。関数内に `static` やキャッシュはなく、クラッシュレポートまたは `--save-logs` の本文を組み立てる時点で現在のプロセス環境から読みます。同一プロセス内でその前に環境値が変更されていれば、その時点の値が対象です。

クラッシュログでは `crash_report()` が「Graphics session」欄に項目を追加し、`write_crash_log()` がファイルへ書きます。これは Linux の supervisor がウィンドウプロセスの失敗を扱う経路です。保存ログでは `save_logs()` が同じ環境情報をテキストに含めます。したがって観測結果は診断ログ内の文字列であり、この値を理由とする Strata の警告、エラー、終了、描画処理の分岐はありません。

この調査では、外部ライブラリや driver が同名の環境変数をどう解釈するかは扱いません。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194`: 描画環境変数名の一覧と `std::env::var(n).ok()` による取得、値の文字列化。
- `apps/desktop/src-tauri/src/desktoplog.rs:241-259,281-289`: クラッシュレポートの Graphics session 欄、およびファイル書き込み。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-320,340`: `--save-logs` 用本文に同じ情報を含めて保存。
- `apps/desktop/src-tauri/src/supervisor.rs:303-313`: Linux のウィンドウ異常終了時にクラッシュログを作る呼び出し。
- `apps/desktop/src-tauri/src/supervisor.rs:316-330`: Linux シェルの `--save-logs` 経路。
- `apps/desktop/src-tauri/src/main.rs:40-44,865-873`: supervisor が Linux 向けに組み込まれ、Linux でシェル／ウィンドウ子プロセス経路へ進むこと。
- `docs/envvars/000_envvers.md:442`: 候補一覧の記載。リポジトリ全体の参照検索では、対象名は上記 `desktoplog.rs` の一覧以外に見つかりませんでした。
