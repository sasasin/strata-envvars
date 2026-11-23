# `GDK_PIXBUF_MODULEDIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の engine や通常の host 設定を制御する読み取り箇所は見つからなかった。Strata がこの名前を使うのは `app/host/server/external-env.mjs` の `APPIMAGE_ONLY` リストであり、AppImage の環境を Strata 外のプログラムへ渡すときの除外対象として扱う。`externalEnvironment` は、AppImage 起動元の環境記録があればそれを外部プログラム用環境に戻す。記録がない AppImage では `withoutAppImage` がこの名前を削除する。値の内容を見て機能を有効化したり、値を書き換えたりはしない（`app/host/server/external-env.mjs:17-24,43-57,63-71`）。

この環境の受け渡しは Linux のフォルダー選択器 (`zenity`、`kdialog`、`gdbus`)、`xdg-open` 等の opener、通知、外部アプリ起動に使われる。エージェント用環境はさらに `KEEP` の許可リストで絞るため、この名前はエージェントの shell/tools には渡らない（`app/host/server/folder-dialog.mjs:112-126,135-146`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/app-ui.mjs:39-48,56-61`、`app/host/server/agent/harness-runtime.mjs:20-36`）。

## 値と判定

Strata は `GDK_PIXBUF_MODULEDIR` の値を直接取得・parse しない。`withoutAppImage` では名前の一致で削除し、`externalEnvironment` の起動元環境復元経路では環境オブジェクトをまとめてコピーする。したがって `0` / `1` / `true` / `false`、空文字、その他の文字列を Strata が検証・変換する規則はない。

| 条件 | unset | 値がある場合 | 空文字・無効値 |
|---|---|---|---|
| AppImage 外、`STRATA_ORIGINAL_ENV` なし | 子環境にも存在しない | `env` の値をそのまま子環境へコピー | 空文字もそのままコピー。値の妥当性判定なし |
| AppImage 内、または `STRATA_ORIGINAL_ENV` が truthy で、復元記録が正常に得られる | 記録に名前がなければ子環境にも存在しない | 記録された値をそのまま子環境へコピー | 記録の文字列を値として復元。対象値の妥当性判定なし |
| AppImage 内で復元記録を得られない | 削除後も存在しない | `APPIMAGE_ONLY` にあるため名前ごと削除 | 値によらず名前ごと削除 |
| `externalEnvironment(env, extra)` の `extra` に明示 | `extra` に指定がなければ上記各行の結果 | 最後に `extra` の値で追加または上書き | 値の検証なし。空文字も追加・上書きされる |

復元記録は `STRATA_ORIGINAL_ENV` が空でない場合に decode を試み、NUL 区切りの `NAME=VALUE` を環境オブジェクトに戻す。これは対象変数の値判定ではなく、起動元環境全体の復元処理である（`app/host/server/external-env.mjs:28-41,67-71`）。

## 有効になる条件

- 通常の Strata engine 機能を有効にする条件はない。この名前を読む engine 実装は見つからなかった。
- 子プロセス環境への受け渡し結果は、`externalEnvironment` 呼び出し時の `env`、`APPDIR` / `APPIMAGE`、`STRATA_ORIGINAL_ENV` の有無と内容、`extra` によって決まる（`app/host/server/external-env.mjs:43-71`）。
- AppImage の launcher hook は、実行開始元の環境を `STRATA_ORIGINAL_ENV` に記録する。文書化された repack 処理はこの記録を AppRun に追加する（`app/desktop/scripts/repack-appimage.sh:79-85`）。
- エージェント shell/tools への引き渡しでは `agentEnvironment` の `KEEP` がさらに適用され、この名前は許可リストに含まれない（`app/host/server/agent/harness-runtime.mjs:20-36`）。

## 実行時の詳細

`externalEnvironment` は呼び出しごとに環境オブジェクトをコピーする。対象名の値をキャッシュしたり、読み取り時点を固定したりする処理はない。引数 `env` の既定値は呼び出し時点の `process.env` である。AppImage 外で `STRATA_ORIGINAL_ENV` もない場合は `{ ...env, ...extra }` を返す。その他の場合、まず復元記録があればその環境を使い、なければ `withoutAppImage(env)` の結果を使い、最後に `extra` を重ねる（`app/host/server/external-env.mjs:28-41,43-57,60-71`）。

`APPIMAGE_ONLY` による削除は `withoutAppImage` が呼ばれた場合に行われ、`GDK_PIXBUF_MODULEDIR` の値や `APPDIR` 配下を指すかどうかには依存しない。対して `APPDIR` がある場合の追加フィルターもあるが、この名前は既に固定リストで削除される。`extra` が明示すれば、返却環境へ再追加できる（`app/host/server/external-env.mjs:17-24,43-57,67-71`）。

復元またはコピーされた環境は、外部プロセス起動時の `env` として渡される。該当する呼び出し元には folder chooser、`xdg-open` / desktop opener、通知、ファイルを開く処理などがある（`app/host/server/folder-dialog.mjs:117-136,153-164`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/app-ui.mjs:39-48,56-61`、`app/host/server/open-text-file.mjs:26-36`、`app/host/server/chat-files.mjs:85-93`）。エージェント環境は `externalEnvironment(base)` の後でキー許可リストによるフィルターを通るため、この名前を引き継がない（`app/host/server/agent/harness-runtime.mjs:25-36`）。

## ログと測定値

この名前の有無や値に関する Strata 固有のログ、警告、終了・失敗経路はない。Strata は子プロセス用環境へのコピーまたは削除だけを行い、子プロセス側の値の解釈や結果はここでは説明しない（`app/host/server/external-env.mjs:43-71`）。

## 根拠

- `app/host/server/external-env.mjs:17-24` — AppImage 専用として除外する環境変数名。
- `app/host/server/external-env.mjs:28-41` — `STRATA_ORIGINAL_ENV` の取得と復元。
- `app/host/server/external-env.mjs:43-57` — 固定名および AppImage 関連値の削除。
- `app/host/server/external-env.mjs:60-71` — AppImage 判定、環境の選択、`extra` の適用順。
- `app/desktop/scripts/repack-appimage.sh:79-85` — 起動元環境記録を AppRun に追加する処理。
- `app/host/server/agent/harness-runtime.mjs:20-36` — エージェント環境の追加フィルター。
