# `STRATA_APP_UPDATE_PUBKEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査範囲はこの commit の Strata 所有ソースです。

## 役割

Terminal のアプリ更新経路が、ダウンロードした Desktop アプリのインストーラー署名を検証するときに使う minisign 公開鍵です。通常のフィード署名・engine component 署名用の鍵とは別です。変数は `strata update --app`（または `strata components update --app`）でアプリ更新処理が実行される場合にだけ参照されます。

## 値と判定

| 環境値 | `app_public_key()` の結果 |
|---|---|
| 未設定 | `strata_control/update_keys.json` の `app_minisign_public` を読む |
| 空文字 | Python の偽値判定により、未設定と同じく同梱キーへ fallback |
| 空でない文字列 | 内容の検証をせず、その文字列を同梱キーより優先して返す |

数値変換、大小文字判定、長さ制限、CLI による鍵指定はありません。空白だけの値も空文字ではないため優先され、後段の公開鍵 parser で失敗します。公開鍵 parser は外側の空白を除き、minisign 公開鍵ファイル形式またはその base64 形式を受け付けます。不正な形式、鍵 ID の不一致、署名不一致などは検証エラーになります（`strata_control/signing.py:277-291,294-324`）。

## 有効になる条件

- CLI の `--app` が指定され、更新処理の app step が有効である必要があります。`--no-engine` や `--no-control` は app step を止めません（`strata_cli/update_cmd.py:49-63,245`; `strata_control/updater.py:1466-1478`）。
- フィードにアプリがあり、この PC 向けの配布物があり、状態が `available` またはインストール済み app version が不明である場合に鍵を取得して検証へ進みます。インストール済み版が提示版以上なら app step は `current` となり、鍵は参照されません（`strata_control/updater.py:1402-1415,1422-1428`）。
- 通常の CLI では `Context.environ` は作成時点の `os.environ` のコピーです（`strata_control/updater.py:321-341`）。その環境辞書を `app_public_key` に渡します。値は app step の実行時に読み、関数内やプロセス共通の static cache はありません。
- `--app-version` / `STRATA_APP_VERSION` はアプリ更新の要否判定に影響し、更新対象になればこの鍵の読み取りに到達します（`strata_cli/update_cmd.py:53-54,204-206`; `strata_control/updater.py:1402-1415`）。公開鍵そのものの優先順位には関与しません。
- 直接参照検索では、この名前の実装読み取りは `strata_control/updater.py` の一箇所です。Desktop 側の Tauri updater 設定には別途コンパイル時の `pubkey` が記述されていますが、この環境変数を読む参照は見つかりません（`apps/desktop/src-tauri/tauri.conf.json:65-70`）。ここでは Terminal 側が行う処理のみを記載します。

## 実行時の詳細

`app_public_key(ctx.environ)` は同梱鍵を `utf-8-sig` で読み、JSON の `app_minisign_public` が空でない文字列なら fallback 値として返します。ファイル読み込みまたは JSON decode が `OSError` / `ValueError` で失敗した場合や、値が空・文字列でない場合は `None` です（`strata_control/updater.py:1389-1399`）。明示値は同梱鍵に対する追加鍵ではなく置き換えです。

更新対象なのに鍵が得られないと、ダウンロード前に exit code 5 の `UpdateError` となり、メッセージは `this build has no app update key (update_keys.json app_minisign_public); the app installer cannot be verified, so it was not downloaded` です。鍵が得られた場合、Terminal はフィードに記載された配布物を取得し、その署名を鍵で検証します。署名検証エラーなら一時アーカイブを削除し、`the app installer failed its signature check: ...; it was deleted` として app の結果を `failed`、終了コードを 5 にします。成功時はファイルを `.updates/app` に移し、`downloaded` と検証済みパスを返します。Terminal はインストーラーを起動せず、実行は利用者に委ねます（`strata_control/updater.py:1418-1449`）。

`run_update` は app step の `UpdateError` を結果に記録して処理を続け、失敗時は最終 `exit_code` に反映します（`strata_control/updater.py:1478-1489`）。通常表示では `NOT downloaded: ...`、JSON/JSONL では失敗結果と `ok: false` が観測できます（`strata_cli/update_cmd.py:145-149,247-256`）。不正な明示鍵は「鍵なし」fallback にはならず、minisign parser / verifier のエラー経路に入ります。

## 根拠

- 直接読み取り、空値判定、同梱 fallback: `strata_control/updater.py:1389-1399`
- CLI と app step の有効化: `strata_cli/update_cmd.py:49-63,183-206,229-256`; `strata_control/updater.py:1466-1489`
- app の更新判定、公開鍵利用、検証、失敗時削除、保存: `strata_control/updater.py:1402-1449`
- minisign 公開鍵の形式判定と署名検証: `strata_control/signing.py:277-291,294-330`
- 同梱 app 鍵: `strata_control/update_keys.json:10`
- Desktop の Tauri 設定鍵: `apps/desktop/src-tauri/tauri.conf.json:65-70`
- 概要資料も Terminal が `strata update --app` 時に同じ署名を確認すると説明しています: `docs/SAFETY.md:117-119`
