# `GIO_EXTRA_MODULES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの値をアプリ機能の設定として解釈しない。ホスト側の `external-env.mjs` が、外部プログラムへ渡す環境を組み立てる際、AppImage 自身用の変数として扱う。AppImage 由来の環境を掃除する経路では、現在の値を外部プログラムへ渡さない。起動元環境の記録が使える経路では、その記録に含まれる値を復元して渡す。AppImage 外で記録もない場合は、呼び出し元の環境をそのまま渡す（`app/host/server/external-env.mjs:17-24,43-57,64-70`）。

この環境組み立て関数はフォルダー選択（`zenity`、`kdialog`、`gdbus`）、ファイル・URL を開く処理、デスクトップ通知、およびエージェントの子プロセス環境などで使われる（`app/host/server/folder-dialog.mjs:117-126,135-164`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/app-ui.mjs:39-47,57-60`; `app/host/server/agent/harness-runtime.mjs:25-36`）。

## 値と判定

値の内容、空文字、数値、大小文字は解析・比較されない。`withoutAppImage` が環境オブジェクトを複製した後、変数名のリストに従ってキーを無条件で削除するため、空文字を含め値が設定されていれば同じ扱いになる（`app/host/server/external-env.mjs:17-24,43-57`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `APPIMAGE` と `APPDIR` がともに偽で、`STRATA_ORIGINAL_ENV` も空／未設定 | `externalEnvironment` は入力環境を複製して渡す。キーがなければ未設定のまま | `''`、`/some/modules` など、キーがあればその値をそのまま渡す | 該当なし。値の妥当性検査はない |
| `APPIMAGE` または `APPDIR` が真、もしくは `STRATA_ORIGINAL_ENV` が設定済み | 有効な起動元記録にこのキーがなければ渡されない。記録が使えない場合も `withoutAppImage` が削除 | 起動元記録に含まれる値（空文字も含む）は復元して渡される | 現在の AppImage 環境にある値は記録が使えない場合に削除。記録が使える場合は現在値でなく記録の値が採用される |

起動元記録は `STRATA_ORIGINAL_ENV` の Base64 文字列を NUL 区切りの `NAME=value` として復元し、値の部分を文字列のまま格納する。`STRATA_ORIGINAL_ENV` 自体が偽なら記録なしとして扱う。記録を復元できない場合も AppImage 環境の掃除へフォールバックする（`app/host/server/external-env.mjs:28-40,67-70`）。

## 有効になる条件

- 環境整理は呼び出し元が `externalEnvironment` を使う外部プロセス起動に適用される。通常のプロセス起動や Strata 同梱エンジンの設定としてこの値を読む参照は見つからない（`app/host/server/external-env.mjs:2-9,64-70`）。
- `APPIMAGE` と `APPDIR` がともに偽で、`STRATA_ORIGINAL_ENV` も偽なら、値は変更されずに外部プロセスへ渡る（`app/host/server/external-env.mjs:60-70`）。
- AppImage 環境または起動元記録がある場合、`STRATA_ORIGINAL_ENV` を復元できれば記録内の環境が優先される。記録がない、空、または復元できない場合は AppImage 用変数として削除される（`app/host/server/external-env.mjs:28-40,43-57,67-70`）。
- エージェントの子プロセス環境では、`externalEnvironment` の結果をさらに許可リスト `KEEP` で絞る。`GIO_EXTRA_MODULES` は `KEEP` に含まれないため、この経路では AppImage 外であっても渡されない（`app/host/server/agent/harness-runtime.mjs:20-36`）。
- 読み取り側に OS/backend/build macro/CLI 引数による値判定はない。子プロセス側や外部ライブラリ側で値がどう作用するかは Strata の挙動として扱わない。

## 実行時の詳細

環境は外部プロセス起動時に `externalEnvironment` が呼ばれるたびに組み立てられ、関数内のキャッシュはない。引数 `env` の既定値はその時点の `process.env`。起動元記録が使える場合は記録全体を基にし、使えない AppImage 経路では現在の環境を複製して掃除する。関数の `extra` 引数が指定された場合は最後にマージされ、同名キーを上書きするが、確認した本番呼び出しでは第 2 引数の指定はない（`app/host/server/external-env.mjs:28-30,43-57,60-70`; 呼び出し例: `app/host/server/folder-dialog.mjs:117-126`, `app/host/server/chat-files.mjs:89-94`）。

Strata はこの変数自体について警告やエラーを出さず、値の不正を理由に終了もしない。フォルダー選択など外部プログラムの失敗は呼び出し元が個別に処理するが、その失敗原因をこの変数に結び付ける Strata の分岐はない（`app/host/server/folder-dialog.mjs:123-145`; `app/host/server/chat-files.mjs:89-94`）。

## 根拠

- `app/host/server/external-env.mjs:17-24` — AppImage 専用変数リストにこの名前がある。
- `app/host/server/external-env.mjs:28-40` — 起動元環境記録の復元方法。
- `app/host/server/external-env.mjs:43-57` — AppImage 専用変数を無条件削除する処理。
- `app/host/server/external-env.mjs:60-70` — AppImage 判定、分岐、起動元環境・追加環境の優先順位。
- `app/host/server/folder-dialog.mjs:117-145,153-166` — フォルダー選択プロセスへ環境を渡し、その失敗を処理する箇所。
- `app/host/server/chat-files.mjs:89-94` — ファイル／URL を開く子プロセスへ環境を渡す箇所。
- `app/host/server/app-ui.mjs:39-47,57-60` — opener と通知プロセスへの環境引き渡し。
- `app/host/server/agent/harness-runtime.mjs:20-36` — エージェント子プロセスの許可リストによる追加フィルター。
