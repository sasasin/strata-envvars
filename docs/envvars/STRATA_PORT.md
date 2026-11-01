# `STRATA_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの動作は対象外。

## 役割

`apps/host` の HTTP ホストが listen に渡すポート番号を決めます。ホストはこの値を起動時に `Number(...)` で数値化し、`server.listen(PORT, HOST, ...)` に渡します。ホストの既定値は `8791`、bind address の既定値は別変数 `STRATA_BIND` の `127.0.0.1` です（`apps/host/server/index.mjs:100-101,2256-2263`）。

同じ名前は Docker Compose 定義でも使われますが、そこでは Compose がホスト側の公開ポートを置換します。コンテナ内のポートは固定で `8080` です（`docker/compose/docker-compose.nvidia.yml:14-15`, `docker/compose/docker-compose.amd.yml:13-14`, `docker/compose/docker-compose.intel.yml:14`）。これはホストプロセスが読む `STRATA_PORT` とは別の適用箇所です。

## 値と判定

App Host は `Number(process.env.STRATA_PORT ?? 8791)` を使います。文字列全体を `Number` で数値化し、個別の書式検証、整数化、範囲制限、fallback 処理はしていません（`apps/host/server/index.mjs:100`）。

| 環境値 | Strata 側の処理 |
|---|---|
| 未設定 | `8791` を使う。 |
| 空文字 | nullish 判定には該当せず、`Number("")` の結果 `0` を使う。 |
| 数値として読める文字列 | `Number` の結果を使う。10進数以外の Number 形式もここで拒否されない。 |
| 数字でない文字列 | `Number` の結果 `NaN` をそのまま listen に渡す。 |
| 負数、小数、範囲外の数値 | Strata 側では検証・clamp せず、その数値を listen に渡す。 |

最後の3種類が実際に bind できるかどうかは `server.listen` 側の処理によります。Strata の起動コードには事前検査や別ポートへの自動 fallback はありません。listen 前に `error` イベントが起きた場合は、後述のメッセージを出して終了コード `1` で終了します（`apps/host/server/index.mjs:2256-2262`, `apps/host/server/ports.mjs:5-10`）。

## 有効になる条件

- `apps/host/server/index.mjs` を実行する経路で有効です。トップレベルで値を読み取るため、プロセスのモジュール起動時に一度だけ評価されます。起動後に環境を変更しても `PORT` は再評価されません（`apps/host/server/index.mjs:88-100`）。
- `npm run dev` 相当の開発ランチャーも、親の `STRATA_PORT` を読み、未設定なら `8791` としてホスト子プロセスに渡します。ランチャーの表示ポートと Vite の `STRATA_HOST` も同じ値から作ります（`apps/host/scripts/dev.mjs:15-16,61-66`）。
- Windows/macOS のデスクトップアプリは、設定ファイル `shell-prefs.json` のポート（未指定時は通常 `47831`）を選んで子ホストへ `STRATA_PORT` を渡します。設定値は `1024..65535` に制限され、指定ポートが使用中なら空きポートに切り替えます。この経路ではデスクトップシェルが親環境の同名変数を上書きします（`apps/desktop/src-tauri/src/shell.rs:37-58`, `apps/desktop/src-tauri/src/main.rs:250-274,442-477,495-501`）。切替時は `STRATA_PORT_NOTICE` も渡され、ホスト状態に notice として含まれます（`apps/desktop/src-tauri/src/main.rs:256-258,269-272,484-485`; `apps/host/server/index.mjs:133-143`）。
- デスクトップの packaged self-test は空きポートを選択し、その値でホストを起動します（`apps/desktop/src-tauri/src/main.rs:729-744`）。
- CLI 引数で `PORT` を上書きする処理はホストの起動コードにありません。ここで解析する引数は `--dist` です（`apps/host/server/index.mjs:88-100`）。別途 `STRATA_SHARE_PORT` / `STRATA_TUNNEL_PORT` が設定されなければ、共有用・トンネル用 listener の希望ポートはそれぞれ `PORT + 1`, `PORT + 2` から計算され、空きポートを探します（`apps/host/server/index.mjs:944-948`; 探索処理は `apps/host/server/ports.mjs:13-30`）。
- Docker Compose の NVIDIA/AMD/Intel 定義では `${STRATA_PORT:-8080}` がホスト側ポート欄です。Compose の `:-` 置換では未設定または空値が `8080` になります。コンテナ内の公開先は `8080` 固定で、compose 定義はこの値をコンテナの `STRATA_PORT` 環境変数として渡していません（上記 Compose ファイル各行）。

## 実行時の詳細

ホストは `PORT` を server の listen に使うほか、デスクトップ向けの shell state に `port` として返し、サーバー内で生成する自ホスト URL にも使います（`apps/host/server/index.mjs:133-143,944-950,1164,1325-1326`）。`process.send` がある起動では ready メッセージにも同じ `PORT` を載せます（`apps/host/server/index.mjs:2262-2263`）。Strata コードは listen 後に実際の bind port を読み直していません。

listen 前のエラーでは、`EADDRINUSE` に対し「Port {port} is already in use...」、`EACCES` に対し Windows/firewall の拒否と別ポート利用を案内し、それ以外は `Strata cannot listen on {host}:{port} ({error})` の形式で出します。ログは `[strata] ` を付けた stderr への `console.error` で、プロセスは終了コード `1` になります（`apps/host/server/ports.mjs:5-10`; 呼び出しは `apps/host/server/index.mjs:2256-2261`）。エラー発生後すでに listen 中なら、一般のエラーメッセージをログに出すだけで終了しません（同 `index.mjs:2256-2257`）。

デスクトップでは busy-port fallback の通知をホストが `shellState()` に含め、ページ側へ見せます。ホストの起動失敗はデスクトップ側の `start_host` から startup error として扱われます（`apps/host/server/index.mjs:133-143`; `apps/desktop/src-tauri/src/main.rs:507-537,903-915`）。

## 根拠

- Host の読み取り、既定値、listen、および起動エラー処理: `apps/host/server/index.mjs:88-101,2256-2266`。
- listen 失敗時のメッセージ: `apps/host/server/ports.mjs:4-10`。
- 開発ランチャーからホストと Vite への転送: `apps/host/scripts/dev.mjs:15-16,61-66`。
- デスクトップのポート設定値チェック、busy fallback、子プロセスへの環境設定: `apps/desktop/src-tauri/src/shell.rs:37-58`, `apps/desktop/src-tauri/src/main.rs:250-274,442-492,495-501`。
- Compose 側の公開ポート置換: `docker/compose/docker-compose.nvidia.yml:14-15`, `docker/compose/docker-compose.amd.yml:13-14`, `docker/compose/docker-compose.intel.yml:14`。

調査はコード読解のみです。build、GPU 実行、性能測定、テストは実施していません。
