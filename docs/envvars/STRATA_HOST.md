# `STRATA_HOST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

開発用 Vite サーバーが `/api` と WebSocket のリクエストを転送する proxy target を指定します。Strata 本体の推論エンジンや、`apps/host/server/index.mjs` で起動する engine host の設定を変更する変数ではありません。候補名の直接参照は `apps/host/vite.config.ts` の一箇所です。

## 値と判定

| 状態 | proxy target に設定される値 |
|---|---|
| `STRATA_HOST` が未設定 | `http://127.0.0.1:8791` |
| 設定あり（空文字を含む） | 環境変数の文字列をそのまま使用 |

判定は JavaScript の nullish coalescing (`??`) です。未設定 (`undefined`) の場合だけ既定値にします。空文字、空白、URL 形式でない文字列も Strata 側では検査・trim・変換されず、そのまま設定値になります。Strata のコードには無効値向けの fallback、警告、エラー処理がありません。設定値の妥当性検査や、設定を受け取った後の Vite の反応はこの Strata 側の読み取りからは判断しません。

## 有効になる条件

- `npm run dev:web` は `vite` を直接起動するため、起動プロセスの `STRATA_HOST` が設定されていればその文字列が使われ、未設定なら上記の既定値になります。
- 通常の `npm run dev` は `scripts/dev.mjs` が Vite を子プロセスとして起動し、`STRATA_HOST` を `http://127.0.0.1:${HOST_PORT}` に設定します。`HOST_PORT` は同スクリプトが `STRATA_PORT` から取得し、未設定なら `8791` です。子プロセス環境の組み立てではこの指定値を親環境より後に展開するため、親から渡された `STRATA_HOST` はこの開発起動経路では上書きされます。
- 設定は Vite の `server.proxy['/api']` にあります。`npm run build` や `npm run serve` の Strata engine host がこの `/api` 開発 proxy を使うとは、該当する Strata コードからは確認できません。

## 実行時の詳細

Vite が `vite.config.ts` を読み込む際に `process.env.STRATA_HOST` を一度評価し、その設定値を `/api` proxy の `target` に置きます。`changeOrigin` と `ws` も有効に設定されています。設定後にプロセス環境を書き換えて再評価する Strata コードや、CLI 引数との優先順位はありません。

通常の統合開発起動では `scripts/dev.mjs` が host と web の出力を stdout/stderr に接頭辞付きで転送します。また、いずれかの子プロセスが終了すると `exited (...)` を出して両方を終了します。`STRATA_HOST` 自体について専用のログ・警告・終了経路はありません。

## 根拠

- `apps/host/vite.config.ts:25-34` — `/api` と WebSocket の proxy 設定、`STRATA_HOST ??` による既定値と文字列の設定。
- `apps/host/package.json:7-13` — `dev:web`、`dev`、`build`、`serve` の起動コマンド。
- `apps/host/scripts/dev.mjs:15-16,24-28,42-45,61-65` — `STRATA_PORT` による host port、子プロセス環境の上書き順、終了ログ、Vite 子プロセスへの `STRATA_HOST` 設定。
