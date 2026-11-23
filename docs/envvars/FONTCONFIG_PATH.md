# `FONTCONFIG_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Linux デスクトップ診断情報に、プロセス環境に設定されている `FONTCONFIG_PATH` の値を記録する。ウィンドウの描画設定を Strata 自身が切り替える用途ではなく、クラッシュレポートと `--save-logs` の `Graphics session` 欄に環境情報を載せる用途である。`graphics_environment()` は名前の配列を順に `std::env::var` で読み、取得できた値を `  NAME=value` の行にする（`app/desktop/src-tauri/src/desktoplog.rs:186-194`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `graphics_environment()` が呼ばれるとき | 行を出さない | `std::env::var` が `Ok` を返す値。空文字も `  FONTCONFIG_PATH=` として出力する | 未設定、または `std::env::var` が `Err` を返す値（例: 現行プラットフォームで Unicode 文字列にできない値）は行を出さない |

この値は文字列として取得されるだけで、数値化、真偽判定、空白除去、大小文字変換、パス検査、範囲・境界チェックは行わない。したがって `0`、`1`、`true`、`false`、`0anything` も、取得できればそのまま記録される。設定値の妥当性を理由に Strata が拒否する経路はない（`app/desktop/src-tauri/src/desktoplog.rs:188-194`）。

## 有効になる条件

- `FONTCONFIG_PATH` という名前は `graphics_environment()` の診断対象リストに含まれる。Strata のデスクトップ診断経路でこの関数が実行され、環境値を文字列として取得できるときにだけ記録される（`app/desktop/src-tauri/src/desktoplog.rs:187-194`）。
- Linux ではウィンドウプロセスの異常終了時に supervisor がクラッシュログを作成し、そのログに現在の `Graphics session` を含める（`app/desktop/src-tauri/src/supervisor.rs:465-475`、`app/desktop/src-tauri/src/desktoplog.rs:241-259,281-289`）。
- Linux の `--save-logs` 経路でも同じ情報を保存ファイルの `Graphics session` 欄へ含める（`app/desktop/src-tauri/src/supervisor.rs:478-494`、`app/desktop/src-tauri/src/desktoplog.rs:310-320`）。通常起動時にこの値だけを理由に処理を分岐したり、警告を出したりする条件はない。
- Linux ウィンドウ起動前の Strata のフォント設定処理は、`HOME`、`XDG_DATA_HOME`、`XDG_DATA_DIRS`、`FONTCONFIG_FILE`、`STRATA_FONT_CONFIG` を参照するが、`FONTCONFIG_PATH` は参照しない（`app/desktop/src-tauri/src/fontguard.rs:37-57,141-157`、呼び出し元 `app/desktop/src-tauri/src/main.rs:1307-1314`）。

## 実行時の詳細

読み取りは関数内のキャッシュではなく、診断レポートを組み立てるたびに `graphics_environment()` が環境を走査して行う。クラッシュ時は `crash_report()` の組み立て時、`--save-logs` では保存ファイルの組み立て時点の値が使われる（`app/desktop/src-tauri/src/desktoplog.rs:187-194,243-259,310-320`）。その時点までにプロセス環境が変更されていれば、新しい値が記録される。

Linux supervisor はウィンドウを子プロセスとして起動し、ここで `FONTCONFIG_PATH` を個別に設定・削除せず、環境を消去する処理も行わない（`app/desktop/src-tauri/src/supervisor.rs:390-400`）。ただしクラッシュレポート側の `graphics_environment()` は、クラッシュしたウィンドウではなくレポートを作るプロセスである supervisor の環境を読み取る。Strata が `FONTCONFIG_PATH` をフォント設定先として処理したり、値に応じてログ以外の動作を変えたりするコードは確認できない。

## ログと測定値

値が取得できる場合、クラッシュレポートおよび `--save-logs` の `Graphics session` に `  FONTCONFIG_PATH=<取得値>` の形式で記録される。未設定または文字列として取得できない場合はこの行がない（`app/desktop/src-tauri/src/desktoplog.rs:187-194,255-259,319`）。`--save-logs` の成功時は `Saved to <path>. Please send this file to us.` を標準出力に出して終了コード `0`、保存失敗時は `[strata] could not save the logs: {e}` を標準エラーに出して終了コード `1`（`app/desktop/src-tauri/src/supervisor.rs:484-493`）。`FONTCONFIG_PATH` 固有の警告・エラーや測定値はない。

## 根拠

- `app/desktop/src-tauri/src/desktoplog.rs:186-194` — 診断対象名と動的な環境変数読み取り、値の整形。
- `app/desktop/src-tauri/src/desktoplog.rs:241-259,281-289` — クラッシュレポートへの記録。
- `app/desktop/src-tauri/src/desktoplog.rs:310-320` — `--save-logs` ファイルへの記録。
- `app/desktop/src-tauri/src/supervisor.rs:390-400,465-475,478-494` — ウィンドウ子プロセス起動、クラッシュログ作成、CLI のログ保存と終了結果。
- `app/desktop/src-tauri/src/fontguard.rs:37-57,141-157`、`app/desktop/src-tauri/src/main.rs:1307-1314` — Strata のフォント設定経路で参照する環境変数と呼び出し。
