# `STRATA_PORT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有ソースを対象とし、Docker Compose や Node.js 自体の環境変数処理は Strata の挙動として扱わない。

## 役割

Strata App Host の HTTP サーバーが listen するポートを指定する。Host は指定ポートと `STRATA_BIND` のアドレスで `server.listen()` を呼び、起動ログにもその値を表示する。`STRATA_PORT` は `apps/host/server/index.mjs` のモジュール初期化時に一度読み取られ、その後の環境変更では再評価されない。

## 値と判定

値は `Number(process.env.STRATA_PORT ?? 8791)` で変換され、文字列の全体を JavaScript の `Number` に渡す。Strata 独自の書式検証、範囲制限、clamp はない。

| 環境値 | Strata が作る値 |
|---|---:|
| 未設定（`undefined`） | `8791` |
| 空文字、空白だけの文字列 | `0` |
| 数値として変換できる文字列（例: `8080`, `8.08e3`, `0x1f90`） | 変換された数値 |
| 数値に変換できない文字列 | `NaN` |
| 負数や `65535` より大きい数値 | その値のまま。Strata 側で補正しない |

値は `server.listen(PORT, HOST, ...)` にそのまま渡される。したがって、異常値を含む設定が実際に listen 可能かは Node.js の `listen` API に委ねられ、このソースでは事前検証や別ポートへの fallback をしない。空文字は未設定と同じではなく、数値 `0` に変換される。

## 有効になる条件

- Host を直接起動する場合、環境値が `server/index.mjs` の初期化時に参照される。
- `npm run dev` は親プロセスの `STRATA_PORT` を保持し、未設定なら文字列 `8791` を子 Host に明示して渡す。Vite の proxy 先にも同じ値を使う。
- デスクトップアプリは自身が選んだポートを子 Host に `STRATA_PORT` として設定するため、起動元の値を引き継がない。この起動経路では `STRATA_BIND=127.0.0.1` も明示する。
- Docker Compose ファイルにも `${STRATA_PORT:-8080}:8080` のポート割当てがある。これはコンテナ起動時のポート公開設定であり、App Host が読む既定値 `8791` とは別の設定箇所である。

## 実行時の詳細

Host は `PORT` を `serving.init()` に渡し、内部 agent 用 URL にも埋め込む。メイン HTTP サーバーの listen 成功時は起動通知に `PORT` を載せ、コンソールに `strata host  ·  http://${HOST}:${PORT}` を出す。bind に失敗した場合は stderr に `[strata] ` と `listenProblem()` の文を出して終了コード 1 で終了する。`EADDRINUSE` の場合は `Port ${port} is already in use. Strata may already be running; close it or the other program, or start Strata with another port (STRATA_PORT).`、`EACCES` の場合はポートを変えるよう案内する文が使われる。

この環境変数は共有・tunnel 用の listen ポートを直接指定しない。それらは別変数 `STRATA_SHARE_PORT` / `STRATA_TUNNEL_PORT`、または `PORT + 1` / `PORT + 2` を希望値として `findFreePort()` に渡される。メインポートはその探索で skip される。

## 根拠

- `apps/host/server/index.mjs:93-94` — `STRATA_PORT` の読み取りと数値変換、bind アドレスの既定値。
- `apps/host/server/index.mjs:211-216,253` — Host 初期化とポート表示。
- `apps/host/server/index.mjs:913-916` — 関連する共有・tunnel ポートの別設定。
- `apps/host/server/index.mjs:2179-2186` — listen、失敗時の出力と終了、成功通知。
- `apps/host/server/ports.mjs:5-10` — listen 失敗メッセージ。
- `apps/host/scripts/dev.mjs:16,24-28,61-66` — 開発起動スクリプトから子プロセスへの値の伝達。
- `apps/desktop/src-tauri/src/main.rs:430-465,1311-1333` — デスクトップ起動時に選んだポートを子 Host に設定する実装と対応するソース内テスト。
- `docker/compose/docker-compose.nvidia.yml:15` — Compose のホスト側ポート割当て。
