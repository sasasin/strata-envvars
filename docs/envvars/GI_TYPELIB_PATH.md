# `GI_TYPELIB_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Node.js ホストは `GI_TYPELIB_PATH` の値を解釈して機能を切り替えるのではなく、AppImage 外のプログラムへ渡す環境を組み立てる際に、この名前のキーを条件付きで除去する。目的は AppImage 専用の環境設定を外部プログラムへ持ち込まないことである。除去対象は子プロセス用のコピーであり、Strata プロセス自身の `process.env` を書き換えない（`app/host/server/external-env.mjs:17-24,43-57,63-71`）。

## 値と判定

この変数の値は parse・比較されない。値の内容、空文字、数値らしさ、大文字小文字や空白は判定に使われず、環境オブジェクトのキー名 `GI_TYPELIB_PATH` の有無で扱いが決まる（`app/host/server/external-env.mjs:18-23,48`）。

| 条件 | unset | 設定時の扱い |
|---|---|---|
| `APPIMAGE` / `APPDIR` と `STRATA_ORIGINAL_ENV` がいずれも未設定または空 | なしのまま | 空文字を含め、値をそのまま外部環境へ渡す |
| `STRATA_ORIGINAL_ENV` から空でない環境を復元できる | 記録内でも未設定ならなし | 記録された値をそのまま使う。現在の環境にある別の値は使わない |
| 上記以外で `APPIMAGE`、`APPDIR`、または `STRATA_ORIGINAL_ENV` が真値 | なしのまま | 値の内容を問わずキーを削除する |

`externalEnvironment` は `APPIMAGE` / `APPDIR` と `STRATA_ORIGINAL_ENV` を呼び出しごとに確認する。AppImage 内のフォールバック処理では `withoutAppImage` が `APPIMAGE_ONLY` の各キーを無条件に削除する。復元できる起動元環境は `env -0` の Base64 記録をデコードし、NUL 区切りの `NAME=value` から作られる（`app/host/server/external-env.mjs:28-40,43-57,60-71`; 記録の設定は `app/desktop/scripts/repack-appimage.sh:79-85`）。

## 有効になる条件

- 対象は `externalEnvironment` の返す環境を使って起動する外部プログラムである。確認できた呼び出し元には、Linux のフォルダー選択（`zenity`、`kdialog`、`gdbus`）、ファイルや URL を開くプログラム、通知、テキストエディター確認処理、および Harness の子プロセスがある（`app/host/server/folder-dialog.mjs:117-136,153-165`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/app-ui.mjs:56-60`; `app/host/server/open-text-file.mjs:26-29`; `app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。
- Strata の `process.env` にある値を直接削除する処理ではない。外部環境を作るたびに新しいオブジェクトを返し、元環境は保持される（`app/host/server/external-env.mjs:43-57,67-71`）。
- `externalEnvironment` の `extra` 引数は基底環境へ後から重ねられるため、呼び出し側が同名キーを明示すれば追加・上書きできる（`app/host/server/external-env.mjs:63-71`）。調査した呼び出し元に `GI_TYPELIB_PATH` を明示して `extra` へ渡す処理は見つからなかった。
- Harness の子プロセスは追加で `KEEP` の許可リストを通る。この正規表現に `GI_TYPELIB_PATH` は含まれないため、起動元環境に値があっても通常の Harness 環境には含まれない（`app/host/server/agent/harness-runtime.mjs:20-36,80-83`）。
- OS、GPU backend、build macro、モデル状態による値判定の分岐はない。削除対象として列挙される条件は AppImage 環境の処理経路である（`app/host/server/external-env.mjs:17-26,43-71`）。

## 実行時の詳細

AppImage 起動用 `AppRun` はフックによる環境変更より前に起動元環境を `STRATA_ORIGINAL_ENV` へ記録する。Strata は外部環境の要求時にその記録をデコードし、復元できれば記録内容を基底環境にする。記録がなければ現在の環境を複製した後、`GI_TYPELIB_PATH` を含む `APPIMAGE_ONLY` の名前を削除する。AppImage 外で記録もなければ現在の環境をそのまま複製する（`app/desktop/scripts/repack-appimage.sh:79-85`; `app/host/server/external-env.mjs:28-57,60-71`）。

関数内 static cache はなく、環境オブジェクトは呼び出しごとに組み立てられる。したがって、その時点の `env` 引数（省略時は `process.env`）が参照される。関数は値を検証せず、待機やタイムアウトも行わない（`app/host/server/external-env.mjs:28-71`）。

この関数自体はログを出さず、終了もしない。外部プログラムが失敗した場合の処理は呼び出し元による。たとえば Linux のフォルダー選択は選択器を順に試し、失敗理由を結果に含めるが、`GI_TYPELIB_PATH` の除去を個別に記録したり、その値に結び付けたエラーを出したりはしない（`app/host/server/folder-dialog.mjs:117-145`）。

## 根拠

- `app/host/server/external-env.mjs:17-26` — AppImage 専用キー一覧と `GI_TYPELIB_PATH` の登録。
- `app/host/server/external-env.mjs:28-40` — 起動元環境記録の取得・デコード。
- `app/host/server/external-env.mjs:43-57,60-71` — 条件分岐、キー削除、外部環境の生成。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage フック前に起動元環境を記録。
- `app/host/server/folder-dialog.mjs:117-145` — 外部プロセスへの適用とフォルダー選択失敗時の結果。
