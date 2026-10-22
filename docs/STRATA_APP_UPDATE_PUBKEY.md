# `STRATA_APP_UPDATE_PUBKEY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Terminal の `strata update --app` がダウンロードする Desktop アプリのインストーラーを検証する minisign 公開鍵を上書きします。アプリの更新処理でのみ使われ、エンジンや Control の署名検証鍵には使われません。`strata update --check` は更新候補を報告するだけで、インストーラーの署名検証鍵を読みません。

## 値と判定

| 環境変数の状態 | `app_public_key()` の結果 |
|---|---|
| 未設定または空文字 | 同梱 `strata_control/update_keys.json` の `app_minisign_public` にフォールバック |
| 空でない文字列 | その文字列をそのまま同梱鍵より優先 |
| 同梱 JSON を読めない、JSON の構文解析に失敗する、または鍵が空/文字列でない | `None`。対象アプリ更新を拒否 |

`1` や `0` を真偽値として解釈する規則はありません。たとえば `STRATA_APP_UPDATE_PUBKEY=0` も鍵文字列として優先され、署名検証時に不正な公開鍵として扱われます。空白だけの値も優先値になりますが、minisign parser は前後空白を除いた後に形式を検証します。公開鍵として有効かどうかは `app_public_key()` では検査せず、インストーラーを取得した後の署名検証で検査します。同梱 JSON が構文上は有効でもトップレベルが辞書以外の場合、`data.get(...)` が `AttributeError` となり、ここで捕捉されない点は通常の `update_keys.json` 構造外の経路です。

## 有効になる条件

- `strata update --app` を指定し、更新 feed にこの PC 向けアプリがあり、インストール済みバージョンが不明または feed のバージョンより古い場合に鍵が参照されます。
- feed にアプリがない、PC 向け配布がない、または既に最新の場合は、アプリ更新が早期終了し、この変数も同梱鍵も読みません。
- Terminal の `strata update` では `--app` がない限り `run_update()` にアプリ更新を依頼しません。Desktop アプリ自身の Tauri updater が読む環境変数ではありません。コード全体でこの変数を読む箇所は Terminal の updater 一か所です。

## 実行時の詳細

CLI は `Context` の生成時に `dict(os.environ)` を保存します。したがって通常の CLI 実行では、この変数は更新コマンド開始時の環境から取得されます。アプリ更新対象と判定された後、`app_public_key(ctx.environ)` が空でない override を採用し、なければ同梱 JSON を UTF-8 BOM 許容で読みます。JSON 読み込み時の `OSError` / `ValueError` は `None` にし、鍵がない場合は exit code 5 の `UpdateError` で停止します（インストーラーはダウンロードしません）。

鍵が得られると、Terminal は feed 記載のサイズ・SHA-256 を使ってインストーラーをダウンロードし、その後 `signing.minisign_verify()` でアプリ署名を検証します。公開鍵は minisign のテキスト形式（またはその Base64 表現）として解釈され、Ed25519 鍵であること、署名の key ID が鍵と一致すること、署名がインストーラー内容に一致することを確認します。Tauri 形式の `ED`（BLAKE2b-512 digest）と旧形式の `Ed`（データ本体）の両方を受け付けます。署名不一致や鍵形式エラーでは、ダウンロードした archive を削除し、エラー code 5 で失敗します。検証に成功した場合は `.updates/app` に保存し、「インストーラーを実行して完了する」扱いで、Terminal 自身はインストールしません。

## 根拠

- `strata_control/updater.py:277-296` — `Context.environ` はデフォルトでプロセス環境のコピー。
- `strata_cli/update_cmd.py:174-176,205` — CLI が `Context` を作り、`--app` の指定を `run_update()` に渡す。
- `strata_control/updater.py:1046-1056` — override の優先、空値の扱い、同梱鍵へのフォールバック。
- `strata_control/updater.py:1059-1072,1075-1105,1123-1134` — 鍵を読む条件、署名検証、失敗時の削除、検証済み installer の保存。
- `strata_control/signing.py:277-330` — 公開鍵と署名の形式、および検証内容。
- `strata_control/update_keys.json:1-11` — 同梱の `app_minisign_public`。
- `docs/SAFETY.md:111-113`, `docs/INSTALL.md:263-270` — アプリ更新鍵の分離と `strata update --app` の利用説明。ソースでは Terminal が署名を検証した後に installer を保存することを確認。
