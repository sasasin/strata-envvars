# `STRATA_APP_UPDATE_PUBKEY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal のアプリ更新で、ダウンロードした Desktop アプリのインストーラー署名を検証する minisign 公開鍵を上書きする。変数を設定しただけでは更新は実行されず、通常の `strata update` は対象外である。`strata update --app` または `strata components update --app` がアプリ更新ステップを実行するときに使われる（`terminal/strata_cli/update_cmd.py:59-79, 367-368`、`terminal/strata_control/updater.py:1996-2007, 2087-2100`）。

## 値と判定

`app_public_key()` は `ctx.environ.get("STRATA_APP_UPDATE_PUBKEY")` の戻り値を文字列比較や数値変換なしで判定する。Python の truthiness により、未設定と空文字 `""` は同じく明示値なしとなり、同梱 `update_keys.json` の `app_minisign_public` に fallback する。空白だけの文字列を含む非空値は明示鍵としてそのまま返され、同梱鍵へ fallback しない（`terminal/strata_control/updater.py:1967-1977`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Terminal のアプリ更新 | 同梱 `update_keys.json` の `app_minisign_public` が非空文字列ならそれを使用。ファイル読み込み／JSON 構文解析に失敗、または JSON object 内の値が非文字列／空文字なら鍵なし | minisign の公開鍵テキスト（`.pub` の base64 表現またはファイルテキスト）が有効な形式。選択時点では形式検査しないため、`"true"`、`"0"` など任意の非空文字列も明示値として選ばれる | 空文字は明示値として採用されず unset と同じ fallback。空白だけを含む文字列は truthy なので明示値に採用されるが、署名検証時に公開鍵として拒否される |

アプリ更新の実処理では鍵が得られなければダウンロード前に `UpdateError`（終了コード 5）になる。非空だが不正な鍵は選択時には拒否されず、インストーラーをダウンロードした後に `minisign_verify()` で検査される。公開鍵の base64・鍵行・Ed25519 形式・署名との鍵 ID 照合・署名本体の検証に失敗すると `SignatureError` となり、ダウンロード済みファイルを削除して終了コード 5 の更新失敗として返す（`terminal/strata_control/updater.py:2004-2019`、`terminal/strata_control/signing.py:277-324`）。同梱ファイルが有効な JSON でも object ではない場合、この関数は `.get()` の例外を捕捉しないため、鍵なし扱いにはならず通常の `UpdateError` 経路も通らない（`terminal/strata_control/updater.py:1972-1977`）。

## 有効になる条件

- `--app` を指定してアプリ更新ステップを要求する必要がある。両 CLI 形式とも既定では `--app` は false（`terminal/strata_cli/update_cmd.py:59-79`、`terminal/strata_cli/update_cmd.py:367-368`）。
- フィードにアプリ項目があり、現在のプラットフォーム用のエントリーが必要。さらに `update_app()` は判定状態が `available` または `unknown-installed` のときだけ鍵を取得する。`--check` はフィード上の状態を表示するだけで、この変数を使ったインストーラー検証を行わない（`terminal/strata_control/updater.py:1980-1993, 1996-2007`、`terminal/strata_cli/update_cmd.py:357-368`）。
- インストーラー検証に必要な鍵はこの変数が優先される。空または未設定時は同梱鍵に fallback する。フィード／コンポーネント用の `STRATA_UPDATE_TRUSTED_KEYS` は別の鍵経路であり、このアプリ鍵を置き換えない（`terminal/strata_control/updater.py:1967-1977`、`terminal/strata_control/signing.py:8-15, 275-299`）。
- 既知のインストール済みアプリ版がフィード版以上なら状態は `current` となり、アプリ更新ステップは鍵を読まずに終了する。版が不明なら `unknown-installed` として鍵検証付きダウンロードの対象になり得る。比較に使う版は `--app-version` が truthy ならその値、そうでなければ `STRATA_APP_VERSION`（さらに無ければ不明）であり、この変数とは独立している（`terminal/strata_cli/update_cmd.py:63-64, 319-321`、`terminal/strata_control/updater.py:1989-2007`）。

## 実行時の詳細

CLI は `Context` を作る時点で `dict(os.environ)` を `environ` に保存する。アプリ更新時に `app_public_key(ctx.environ)` が呼ばれるため、値はその更新処理で読む環境スナップショットに基づく。プロセス起動後に OS 環境を変更しても、この `Context` の値は更新されない。関数内 static cache はなく、同一 `Context` 上で関数を再度呼べばその時点の `ctx.environ` を再参照する（`terminal/strata_control/updater.py:406-425, 1967-1977, 2004-2007`、`terminal/strata_cli/update_cmd.py:314-321`）。

鍵選択後、Terminal はフィードの該当プラットフォーム用 URL からインストーラーを取得し、SHA-256 はフィード値で確認したうえで、選択した minisign 公開鍵で署名を検証する。成功時はインストーラーを `<components>/.updates/app` に保存し、結果を `downloaded` として報告する。これは Terminal が検証済みインストーラーを取得する経路であり、Desktop アプリ自身の Tauri updater の実行設定をこの変数で変更する処理ではない（`terminal/strata_control/updater.py:1996-2027`、`terminal/strata_control/signing.py:294-329`）。

## ログと測定値

鍵が無い場合のエラー文は `this build has no app update key (update_keys.json app_minisign_public); the app installer cannot be verified, so it was not downloaded`。署名検証失敗時は `the app installer failed its signature check: ...; it was deleted` となる。これらは `run_update()` が app コンポーネントの結果 `status: failed`、エラー文、`exit_code: 5` として記録する。人間向け表示では `App     NOT downloaded: ...`、JSON/JSONL では失敗結果として出力される。測定値は該当しない（`terminal/strata_control/updater.py:2006-2019, 2087-2117`、`terminal/strata_cli/update_cmd.py:175-210, 369-373`）。

## 根拠

- `terminal/strata_control/updater.py:1967-1977` — 環境値と同梱鍵の選択、fallback。
- `terminal/strata_control/updater.py:1980-1993` — フィード項目、プラットフォーム、版による更新状態。
- `terminal/strata_control/updater.py:1996-2027` — 鍵の利用、ダウンロード、署名検証、保存。
- `terminal/strata_control/updater.py:2087-2117` — app ステップの opt-in と失敗結果。
- `terminal/strata_cli/update_cmd.py:59-79, 314-321, 357-373` — CLI オプション、環境スナップショット、app-version の優先、`--check` と更新処理。
- `terminal/strata_cli/update_cmd.py:175-210` — 人間向けのアプリ結果表示。
- `terminal/strata_control/signing.py:275-329` — minisign 公開鍵と署名の形式・検証。
