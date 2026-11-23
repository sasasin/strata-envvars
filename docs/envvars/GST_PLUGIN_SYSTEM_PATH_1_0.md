# `GST_PLUGIN_SYSTEM_PATH_1_0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の推論 engine や GStreamer の動作を切り替える変数ではない。Node.js の host が外部プログラム用の環境を作るとき、AppImage の起動元環境を復元できない場合に、この名前の値を環境から除くための対象として登録されている。値そのものの検査・変換・警告は行わない（`app/host/server/external-env.mjs:17-24,43-57,67-71`）。

この環境は Linux のフォルダー選択や、ファイル・URL を開くプログラム、通知プログラムなどの起動に使われる。AppImage 起動元の記録がある場合は記録された環境を復元し、Strata の launcher が加えた環境を外部プログラムに渡さない設計である（`app/host/server/folder-dialog.mjs:112-126`、`app/host/server/app-ui.mjs:39-47,57-60`、`app/host/server/chat-files.mjs:89-94`、`app/desktop/scripts/repack-appimage.sh:79-85`）。

## 値と判定

Strata は `GST_PLUGIN_SYSTEM_PATH_1_0` の値を読み比べない。`withoutAppImage()` が環境オブジェクトを複製し、同名キーを `delete` するため、空文字を含め値が設定されていれば、復元失敗時には値の内容に関係なく除去される（`app/host/server/external-env.mjs:17-24,43-57`）。

| 条件 | 未設定 | 設定時の扱い | 判定される値の例 |
|---|---|---|---|
| AppImage 外で、`STRATA_ORIGINAL_ENV` もない | 未設定のまま | 値をそのまま返す | `""`、`/usr/lib/gstreamer-1.0` とも保持 |
| AppImage の起動元環境を記録から復元できる | 記録にもなければ未設定 | 記録に含まれる値をそのまま返す | 空文字も文字列も記録どおり |
| AppImage 内で記録がない、空、または復元できない | 未設定のまま | キーを削除 | `""`、`/usr/lib/gstreamer-1.0` とも削除 |

有効・無効を示す値、大小文字、空白、数値境界はない。値の解釈は外部プログラム側に委ねられ、Strata はその解釈結果を扱わない（`app/host/server/external-env.mjs:44-57,67-71`）。

## 有効になる条件

- `externalEnvironment()` の結果を外部プログラム起動に使う経路で適用される。AppImage 外で記録もない場合は環境をコピーして返すだけで、この変数は変更されない（`app/host/server/external-env.mjs:64-71`）。
- AppImage 起動時の環境記録 `STRATA_ORIGINAL_ENV` がデコードされ、空でない環境オブジェクトを復元できれば、その記録が優先される。記録内にこの変数があればその値を渡し、なければ渡さない（`app/host/server/external-env.mjs:28-40,67-71`）。launcher は AppImage 起動前の環境を NUL 区切りで Base64 化し、`STRATA_ORIGINAL_ENV` に記録する（`app/desktop/scripts/repack-appimage.sh:79-85`）。
- AppImage 内で記録を復元できない場合は `withoutAppImage()` にフォールバックし、このキーを無条件に削除する。空文字かどうか、パスが AppImage を指すかどうかは条件にならない（`app/host/server/external-env.mjs:43-57,67-71`）。
- agent 用環境を組み立てる経路では、`externalEnvironment()` の後に `KEEP` の許可リストでさらに絞り込まれる。この変数は許可リストにないため、agent とその shell tools には渡らない（`app/host/server/agent/harness-runtime.mjs:20-36`）。
- `externalEnvironment(env, extra)` の `extra` に同名キーを渡した場合は、元の環境の復元・除去後に追加値が優先される。ただし、確認した直接参照の呼び出しでは `extra` は渡されていない（`app/host/server/external-env.mjs:64-71`）。

## 実行時の詳細

`externalEnvironment()` は引数が省略されるたびに現在の `process.env` を参照し、関数内に結果を cache しない（`app/host/server/external-env.mjs:29,44,61,67`）。ただし、有効な `STRATA_ORIGINAL_ENV` がある経路では、launcher が記録した起動元環境を毎回復元するため、起動後に host の `process.env` だけを変更してもこの変数の引き渡し値は変わらない。記録がないフォールバック経路では、その呼び出し時の環境から生成する（`app/host/server/external-env.mjs:28-40,67-71`）。

この関数の結果は、folder chooser（`app/host/server/folder-dialog.mjs:117-126,135-136`）、URL opener と通知（`app/host/server/app-ui.mjs:39-47,57-60`）、`xdg-open` 等（`app/host/server/artifacts.mjs:5-6`、`app/host/server/chat-files.mjs:89-94`）、システム情報照会（`app/host/server/open-text-file.mjs:26-29`）の子プロセス起動に渡される。子プロセスの起動後に Strata がこの変数を再読したり、値を変更したりする経路は確認できない。

## ログと測定値

この変数の有無や値を理由にした Strata のログ、警告、終了分岐はない。関連する起動機能には個別の失敗処理があるが、この変数の値によるものではない。例として URL opener は起動エラーまたは短時間内の非ゼロ終了を失敗として扱い、Linux folder chooser は候補プログラムの失敗後に次の chooser を試す（`app/host/server/app-ui.mjs:35-53`、`app/host/server/folder-dialog.mjs:112-145`）。測定値は該当しない。

## 根拠

- `app/host/server/external-env.mjs:17-24` — AppImage 専用環境変数の一覧に対象名がある。
- `app/host/server/external-env.mjs:28-40,43-57,64-71` — 起動元環境の復元、対象キーの削除、外部プログラム用環境の選択。
- `app/desktop/scripts/repack-appimage.sh:79-85` — launcher が起動元環境を記録する処理。
- `app/host/server/agent/harness-runtime.mjs:20-36` — agent 環境の許可リストによる追加の除外。
- `app/host/server/folder-dialog.mjs:112-145`、`app/host/server/app-ui.mjs:35-60`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/open-text-file.mjs:26-29` — helper の利用経路。
