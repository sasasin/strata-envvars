# `GTK_DATA_PREFIX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `GTK_DATA_PREFIX` を GTK の設定値として解釈しません。Node.js ホストの `externalEnvironment()` が、AppImage 起動時に注入された環境をシステムの外部プログラムへ渡すときに、この名前を AppImage 専用変数として扱います。AppImage の元環境を記録した `STRATA_ORIGINAL_ENV` が使える場合は元の環境を戻し、記録がない旧式 AppImage 経路ではこの名前を外部環境から削除します（`app/host/server/external-env.mjs:17-24,43-57,63-71`）。

## 値と判定

`GTK_DATA_PREFIX` 自体の文字列は parse・比較・変換されません。`withoutAppImage()` が `APPIMAGE_ONLY` の各名前を複製環境から無条件に削除するため、旧式 AppImage 経路では未設定・空文字・任意の非空文字のいずれも外部環境には残りません。通常の非 AppImage 経路では環境オブジェクトをコピーするだけなので、未設定は未設定、空文字やその他の値はそのままです。元環境記録がある経路では記録をデコードして作った元環境が使われ、記録中に `GTK_DATA_PREFIX=` があれば空文字も保持され、キーがなければ未設定です（`app/host/server/external-env.mjs:28-40,43-57,63-71`）。

| 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 非 AppImage、`STRATA_ORIGINAL_ENV` なし | 未設定のまま | なし。値を解釈しない | なし。値を解釈しない |
| AppImage または元環境記録あり、記録を復元できる | 元環境でも未設定なら未設定 | なし。記録中の値をそのまま外部環境へ戻す | なし。空文字を含め、記録中の値をそのまま戻す |
| AppImage の元環境記録を復元できない旧式経路 | 外部環境でも未設定 | なし | 設定の有無・値にかかわらず削除 |

`1`、`0`、`true`、`false`、空白付き文字列などに特別な意味はありません。数値妥当性、大文字小文字、境界値の検証もありません。ここでの実質的な分岐は値ではなく、起動元環境を復元できるかです（`app/host/server/external-env.mjs:30-40,44-55,67-70`）。

## 有効になる条件

- 外部プログラム向けの環境を作る箇所で `externalEnvironment()` が呼ばれること。通常は呼び出し時点の `process.env` を使います（`app/host/server/external-env.mjs:67-71`）。
- `APPIMAGE` または `APPDIR` が設定されている、あるいは `STRATA_ORIGINAL_ENV` が設定されている場合に AppImage 用の分岐へ入ります。どちらもなく記録もなければ環境はコピーされるだけです（`app/host/server/external-env.mjs:60-70`）。
- AppImage 用分岐では、復元可能な `STRATA_ORIGINAL_ENV` があれば記録した起動元環境を返します。記録を復元できなければ `withoutAppImage()` が `GTK_DATA_PREFIX` を含む AppImage 専用名を削除します（`app/host/server/external-env.mjs:28-40,43-57,67-71`）。
- Linux のフォルダ選択では zenity、kdialog、gdbus にこの環境が渡されます。ファイル・フォルダを開く xdg-open、通知の notify-send、テキストエディタ探索の補助コマンドなども同じ関数を使います（`app/host/server/folder-dialog.mjs:112-127,135-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/app-ui.mjs:39-47,57-60`; `app/host/server/open-text-file.mjs:26-29`; `app/host/server/artifacts.mjs:5-6`）。これらの外部プログラムや GTK 自身が受け取った値をどう扱うかは Strata の動作としては説明しません。
- Harness の子プロセスでは `externalEnvironment()` の結果をさらに `KEEP` 許可リストで絞るため、`GTK_DATA_PREFIX` は通常の継承環境から落ちます。`agentEnvironment()` の `extra` は最後に重ねられ、Harness 起動時の `extra` は `profile.env` と `DSH_HOME` です。コード上、`GTK_DATA_PREFIX` をその `profile.env` に固定で加える処理はありません（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`; `app/host/server/agent/agent-bridge.mjs:303-305`）。

## 実行時の詳細

値を読む専用の `process.env.GTK_DATA_PREFIX` や設定 cache はありません。`externalEnvironment()` は呼び出しごとに渡された環境オブジェクト（省略時は `process.env`）を判定し、通常経路では浅いコピーを、AppImage 経路では復元環境または除去済みコピーを返します。したがって、このヘルパーに渡す環境を呼び出し間で変更すれば次の呼び出しに反映されます。すでに起動した子プロセスの環境は後から変更されません。AppImage の `STRATA_ORIGINAL_ENV` はランチャーがフックで `env -0 | base64 -w0` を記録し、Strata 側はその記録から元環境を復元します（`app/desktop/scripts/repack-appimage.sh:79-85`; `app/host/server/external-env.mjs:28-40,43-57,67-71`）。

`extra` 引数を指定した場合は最後に追加・上書きされますが、通常の外部プログラム呼び出しはこれを指定していません（`app/host/server/external-env.mjs:63-71`）。Harness 経路では許可リストの後に呼び出し元の `profile.env` が重なります（`app/host/server/agent/harness-runtime.mjs:26-36,80-83`; `app/host/server/agent/agent-bridge.mjs:303-305`）。

## ログと測定値

この変数の削除・保持を示す専用ログ、警告、終了コードはありません。フォルダ選択などで外部プログラムが失敗した場合の一般的な失敗処理はありますが、`GTK_DATA_PREFIX` による失敗だと識別するログではありません（`app/host/server/folder-dialog.mjs:108-115,123-145`）。測定値は該当しません。

## 根拠

- `app/host/server/external-env.mjs:17-24` — `GTK_DATA_PREFIX` を含む AppImage 専用名の列挙。
- `app/host/server/external-env.mjs:28-40,43-57,60-71` — 元環境の復元、旧式環境の除去、AppImage 判定、外部環境の組み立て。
- `app/host/server/folder-dialog.mjs:112-127,135-164` — Linux フォルダ選択プログラムへの環境引き渡し。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 環境の許可リストと追加環境。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage ランチャーによる元環境記録。
