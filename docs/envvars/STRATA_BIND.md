# `STRATA_BIND`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Node.js の App Host が HTTP サーバーを listen する host 文字列を選ぶ。未設定なら `127.0.0.1`、設定されていれば値をそのまま `server.listen(PORT, HOST, ...)` に渡す。Strata 側でアドレスの解決、値の正規化、公開範囲の判定はしない。ポートは別の `STRATA_PORT` が決める。`app/host/server/index.mjs` は通常の `dev:host` / `serve` 起動のほか、デスクトップアプリからも起動される（`app/host/package.json:7-13`）。

デスクトップシェルの `host_command` は子プロセスに `STRATA_BIND=127.0.0.1` を明示設定するため、その起動では呼び出し元の同名環境変数が上書きされる（`app/desktop/src-tauri/src/main.rs:503-540`）。一方、Docker Compose 3 flavor の同名はコンテナのポート公開先アドレスを表す補間変数であり、Compose の `environment` 欄からコンテナへ渡してはいない。ホスト側公開先の既定は `127.0.0.1`（`tools/docker/compose/docker-compose.nvidia.yml:14-24`、`docker-compose.intel.yml:13-23`、`docker-compose.amd.yml:13-23`）。

## 値と判定

ホスト起動モジュールのトップレベルで `process.env.STRATA_BIND ?? '127.0.0.1'` として一度読み、結果を `HOST` 定数に保持する。文字列全体の比較、数値・真偽値変換、空白除去、形式検証はない。`??` なので未設定（`undefined`）だけが既定値になり、空文字は既定値に置き換わらない。`HOST` はそのまま listen 呼び出しへ渡される（`app/host/server/index.mjs:95-110, 2563-2564`）。

| 起動経路・条件 | unset | 設定された値の扱い | 例 |
|---|---|---|---|
| Node App Host を直接起動 | `127.0.0.1` | 値を加工せず host 引数へ渡す | `127.0.0.1`、`0.0.0.0` は文字列のまま渡る。`''`、`0`、`1`、`true`、`false`、空白を含む文字列も Strata は判定・変換せず、そのまま渡す |
| Tauri デスクトップの `host_command` 経由 | 子プロセスには unset でなく `127.0.0.1` を設定 | 親の値を常に `127.0.0.1` で上書き | 親側が `0.0.0.0` でも子には `127.0.0.1` |
| Docker Compose の公開ポート指定 | Compose 式の既定 `127.0.0.1` | Compose のポート公開先アドレス欄へ展開 | `0.0.0.0` は公開先として展開される。これは App Host の `HOST` 値判定ではない |

Strata は設定値を「有効 / 無効」と分類しないため、`0` / `1` / `true` / `false` をフラグとして扱う規則や、無効値時の fallback はない。直接起動時にアドレスとして受理されるかは listen の結果に委ねられ、Strata 自身による値域・境界チェックはない。

## 有効になる条件

- `STRATA_BIND` の読み取りと listen は `app/host/server/index.mjs` の App Host 起動経路で行われる。OS、GPU backend、モデル状態による分岐はない（`app/host/server/index.mjs:95-110, 2555-2564`）。
- Tauri デスクトップアプリ経由では、Rust 側が子プロセス環境へ `127.0.0.1` を設定するので、親プロセスの値では listen アドレスを変更できない（`app/desktop/src-tauri/src/main.rs:522-540`）。
- Docker Compose の NVIDIA / Intel / AMD 定義では、値はホスト上の公開ポートのアドレス欄にだけ補間され、コンテナの `environment` には含まれない。コンテナ内 App Host が別途この変数を受け取る動作はこれらの定義にはない（各 compose ファイルの `ports` と `environment`、例: `tools/docker/compose/docker-compose.nvidia.yml:14-24`）。
- `--dist` は配信 UI の場所を選ぶ CLI オプションであり、bind host を変更する CLI オプションはこの起動コードにない（`app/host/server/index.mjs:97-110`）。

## 実行時の詳細

モジュール評価時に `HOST` を定数へ保存し、起動処理末尾で `server.listen(PORT, HOST, ...)` に渡す。起動後の環境変数変更を再読込する経路や cache 更新処理はないため、実行中の変更は反映されず、変更にはホストプロセスの再起動が必要（`app/host/server/index.mjs:95-110, 2555-2564`）。CLI bind 引数、設定ファイル、別環境変数による上書きもない。

起動時には選択された host と port を `strata host  ·  http://${HOST}:${PORT}` として標準出力へ出した後に listen を試みる（`app/host/server/index.mjs:306-311, 2563-2564`）。listen が失敗して起動前の `error` イベントを受けると、`listenProblem` の文面を `[strata] ` 付きで標準エラーへ出し、終了コード `1` で終了する。`EADDRNOTAVAIL` の場合は `{host} is not an address of this computer, so Strata cannot listen on it. Check STRATA_BIND.`。`EADDRINUSE`、`EACCES` には個別の説明があり、それ以外は `Strata cannot listen on {host}:{port} ({message-or-code}).` となる。listen 成功時は `process.send` がある子プロセスなら `{ type: 'strata-ready', port: PORT }` を送る（`app/host/server/index.mjs:2557-2564`、`app/host/server/ports.mjs:7-15`）。

## ログと測定値

性能測定値は該当しない。起動時の URL 出力と listen 失敗時の標準エラー文言は「実行時の詳細」に記載した。デスクトップ側の loopback 固定は、本番コードの `.env(...)` 設定による（`app/desktop/src-tauri/src/main.rs:535-536`）。

## 根拠

- `app/host/server/index.mjs:95-110` — CLI 引数の確認と `HOST` の既定値・読み取り。
- `app/host/server/index.mjs:306-311, 2555-2564` — 起動ログ、listen 呼び出し、ready 通知、エラー時の終了。
- `app/host/server/ports.mjs:7-15` — listen 失敗コードごとのログ文言。
- `app/desktop/src-tauri/src/main.rs:503-540` — デスクトップシェルが子プロセス環境へ loopback を設定。
- `tools/docker/compose/docker-compose.nvidia.yml:14-24`、`docker-compose.intel.yml:13-23`、`docker-compose.amd.yml:13-23` — Compose のホスト側公開アドレスとコンテナ環境欄。
