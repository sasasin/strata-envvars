# `GST_PTP_HELPER_1_0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の推論や通常のアプリ設定を制御する読み取り箇所は見つからなかった。Strata がこの名前を使うのは、外部プログラム向け環境を作る `app/host/server/external-env.mjs` の AppImage 専用名リストである。このため「有効値」を解析するのではなく、外部プロセスへ渡す環境を選ぶ際に値を保持するか、名前ごと削除するかが変わる（`app/host/server/external-env.mjs:17-24,43-57,64-71`）。

## 値と判定

`GST_PTP_HELPER_1_0` 自体の値は読み出し・比較・変換されない。`withoutAppImage()` は `APPIMAGE_ONLY` に列挙された名前をコピー先から無条件に削除する。したがってこの分岐では unset、空文字、`0`、`1`、その他の文字列に差はない（`app/host/server/external-env.mjs:17-24,43-57`）。

| 条件 | unset | 設定時の扱い |
| --- | --- | --- |
| `APPIMAGE` と `APPDIR` がともに falsy で、`STRATA_ORIGINAL_ENV` も falsy | 変更なし | `externalEnvironment()` は元の環境を複製するため、空文字を含めてそのまま渡す |
| AppImage 内、または `STRATA_ORIGINAL_ENV` が truthy で、記録から元環境を復元できる | 記録に従う | 記録された元環境にこの名前があれば、その値を解釈せず保持する |
| AppImage 内、または `STRATA_ORIGINAL_ENV` が truthy だが、有効な元環境を復元できない | 削除 | `withoutAppImage()` が設定値の内容によらず削除する |

`STRATA_ORIGINAL_ENV` は truthy なとき Base64 を UTF-8 に復号し、NUL 区切りの `NAME=value` を組み立てる。空の記録値、復号後に有効な名前がない場合、または復号例外の場合は元環境なしとして扱い、AppImage 環境の除去に進む。復元可能な場合は `externalEnvironment()` の `extra` が最後に結合され、同名なら `extra` の値が優先する（`app/host/server/external-env.mjs:28-40,67-71`）。

## 有効になる条件

- 一般の外部プログラム向け環境では、Strata が AppImage 内で動作するか、`STRATA_ORIGINAL_ENV` が設定されているときに環境の選択処理が働く。AppImage 判定は `APPIMAGE` または `APPDIR` の truthy 判定である（`app/host/server/external-env.mjs:60-70`）。
- フォールバックの `withoutAppImage()` では値に関係なく削除される。復元した起動元環境を使う場合や、AppImage 外かつ記録なしの場合には、このリストによる削除は行われない（同 `:43-57,67-71`）。
- Harness 子プロセス用 `agentEnvironment()` は、環境を `KEEP` の名前パターンに限定する。この名前は許可パターンに含まれないため、親環境からは AppImage 条件にかかわらず除外される。ただし関数の `extra` は最後に結合されるため、呼び出し側が明示的に同名を渡した場合は含まれ得る（`app/host/server/agent/harness-runtime.mjs:20-36,80-83`）。
- CLI、モデル状態、GPU backend、OS に応じてこの名前の値を有効化する Strata 側の分岐はない。

## 実行時の詳細

`externalEnvironment()` は呼び出し時の `env`（既定は `process.env`）を使い、対象名を含む環境オブジェクトを作る。判定結果をプロセス全体のキャッシュに保存する処理はない。ブラウザー起動、フォルダー選択、ファイルを開く処理などがこの関数の結果を子プロセスへ渡す（`app/host/server/app-ui.mjs:39-47,51-59`; `app/host/server/folder-dialog.mjs:112-127,135-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/open-text-file.mjs:26-29`）。

Harness の起動時には `agentEnvironment(process.env, ...)` が環境を作り、フィルター後の環境を `spawn()` に渡す（`app/host/server/agent/harness-runtime.mjs:26-36,75-83`）。この変数について Strata 自身がログ、警告、終了コードを出す処理は確認できない。子プロセスや外部ライブラリがこの変数をどう解釈するかは本調査の対象外である。

## 根拠

- `app/host/server/external-env.mjs:17-24` — AppImage 専用名の定義。
- `app/host/server/external-env.mjs:28-40,43-57,60-71` — 起動元環境の復元、名前の削除、外部環境の選択。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 環境の許可リストと子プロセス起動。
- `app/host/server/app-ui.mjs:39-59`; `app/host/server/folder-dialog.mjs:112-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/open-text-file.mjs:26-29` — 外部プログラムへ渡す箇所。

`docs/DETAILS.md` に本変数またはこの環境整形の説明は見当たらず、上記の Strata ソースを根拠とした。
