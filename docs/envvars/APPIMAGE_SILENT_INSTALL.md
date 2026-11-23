# `APPIMAGE_SILENT_INSTALL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの値を設定として解釈しない。Node host の `external-env.mjs` で AppImage 専用変数名の一つとして登録し、起動元の環境を復元できない場合に外部プログラムへ渡す環境から名前ごと除去する（`app/host/server/external-env.mjs:17-24,43-57,67-71`）。値による分岐や真偽判定はない。

この処理は、フォルダ選択ダイアログ、ファイルや URL を開く処理、通知、agent harness など、`externalEnvironment()` を使う子プロセスの環境に関係する（`app/host/server/folder-dialog.mjs:112-145,153-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/app-ui.mjs:39-42,57-60`; `app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

## 値と判定

`APPIMAGE_SILENT_INSTALL` の値は読み取らず、文字列比較・数値変換・空文字判定をしない。挙動を決めるのは値ではなく、呼び出し元の環境にキーがあるか、AppImage 起動元環境の記録が復元できるかである（`app/host/server/external-env.mjs:15-24,29-40,43-57,61-71`）。

| 条件 | unset | 空文字 | 値の例（`0`、`1`、`true`、`false`、`0anything` 等） |
| --- | --- | --- | --- |
| AppImage 外で `APPIMAGE` / `APPDIR` も `STRATA_ORIGINAL_ENV` もない | そのまま（キーなし） | 該当なし | 該当なし |
| AppImage の環境が検出され、記録を復元できない | 出力にもキーなし | `withoutAppImage()` がキーを削除 | 値を問わずキーを削除 |
| `STRATA_ORIGINAL_ENV` の記録を正常に復元できる | 記録された元環境の内容による | 元環境に空文字で記録されていれば空文字を保持 | 元環境に記録されていれば値をそのまま保持 |

`externalEnvironment(env, extra)` の `extra` に同名キーが明示されていれば最後に結合されるため、削除後でもその値が渡る。確認できた実際の呼び出しは `externalEnvironment()` または `externalEnvironment(base)` で、`extra` の指定はない（`app/host/server/external-env.mjs:67-71`; 上記呼び出し箇所）。

## 有効になる条件

- この名前に応じて機能を有効化する値はない。AppImage 専用名リストにあるため、元環境の復元に失敗してクリーンアップ経路へ進んだ場合に限り、子プロセス環境から削除される（`app/host/server/external-env.mjs:17-24,43-57,67-71`）。
- `externalEnvironment()` は `APPIMAGE` または `APPDIR` が truthy なら AppImage 内と判定する。これらがなくても `STRATA_ORIGINAL_ENV` が truthy なら変換経路に入る。復元可能な記録があれば、その記録内容を使い、この名前を個別には削除しない（`app/host/server/external-env.mjs:15,29-40,43-47,60-71`）。
- 記録の作成コードは AppImage の `AppRun` で `env -0` の結果を `STRATA_ORIGINAL_ENV` に記録する（`app/desktop/scripts/repack-appimage.sh:80-85`）。このため正常な記録経路では、この名前が記録に含まれている場合そのまま復元され得る。
- 対象の判定に OS、backend、build macro、CLI 引数、モデル状態は使われない。ここで確認できる環境加工は Node host の外部プログラム起動経路で行われる。

## 実行時の詳細

`withoutAppImage()` は呼び出し時の `env` を浅く複製し、`APPIMAGE_ONLY` に列挙されたキーを値に関係なく削除する。`externalEnvironment()` は、AppImage でも記録付きでもないときは環境の複製を返し、それ以外では `STRATA_ORIGINAL_ENV` を Base64 として復号・解析して元環境を組み立てる。復元できないときだけ `withoutAppImage()` にフォールバックする（`app/host/server/external-env.mjs:17-24,28-57,60-71`）。

対象値を別の場所へキャッシュする処理はない。既定引数の `process.env` または明示された `env` を関数呼び出し時に参照し、返された環境オブジェクトが各 `spawn` / `execFile` に渡される。起動済み子プロセスの環境は後から変更されない（`app/host/server/external-env.mjs:29,44,61,67-71`; `app/host/server/folder-dialog.mjs:118-126,153-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/agent/harness-runtime.mjs:75-83`）。

## ログと測定値

この変数の値を理由に出すログ、警告、エラー、終了経路はない。環境のクリーンアップ自体もログを出さない（`app/host/server/external-env.mjs:43-57,67-71`）。フォルダ選択などの失敗表示は子プログラム実行の結果に基づくもので、この変数名や値を判定した結果ではない（例: `app/host/server/folder-dialog.mjs:124-145`）。性能測定値は該当しない。

## 根拠

- `app/host/server/external-env.mjs:17-24` — AppImage 専用名リストに対象名を含める。
- `app/host/server/external-env.mjs:43-57,60-71` — 環境の削除、AppImage 判定、起動元環境・クリーンアップ・`extra` の優先順。
- `app/desktop/scripts/repack-appimage.sh:80-85` — 起動元環境の記録を AppImage の `AppRun` に追加。
- `app/host/server/folder-dialog.mjs:112-145,153-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/app-ui.mjs:39-42,57-60`; `app/host/server/agent/harness-runtime.mjs:25-36,75-83` — 加工済み環境を外部プロセスへ渡す呼び出し例。
