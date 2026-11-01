# `GSETTINGS_SCHEMA_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 自身が値を設定読み込みや GTK/GSettings の動作制御に使う実装は見つからない。Strata がこの名前を扱うのは、外部プログラム用の子プロセス環境を作るときである。AppImage の内部用環境が外部プログラムへ漏れないよう、古い AppImage から起動された場合は値を除去する。一方、起動元の環境を記録した AppImage では、外部プログラムに起動元の環境を復元する。通常の AppImage 外の起動では値をそのまま引き継ぐ。

Strata はこの値の内容を parse せず、存在・空文字・パスの妥当性による機能分岐もしない。外部ライブラリが値をどう使うかは本調査の対象外。

## 値と判定

| 状況 | Strata の処理 |
|---|---|
| 通常起動（`APPIMAGE`、`APPDIR`、`STRATA_ORIGINAL_ENV` がない） | `process.env` のコピーを返すため、値が設定されていればそのまま、未設定なら未設定のまま。空文字も変更しない。 |
| AppImage 起動で `STRATA_ORIGINAL_ENV` が有効な記録を含む | 記録した起動元環境を復元する。起動元にこの変数があればその値を渡し、なければ渡さない。 |
| AppImage 起動で記録がない、または記録を復元できない | `withoutAppImage()` が `APPIMAGE_ONLY` に列挙された名前を値に関係なく削除するため、この変数は外部環境から除かれる。 |
| agent / shell 用環境 | `externalEnvironment()` の結果をさらに `KEEP` allowlist で絞る。`GSETTINGS_SCHEMA_DIR` は allowlist に含まれないため除外される。 |

値の変換、数値境界、無効値 fallback はない。`externalEnvironment(env, extra)` の `extra` に同名キーが与えられると最後に上書き・追加される API だが、調査対象 commit の本番呼び出し箇所は `extra` を渡していない。

## 有効になる条件

この処理は GPU backend、モデル状態、CLI 引数には依存しない。AppImage の起動状態と環境記録の有無で外部子プロセス向け環境が変わる。

`externalEnvironment()` は、`APPIMAGE` と `APPDIR` のどちらもなく、`STRATA_ORIGINAL_ENV` もない場合には環境をそのままコピーする。いずれかがある場合は、まず `STRATA_ORIGINAL_ENV` を base64 decode し、NUL 区切りの `NAME=value` を復元する。復元できる項目が一つもない場合は記録なしとして `withoutAppImage()` に進む。復元成功時は元の環境だけを返すので、AppImage が加えた値は引き継がれない。

## 実行時の詳細

`withoutAppImage()` は `GSETTINGS_SCHEMA_DIR` を `APPIMAGE_ONLY` に固定列挙し、値を調べず削除する。AppImage の `APPDIR` が分かる場合には `GSETTINGS` で始まり `APPDIR` を含む環境値を削除する追加処理もあるが、この名前は先に固定リストで削除される。AppImage ランチャー側では `env -0 | base64 -w0` を `STRATA_ORIGINAL_ENV` に記録するフックを追加する。

`externalEnvironment()` はフォルダー選択の Linux chooser（zenity、kdialog、gdbus）、ブラウザー起動、通知、ファイルを開く処理など外部プログラムに渡される。agent Harness の子プロセス環境にも基礎として使われるが、そこでさらに allowlist が適用されるため `GSETTINGS_SCHEMA_DIR` は渡らない。該当処理は起動時に各子プロセスの `env` を生成するもので、Strata 内にこの変数値の cache はない。プロセス実行中に親環境を書き換えた場合の反映を制御するコードもない。

この変数固有のログ、警告、終了・失敗経路はない。外部プログラムの起動成否は各呼び出し元で処理されるが、ソース上で `GSETTINGS_SCHEMA_DIR` の値と結び付けたログやエラーは確認できない。

## 根拠

- `apps/host/server/external-env.mjs:17-26,43-57`: AppImage 専用変数の一覧と、`withoutAppImage()` による無条件削除。AppImage パスを含む GTK/GDK/GIO/GST/GI/GSETTINGS/WEBKIT 系値の除去。
- `apps/host/server/external-env.mjs:28-41,60-71`: 記録環境の復元条件、AppImage 判定、通常環境コピー・復元・除去の選択、および `extra` の上書き順。
- `apps/desktop/scripts/repack-appimage.sh:56-58`: AppImage ランチャーに起動元環境を `STRATA_ORIGINAL_ENV` として記録する処理。
- `apps/host/server/folder-dialog.mjs:106-120,146-158`, `apps/host/server/app-ui.mjs:38-58`, `apps/host/server/artifacts.mjs:5-8`, `apps/host/server/chat-files.mjs:85-94`, `apps/host/server/open-text-file.mjs:26-29`: 外部プログラム起動に外部環境を渡す呼び出し例。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83`: agent 環境の allowlist と子プロセスへの設定。`GSETTINGS_SCHEMA_DIR` は `KEEP` に一致しない。
- `apps/host/tests/external-env.test.mjs:13-33,35-48`: テスト用入力での除去、元環境復元、AppImage 外で変更しないことの確認（本番挙動の根拠は上記実装）。
