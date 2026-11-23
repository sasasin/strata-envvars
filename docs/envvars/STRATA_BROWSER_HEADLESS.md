# `STRATA_BROWSER_HEADLESS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

agent の browser MCP サーバーを設定するとき、起動引数に `--headless` を含めるかを選びます。Strata が値を読み、ブラウザーのツールサーバー設定を組み立てます。`--headless` は環境変数が文字列 `'1'` のときだけ追加されます。それ以外の値では追加されません（`app/host/server/agent/profile.mjs:435-437`）。

## 値と判定

Node.js の `process.env.STRATA_BROWSER_HEADLESS === '1'` という文字列の厳密比較です。設定値を数値・真偽値に変換せず、空白除去や大文字小文字変換もしません。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| browser MCP の設定を生成するとき | `undefined`。`--headless` なし | 文字列 `'1'` のみ | 空文字、`'0'`、`'true'`、`'TRUE'`、`' 1'`、`'1 '`、`'01'`、`'1anything'`。いずれも `--headless` なし |

`--headless` の有無に関して、CLI 引数や他の環境変数による優先順位・上書きはありません。browser サーバーの他の引数は固定値と検出された実行ファイルのパスです（`app/host/server/agent/profile.mjs:436-437`）。

## 有効になる条件

- Settings の browser が有効であること。設定の正規化では `browser.enabled === true` の場合だけ有効です（`app/host/server/agent/tools-settings.mjs:30-37`）。
- browser 実行ファイルのパスと Playwright MCP CLI のパスが利用可能であること。プロファイル側では `tools.browserEnabled && tools.browserPath && tools.browserCli` が成立した場合に限り browser 行を作ります（`app/host/server/agent/profile.mjs:435-437`）。`profileView()` は browser が見つかり、CLI もある場合に `browserEnabled` を true にします（`app/host/server/agent/tools-settings.mjs:145-169`）。
- これらの条件を満たさない場合、browser 行自体が作られず、この変数も効果を持ちません。ソース上、OS・backend・build macro・モデル状態による追加条件はありません。

## 実行時の詳細

値は `buildProfile()` が browser 行を組み立てる時点で直接読み取られます。関数内 static cache や別のキャッシュはありません（`app/host/server/agent/profile.mjs:314`, `435-437`）。agent bridge は `buildProfileNow()` からプロファイルを生成し、各 `ensureRuntime()` で再評価します。生成した設定は patch に含まれて Harness 起動時に使われます（`app/host/server/agent/agent-bridge.mjs:250-263`, `339-360`; `app/host/server/agent/profile.mjs:480-486`）。

既に起動中の Harness の引数がその場で変わるわけではありません。次の profile 評価で値が変わり browser 設定も変化した場合、tools signature が変わるため、bridge は処理中の chat が idle になるのを待って Harness を再起動します（`app/host/server/agent/agent-bridge.mjs:339-355`; `app/host/server/agent/profile.mjs:487-493`）。再起動後の browser MCP 行には、評価時点の値に応じて `--headless` が追加または省略されます（`app/host/server/agent/profile.mjs:436-437`）。環境変数自体を browser プロセスへ転送する処理はこの箇所にはなく、Strata が設定するのは CLI 引数です。

## ログと測定値

この変数の値や `--headless` の付与に関する Strata 固有のログ、警告、測定値は該当コードにありません。条件不成立時も browser 行が作られないだけで、この変数を理由とするエラー処理はありません（`app/host/server/agent/profile.mjs:435-437`）。

## 根拠

- `app/host/server/agent/profile.mjs:435-437` — browser 行の条件、環境変数の厳密比較、CLI 引数への `--headless` 追加。
- `app/host/server/agent/tools-settings.mjs:30-37`, `145-169` — browser 設定の既定状態と browser/CLI の利用可能性。
- `app/host/server/agent/agent-bridge.mjs:250-263`, `339-360` — profile の生成時期、実行時の再評価と再起動。
- `app/host/server/agent/profile.mjs:480-493` — patch と tools signature の生成。
