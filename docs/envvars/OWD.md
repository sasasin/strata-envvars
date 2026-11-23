# `OWD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストは `OWD` の値を設定や分岐に使わない。外部プログラムへ渡す環境を作るとき、AppImage 専用変数名の一覧に含めているため、AppImage の実行時環境から作る環境では `OWD` を削除する。一方、AppImage 外では元の環境を複製してそのまま渡し、起動時の環境を記録した `STRATA_ORIGINAL_ENV` が使える場合は記録側の `OWD` を残す（`app/host/server/external-env.mjs:17-24,43-57,60-70`）。

この helper はフォルダー選択、ファイルや URL のオープン、通知、エージェントの起動など、ホストが外部プロセスを実行する経路で使われる（例: `app/host/server/folder-dialog.mjs:117-127`, `app/host/server/app-ui.mjs:39-42,57-60`, `app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。`OWD` 自体がこれらの機能の選択やモデル処理を変えるコードはない。

## 値と判定

`OWD` の値は読み取らず、変換・大小文字比較・数値 parse もしない。`withoutAppImage` は `APPIMAGE_ONLY` の各名前に対し、値の有無や内容に関係なくコピーからそのキーを削除する。`externalEnvironment` がどの環境を元にするかで扱いが変わる。

| 条件 | `OWD` 未設定 | `OWD` が設定済み（空文字を含む） |
|---|---|---|
| `APPIMAGE` と `APPDIR` がともに falsy、かつ `STRATA_ORIGINAL_ENV` も falsy | コピーにも存在しない | `OWD` を含む環境のコピーを返す |
| `APPIMAGE` または `APPDIR` が truthy、または `STRATA_ORIGINAL_ENV` が truthy で、記録環境を復元できる | 記録環境に従う | 記録環境に含まれていれば、その値をそのまま残す |
| 上記条件だが記録環境を復元できない | `OWD` を含まない | `withoutAppImage` がキーを削除する |

記録環境は `STRATA_ORIGINAL_ENV` の base64 内容を NUL 区切りの `NAME=value` として復元し、`OWD` の値は `=` より後ろをそのまま保存する。記録が不正・空で復元できなければ AppImage 環境の除去処理に戻る（`app/host/server/external-env.mjs:28-40,44-48,67-70`）。呼び出し元が `extra` に同名キーを渡した場合は最後に上書き・追加されるが、`OWD` を渡す専用呼び出しは確認できない（同:64-70）。

## 有効になる条件

- `externalEnvironment` の引数で `APPIMAGE` または `APPDIR` が truthy、あるいは `STRATA_ORIGINAL_ENV` が truthy のとき、外部プロセス用の環境を再構成する。それ以外は環境を複製するだけで、`OWD` は変更されない（`app/host/server/external-env.mjs:60-70`）。
- 再構成時に有効な元環境の記録があれば、AppImage 起動前の環境を使うため、その記録内に `OWD` がある場合は保持する。記録がなければ AppImage 側の環境から `OWD` を削除する（同:28-40,43-57,67-70）。
- `withoutAppImage` の削除処理自体に OS、backend、build macro、CLI、モデル状態の条件はない。判定対象は環境マーカーと記録環境の復元可否である。

## 実行時の詳細

既定の `env` 引数は `process.env` であり、呼び出し時に環境オブジェクトを複製・処理する。`OWD` 専用の `static` cache や値の解析はなく、プロセス実行中に OS 環境が変わるかどうかを Strata が監視する処理もない。生成されたオブジェクトは各呼び出し元から `spawn` / `execFile` へ渡される。たとえば Linux のフォルダー選択は同じ `env` を `zenity`、`kdialog`、portal 用 `gdbus` に渡し、Harness 起動はフィルター後さらに `KEEP` に一致する変数だけを渡すため `OWD` を除外する（`app/host/server/external-env.mjs:67-70`, `app/host/server/folder-dialog.mjs:117-136,153-164`, `app/host/server/agent/harness-runtime.mjs:20-36,79-83`）。

## ログと測定値

`OWD` の削除・保持について専用ログ、警告、エラー、終了経路はない。外部コマンドの成否はそれぞれの呼び出し元が扱うが、`OWD` の値に基づく分岐はない。

## 根拠

- `app/host/server/external-env.mjs:17-24` — `OWD` を含む AppImage 専用名一覧。
- `app/host/server/external-env.mjs:28-40` — 起動時環境記録の復元。
- `app/host/server/external-env.mjs:43-57` — 値に触れず一覧の各キーを削除。
- `app/host/server/external-env.mjs:60-70` — AppImage 判定、記録環境と除去環境の選択、`extra` の優先。
- `app/host/server/folder-dialog.mjs:117-136,153-164` — フォルダー chooser / portal 起動への環境受け渡し。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 用環境の追加フィルターと子プロセス起動。
- `app/host/server/app-ui.mjs:39-42,57-60` — opener / 通知 subprocess への環境受け渡し。
