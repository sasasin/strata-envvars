# `STRATA_UPDATE_APP_ENDPOINT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata Desktop アプリ内の署名付きアプリ更新が参照する更新 endpoint を、実行時に差し替えます。ソースコメントでは用途をローカルテスト feed とし、受け付ける URL は HTTPS または loopback HTTP に制限しています。これは Desktop アプリ本体の更新用です。モデルや engine の更新（`strata update`）には使われません（`apps/desktop/src-tauri/src/updater.rs:11-14,24-25`）。

未設定、空文字、または許可 prefix に一致しない値では、アプリ設定の endpoint を使います。設定ファイルの既定 endpoint は `https://github.com/Niko1221/Strata/releases/latest/download/latest.json` です（`apps/desktop/src-tauri/src/updater.rs:51-67`、`apps/desktop/src-tauri/tauri.conf.json:65-74`）。

## 値と判定

| 環境値 | Strata の判定と処理 |
| --- | --- |
| 未設定 | `std::env::var` が値を返さず override なし。設定済み endpoint に戻る。 |
| Unicode でない値 | `std::env::var(...).ok()?` が `None` になるため override なし。 |
| 空文字 | どの prefix にも一致しないため override なし。 |
| `https://` で始まる値 | override 候補として受理し、URL parse と updater 構築へ進む。 |
| `http://127.0.0.1:` で始まる値 | 同上。 |
| `http://localhost:` で始まる値 | 同上。 |
| 上記以外 | override なし。設定済み endpoint に戻る。 |

prefix 判定は大文字小文字を区別する `starts_with` で、値全体の形式をここでは検査しません。したがって `HTTPS://...` や `http://example.com/...` は override として扱われません。許可 prefix に続く文字列は `tauri::Url` に parse され、失敗すると `bad update endpoint: ...` エラーになります。その場合は設定済み endpoint への fallback はしません。parse 後も `endpoints(vec![url])` または `build()` が失敗すればエラーを返します（`apps/desktop/src-tauri/src/updater.rs:51-67`）。

## 有効になる条件

- Desktop Tauri アプリの updater bridge が起動している必要があります。Windows/macOS では embedded app の `start_host` が bridge を起動し（`apps/desktop/src-tauri/src/main.rs:495-505`）、Linux では window process の setup が bridge を起動して App Host に登録します（`apps/desktop/src-tauri/src/main.rs:1134-1179`）。
- endpoint の読み取り・更新確認はアプリ起動時には行われません。ユーザー操作に応じた bridge の `GET /app-update/check` または `POST /app-update/install` が updater を作る時点で評価されます（`apps/desktop/src-tauri/src/updater.rs:13-14,60-72,80-94,197-210`）。
- 環境値の判定は `endpoint_override()` 内に保存されず、check/install ごとの `updater_for()` 呼び出しで再実行されます。読み取り結果を保持する cache はありません（`apps/desktop/src-tauri/src/updater.rs:51-67,70-72,80-90`）。
- CLI 引数や別環境変数との優先順位分岐はこの実装にありません。候補 endpoint が有効な場合は `updater_builder().endpoints(vec![url])` に一件を設定し、候補がない場合は `app.updater()` を使います（同:60-67）。

## 実行時の詳細

check 経路では `updater_for()` のエラーは bridge から `502 Bad Gateway` と JSON の `error` に返されます。check 成功時は更新有無、version、current、notes が返ります（`apps/desktop/src-tauri/src/updater.rs:70-78,197-200`）。

install 経路では、POST の受理時に `202 Accepted` が返されてからバックグラウンド処理が始まります。endpoint 判定・構築、check、download などで失敗すると progress の `state` が `error` になり、エラー文字列が `error` フィールドに設定されます。進行状態は `GET /app-update/status` で確認できます。更新がない場合の実装上の文言は `There is no newer version of the Strata app.` です（`apps/desktop/src-tauri/src/updater.rs:80-94,201-212`）。

この bridge は loopback listener を開けない場合 `None` を返し、インアプリ更新を提供しません。ソースコメントでは Terminal の `strata update --app` は引き続き利用できるとしています（`apps/desktop/src-tauri/src/updater.rs:227-240`）。これは環境変数による endpoint 上書きとは別の実行経路です。

## 根拠

- 全参照の検索では、候補名は `apps/desktop/src-tauri/src/updater.rs:25` の定数、同ファイルの本番読み取り `:52`、および `#[cfg(test)]` 内のテスト設定・解除 `:282-286` にありました。リポジトリ内の他の本番参照は見つかりませんでした。
- 環境値の取得、許可 prefix、parse、設定 endpoint への切り替え: `apps/desktop/src-tauri/src/updater.rs:51-67`。
- check/install での updater 生成と結果の返却: `apps/desktop/src-tauri/src/updater.rs:70-94,197-212`。
- Desktop の bridge 起動経路: `apps/desktop/src-tauri/src/main.rs:495-505,1134-1179`。
- 設定 endpoint: `apps/desktop/src-tauri/tauri.conf.json:65-74`。
