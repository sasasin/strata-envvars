# `STRATA_BIND`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

`apps/host` の Node.js ホストサーバーが HTTP 待受けに渡すホスト文字列を指定します。単独でサーバーを起動する場合、未設定時は `127.0.0.1` です。デスクトップアプリは子ホストに `STRATA_BIND=127.0.0.1` を明示するため、呼び出し元の値では待受け範囲を広げられません。Docker Compose ファイルでは別に、ホストマシン側で公開ポートを bind する IP の補間値として使われます。

## 値と判定

| 実行経路 | 未設定 | 設定時 | 判定・変換 |
|---|---|---|---|
| `apps/host/server/index.mjs` を直接起動 | `127.0.0.1` | 指定文字列 | `process.env.STRATA_BIND ?? '127.0.0.1'`。nullish coalescing のみで、数値変換、書式検証、空白除去、空文字 fallback はしない。空文字も設定値として `HOST` に残る。 |
| デスクトップアプリから起動 | 親環境の有無・値に関係なく `127.0.0.1` | 同左 | Rust の子プロセス command に `.env("STRATA_BIND", "127.0.0.1")` を設定して上書きする。 |
| NVIDIA / AMD / Intel Docker Compose | Compose の `${STRATA_BIND:-127.0.0.1}` 補間 | 補間された値 | Compose のポート公開設定のホスト側 IP 欄に使う。アプリサーバーの `HOST` を直接読む処理とは別経路。 |

直接起動経路では値の許容範囲を Strata が事前に制限していません。文字列は `server.listen(PORT, HOST, ...)` にそのまま渡されるため、受理可否は listen の結果になります。数値 IP 以外の名前や空文字を含め、Strata 独自の parse / fallback はありません。無効または利用不能な値で listen が失敗した場合、エラーイベントで `[strata] ${listenProblem(error, PORT, HOST)}` を stderr に出し、初期 listen 失敗として終了コード 1 で終了します。`EADDRNOTAVAIL` なら文言は `<HOST> is not an address of this computer, so Strata cannot listen on it. Check STRATA_BIND.` です。他の bind エラーは `listenProblem` の一般文言または該当コード別文言になります。

## 有効になる条件

- Node.js ホストサーバーを直接起動する場合に、環境値が待受け先として使われます。GPU backend やモデル状態による条件分岐はありません。起動処理中の hardware 検出後、サーバー初期化と listen に使われます。
- Electron / デスクトップの `host_command` 経路では loopback 固定です。子プロセス環境を組み立てる時点で値を上書きするので、親環境に `0.0.0.0` 等があっても引き継ぎません。
- Docker Compose の NVIDIA / AMD / Intel 構成では、値は compose の `ports` のホスト側 bind address に補間されます。各ファイルの fallback は `127.0.0.1` です。`apps/host` の `HOST` と同一の設定経路ではありません。
- ホストサーバーの CLI 引数による bind address 上書きは確認できません。`index.mjs` は `process.argv` から `--dist` を処理しますが、待受け `HOST` は環境値または既定値から作られます。

## 実行時の詳細

`HOST` は `apps/host/server/index.mjs` のトップレベル定数としてモジュール評価時に一度設定されます。以降の環境変更を読み直す処理やキャッシュ更新はありません。`serving.init` に host と port を渡し、起動ログに `strata host  ·  http://${HOST}:${PORT}` を出してから `server.listen(PORT, HOST, ...)` を呼びます。listen 前にエラーが起きると `server.on('error')` が `listenProblem` の内容を stderr に出して `process.exit(1)` します。

デスクトップの子プロセス起動では `STRATA_PORT` も選定済みポート値に設定しますが、bind address は常に `127.0.0.1` です。ソース内テストも、親側に `STRATA_BIND=0.0.0.0` を設定していても生成された command の環境値が `127.0.0.1` であることを検査する構成です（テストは挙動の追加根拠ではなく、実装箇所の確認に用いました）。

## 根拠

- `apps/host/server/index.mjs:100-101` — `PORT` と `HOST` の既定値・環境値の採用。
- `apps/host/server/index.mjs:237-243` — hardware 検出後の起動初期化で `HOST` を serving に渡す。
- `apps/host/server/index.mjs:2256-2266` — listen エラー処理と `server.listen(PORT, HOST, ...)`。待受け成功 callback。
- `apps/host/server/index.mjs:280-281` — 待受け先を含む起動ログ。
- `apps/host/server/ports.mjs:4-10` — `EADDRNOTAVAIL` 等の Strata 側エラー文言。
- `apps/desktop/src-tauri/src/main.rs:463-478` — デスクトップ子ホストの環境設定と `STRATA_BIND` の loopback 上書き。
- `apps/desktop/src-tauri/src/main.rs:1341-1363` — 親環境の値を子 command で上書きすることを確認するテスト。
- `docker/compose/docker-compose.nvidia.yml:15`, `docker/compose/docker-compose.amd.yml:14`, `docker/compose/docker-compose.intel.yml:14` — Compose のポート公開 IP 補間と既定値。
- `docs/DOCKER.md:103-106` — Compose のホスト側公開先を `STRATA_BIND=0.0.0.0` にする説明。
