# `ARGV0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のエンジンやサーバーの動作を設定する変数ではない。Node 側の `externalEnvironment` が、AppImage 由来の環境を外部プログラムへ渡す前に除去する名前の一つとして扱う。除去対象は「AppImage tooling が自身のために設定する変数」として `APPIMAGE_ONLY` に列挙されている（`app/host/server/external-env.mjs:17-24`）。

この処理が適用されると、フォルダー選択器（`zenity`、`kdialog`、`gdbus`）、外部 opener・通知、外部プログラムを起動する処理、および agent の shell 用環境を組み立てる経路に `ARGV0` は含まれない（`app/host/server/folder-dialog.mjs:117-136,153-154`、`app/host/server/app-ui.mjs:39-42,57-60`、`app/host/server/agent/harness-runtime.mjs:25-32`、`app/host/server/artifacts.mjs:5-6`）。Strata 自身の起動名、CLI 引数、モデル計算をこの変数で変える読み取り箇所は確認できなかった。

## 値と判定

Strata は `ARGV0` の値を比較・変換せず、名前だけを除外リストに登録している。AppImage 環境をクリーンアップする経路では、値が空文字でも設定済みでも `delete out[name]` により除かれる（`app/host/server/external-env.mjs:43-57`）。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| AppImage の記録環境が使えず、`withoutAppImage` によるクリーンアップを行う | 変更なし | 該当なし。`ARGV0` は機能を有効化する値として読まれない | 値の内容は判定されず、設定があれば空文字を含め常に除去 |
| AppImage 外（`APPIMAGE` と `APPDIR` がなく、`STRATA_ORIGINAL_ENV` もない） | 変更なし | 該当なし | `externalEnvironment` は環境を複製するだけなので、`ARGV0` を含めそのまま残る |
| `STRATA_ORIGINAL_ENV` の記録を復元できる | 記録に無ければ未設定 | 該当なし | 記録を復元した環境をそのまま使うため、記録内に `ARGV0` があれば残る |

分岐は `APPIMAGE` または `APPDIR` の有無と `STRATA_ORIGINAL_ENV` の有無で決まり、`ARGV0` 自体の値や CLI 引数による優先順位はない（`app/host/server/external-env.mjs:28-40,60-70`）。

## 有効になる条件

- `externalEnvironment` の引数が省略された通常の呼び出しでは、呼び出し時点の `process.env` が使われる（`app/host/server/external-env.mjs:67-70`）。
- AppImage 外では `APPIMAGE`、`APPDIR`、`STRATA_ORIGINAL_ENV` がすべて falsy なら環境をそのまま複製するため、`ARGV0` の除去は起きない（`app/host/server/external-env.mjs:60-70`）。
- AppImage 内で有効な起動元環境レコードが復元できれば、そのレコードが外部環境として返される。レコード内の `ARGV0` はこの経路では個別に除去されない（`app/host/server/external-env.mjs:28-40,67-70`）。AppImage の repack スクリプトは `STRATA_ORIGINAL_ENV` を `AppRun` に記録する hook を挿入する（`app/desktop/scripts/repack-appimage.sh:79-85`）。
- レコードが無い、空、復元できない、または復元結果が空の場合は `withoutAppImage` に進み、`ARGV0` を無条件に除去する（`app/host/server/external-env.mjs:28-40,43-48,67-70`）。
- 呼び出し側の `extra` に `ARGV0` が明示的に含まれる場合は、クリーンアップまたは復元の後で追加される。ただし確認した `externalEnvironment` 呼び出しでは `ARGV0` を `extra` として渡していない（`app/host/server/external-env.mjs:64-70`）。

## 実行時の詳細

キャッシュはない。`externalEnvironment` 呼び出しごとに渡された環境（既定ではその時点の `process.env`）を評価し、AppImage 判定後に環境オブジェクトを作る（`app/host/server/external-env.mjs:29,44,60-70`）。したがって呼び出し前に変更された環境は次の呼び出しで反映される。

クリーンアップ経路では `APPIMAGE_ONLY` を順に走査して複製環境から `ARGV0` を削除し、呼び出し元がそれを子プロセスの `env` として使う。Linux のフォルダー選択では同じ環境オブジェクトを `zenity`、`kdialog`、portal の `gdbus` に渡す。外部 opener、通知、artifact opener、および agent の shell 環境にも helper が使われる（`app/host/server/external-env.mjs:43-57`、`app/host/server/folder-dialog.mjs:117-154`、`app/host/server/app-ui.mjs:39-60`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:25-32`）。

子プロセスの終了や失敗を `ARGV0` の値に応じて変える分岐、待機、警告はこの実装にない。外部環境から名前を除く処理だけであり、外部プログラム側の `ARGV0` の意味や挙動はここでは扱わない。

## 根拠

- `app/host/server/external-env.mjs:17-24` — `ARGV0` を含む AppImage 専用変数リスト。
- `app/host/server/external-env.mjs:28-40,43-70` — 起動元環境の復元、クリーンアップ、適用条件。
- `app/desktop/scripts/repack-appimage.sh:79-85` — `STRATA_ORIGINAL_ENV` を記録する hook。
- `app/host/server/folder-dialog.mjs:117-154`、`app/host/server/app-ui.mjs:39-60`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:25-32` — helper の利用先。
