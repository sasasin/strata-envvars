# `APPDIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。外部ライブラリや AppImage runtime 自身の挙動は対象外。

## 役割

Strata は `APPDIR` を Linux AppImage のマウント先ディレクトリとして扱います。ホストサーバーは外部プログラム用の環境を作るとき、AppImage 固有の変数として `APPDIR` を除去し、さらに `APPDIR` 配下を指すパスを環境から取り除きます。これはフォルダー選択、ファイルを開く処理、通知、アシスタント用 shell などの子プロセスに適用されます（`apps/host/server/external-env.mjs:17-26,43-70`）。

Linux デスクトップの診断処理では、`APPDIR` を使って同梱 WebKitGTK のファイルを探し、値自体も graphics session の環境情報に記録します（`apps/desktop/src-tauri/src/desktoplog.rs:186-212,241-259,310-319`）。通常の model / engine 動作や CLI の設定を変える読み取りではありません。

## 値と判定

値の数値変換や文字列 parse はありません。Node.js 側は JavaScript の truthiness と文字列 prefix 判定を使い、Rust 側は OS の環境値をパスとして扱います。

| 状態 | ホストの外部環境処理 | Linux デスクトップ診断 |
|---|---|---|
| 未設定 | `APPIMAGE` も `STRATA_ORIGINAL_ENV` もなければ環境を複製するだけで、AppImage 用の除去処理は行わない。 | `var_os` が `None` となり、WebKit 欄は `not an AppImage (the system's WebKitGTK is used)`。graphics session の一覧にも出ない。 |
| 空文字 | 単独では falsy のため AppImage 起動と判定されない。`APPIMAGE` または `STRATA_ORIGINAL_ENV` が truthy の場合は除去対象名として `APPDIR` が削除されるが、空のディレクトリ prefix によるパス整理は行われない。 | 空文字も設定値（`Some`）として扱われ、相対パス `usr/lib` を探索する。graphics session では `APPDIR=` と記録される。 |
| 空でない値 | `APPDIR` 単独でも AppImage 起動と判定される。保存済み元環境がなければ値をディレクトリ prefix として使い、その環境値自体は外部向け環境から削除する。 | 値を `PathBuf` にして `<APPDIR>/usr/lib` を列挙し、名前が `libwebkit2gtk-4.1.so` または `libjavascriptcoregtk-4.1.so` で始まる項目を探す。 |

Node.js 側で prefix として削除されるのは、値が `APPDIR` と完全一致するか、`APPDIR/` または `APPDIR//` で始まる場合です。GTK/GDK/GIO/GST/GI_/GSETTINGS/WEBKIT で始まる名前の環境変数では値に `APPDIR` が含まれるものを変数ごと削除し、PATH 系変数では `:` 区切りの各要素から該当 prefix を除いて再結合します。空要素も取り除き、残る要素がなければその変数を削除します。値の正規化や大文字小文字変換はありません（`apps/host/server/external-env.mjs:25-26,43-57`）。

## 有効になる条件

- 外部向け環境の切り替えは、`APPIMAGE || APPDIR` が truthy、または `STRATA_ORIGINAL_ENV` が truthy のときに行われます。CLI 引数による優先順位はありません（`apps/host/server/external-env.mjs:60-70`）。
- AppImage launcher が挿入する `STRATA_ORIGINAL_ENV` の記録を復元できれば、それを外部プログラム用環境に使います。記録がない、空、または decode 後に有効な環境項目がない場合は、現在の環境から AppImage 固有値や AppImage 配下のパスを除去する fallback です。`extra` 引数が渡された場合は最後にマージされるため同名項目を上書きできます（`apps/host/server/external-env.mjs:28-41,64-70`）。
- `APPDIR` による診断出力は desktop shell の Linux ログ機能にあります。`bundled_webkit()` は `APPDIR` が未設定なら AppImage 内を検索せず、設定時に `<APPDIR>/usr/lib` の読み取りが失敗するか対象ファイルがなければ `no WebKitGTK file found in the AppImage` を返します（`apps/desktop/src-tauri/src/desktoplog.rs:196-212`）。
- `graphics_environment()` は `std::env::var` が成功した変数のみ出力します。`APPDIR` が非 Unicode の OS 環境値ならこの一覧には現れませんが、`bundled_webkit()` の `var_os` によるパス探索では扱えます（`apps/desktop/src-tauri/src/desktoplog.rs:187-194,197-199`）。

## 実行時の詳細

ホスト側の環境処理は `externalEnvironment()` を呼ぶたびに環境オブジェクトを読み、キャッシュしません。AppImage launcher は Strata 固有の環境 hook を加える前に起動元環境を `STRATA_ORIGINAL_ENV` として記録するコードを AppRun に挿入します（`apps/desktop/scripts/repack-appimage.sh:52-59`）。有効な記録を復元した場合、外部子プロセスにはその元環境を渡します。記録が使えない場合は `withoutAppImage()` が現在の環境を複製して `APPDIR` を含む AppImage 固有変数を除きます。呼び出し先は `spawn` / `execFile` の `env` にこの結果を渡します（例: `apps/host/server/chat-files.mjs:89-94`、`apps/host/server/folder-dialog.mjs:106-115`）。

Linux デスクトップでは `bundled_webkit()` の結果と `graphics_environment()` がクラッシュレポートに含まれ、`--save-logs` の出力にも含まれます。これは診断テキストへの出力とファイル探索であり、`APPDIR` が WebKit の選択や起動を制御する分岐ではありません（`apps/desktop/src-tauri/src/desktoplog.rs:241-259,310-319`）。どちらも診断文書を組み立てる時点で環境を参照し、`APPDIR` の値を別途 cache しません。

## 根拠

- 全参照の確認: `apps/host/server/external-env.mjs:19,45,48-55,61`、`apps/desktop/src-tauri/src/desktoplog.rs:191,198`。その他の一致はパッケージ処理またはテスト fixture であり、追加の本番読み取りではありません。
- 外部プログラム向け環境の生成と元環境の復元: `apps/host/server/external-env.mjs:28-70`。
- 外部環境の子プロセス利用: `apps/host/server/chat-files.mjs:89-94`、`apps/host/server/folder-dialog.mjs:106-115,142-147`、`apps/host/server/agent/harness-runtime.mjs:25-33,78-83`。
- Linux desktop 診断ログでの値出力・同梱 WebKit 探索: `apps/desktop/src-tauri/src/desktoplog.rs:186-212,241-259,310-319`。
- AppRun への起動元環境記録の挿入: `apps/desktop/scripts/repack-appimage.sh:52-59`。

`docs/DETAILS.md` には `APPDIR` の個別設定説明や測定値は見当たらず、本書に性能・正確性の主張は含めていません。
