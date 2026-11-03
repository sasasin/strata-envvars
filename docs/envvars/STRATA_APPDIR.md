# `STRATA_APPDIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の Node host は `STRATA_APPDIR` を設定値として読みません。値の比較・パース・パス処理もありません。一方、外部プログラム用の環境を組み立てる helper では、この名前を AppImage tooling 専用変数の一覧に含めています。旧式の AppImage 環境を掃除する経路では、このキーを子プロセス用環境から削除します（`apps/host/server/external-env.mjs:17-24,43-57`）。

この環境処理はフォルダー選択、ファイルや URL を開く処理、通知、coding assistant の Harness 起動など、外部プログラムを起動する経路で使われます。`STRATA_APPDIR` 自体がこれらの機能を有効化したり、Strata の engine の動作を変えたりする条件はありません（例: `apps/host/server/folder-dialog.mjs:117-126,153-164`, `apps/host/server/artifacts.mjs:5-6`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

## 値と判定

Strata はこの変数の値を読み取らないため、未設定・空文字・任意の値の間に `STRATA_APPDIR` 固有の分岐はありません。数値変換、文字列比較、値域検査、既定値もありません。処理対象になるのは値ではなく、環境オブジェクトにこのキーがあるかどうかです。

| `externalEnvironment()` の条件 | 外部プログラム用環境での扱い |
|---|---|
| `APPIMAGE` と `APPDIR` がどちらも falsy、かつ `STRATA_ORIGINAL_ENV` も falsy | 現在の環境をコピーするため、`STRATA_APPDIR` は存在すればそのまま引き継がれる。 |
| AppImage 条件、または truthy な `STRATA_ORIGINAL_ENV` があり、記録から元環境を復元できる | 現在の環境ではなく復元した元環境を使う。`STRATA_APPDIR` は元環境にあればその値で渡り、なければ渡らない。 |
| AppImage 条件、または truthy な `STRATA_ORIGINAL_ENV` があるが、元環境を復元できない | 現在の環境をコピーし、`APPIMAGE_ONLY` の一括削除で `STRATA_APPDIR` を除く。 |

元環境記録は base64 を UTF-8 文字列に戻し、NUL 区切りの `NAME=value` をオブジェクト化します。空の記録値は復元を試みず、復元後のオブジェクトが空の場合も復元失敗として扱います。`externalEnvironment()` の `extra` 引数があれば最後に追加されるため、同じキーを明示した場合はその値が追加・上書きされます（`apps/host/server/external-env.mjs:28-40,63-70`）。

## 有効になる条件

掃除経路への分岐は OS や backend の判定ではなく、`APPIMAGE` または `APPDIR` の truthiness、あるいは `STRATA_ORIGINAL_ENV` の truthiness で決まります。AppImage 起動時の元環境記録を加える hook は Linux AppImage 再梱包スクリプトにあります（`apps/desktop/scripts/repack-appimage.sh:52-58`）。この記録が有効なら現在の `STRATA_APPDIR` は掃除されず、記録された元環境の内容に置き換わります。

## 実行時の詳細

`withoutAppImage()` は呼び出し時に渡された環境（既定では `process.env`）をコピーし、`APPIMAGE_ONLY` の各キーを無条件に `delete` します。この一覧に `STRATA_APPDIR` があるため、掃除経路では値が空かどうかにかかわらず除去されます。親プロセスの `process.env` 自体は変更しません（`apps/host/server/external-env.mjs:17-24,43-57`）。

`externalEnvironment()` は呼び出されるたびに環境を選び直し、`STRATA_APPDIR` 用の cache はありません。Strata がこの名前について警告、ログ、終了、失敗処理を行う箇所は見つかりません。子プロセスへ値を渡すかどうかは上記の環境選択と呼び出し側の `extra` によります。外部プログラムが受け取った値をどう解釈するかは本調査の対象外です。

## 根拠

- 候補名の唯一の Strata ソース参照と AppImage 専用キー一覧: `apps/host/server/external-env.mjs:17-26`。
- 元環境の復元、コピー後のキー削除、AppImage 条件、外部環境の選択: `apps/host/server/external-env.mjs:28-71`。
- 再梱包時に起動元環境を記録する hook: `apps/desktop/scripts/repack-appimage.sh:52-58`。
- 外部環境 helper の主な適用例: `apps/host/server/folder-dialog.mjs:112-126,153-164`, `apps/host/server/artifacts.mjs:5-6`, `apps/host/server/app-ui.mjs:38,56-59`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/agent/harness-runtime.mjs:25-36,75-83`。
