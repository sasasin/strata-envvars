# `STRATA_BIND`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

App Host のメイン HTTP サーバーが listen するアドレスを指定します。通常の直接起動では未設定時に `127.0.0.1`（loopback）を使います。デスクトップアプリから起動する App Host は、親の環境値にかかわらず `127.0.0.1` に固定されます。

Docker Compose の設定ファイルにも同じ名前がありますが、そこでの用途はコンテナのポートをホスト側のどのアドレスに公開するかの指定です。これは Compose による設定で、Compose ファイルはこの値をコンテナの `environment` に渡していません。

## 値と判定

| 状況 | 実装上の扱い |
|---|---|
| 未設定 | `127.0.0.1` を使用 |
| 設定あり（空文字を含む） | 値を変換・検証せず、そのまま Node.js の `server.listen(PORT, HOST)` に渡す |
| 有効なローカルアドレスでない値 | listen が `EADDRNOTAVAIL` で失敗した場合、`STRATA_BIND` を確認するよう stderr に出し、プロセスを終了コード 1 で終了 |

文字列の trim、大小文字変換、数値 parse、範囲制限、空文字時の fallback はありません。ホスト名や wildcard などの受理範囲は Strata 側で検証しておらず、Node.js に渡した後の listen の成否に従います。

## 有効になる条件

- `apps/host/server/index.mjs` を直接起動する場合は、起動時の `process.env.STRATA_BIND` が使われます。プロセス環境が未設定なら loopback です。
- Windows/macOS のデスクトップアプリは App Host の子プロセスを作る際、`.env("STRATA_BIND", "127.0.0.1")` を設定します。継承された値があっても子プロセスでは上書きされます。
- Docker Compose の NVIDIA、AMD、Intel 各設定では `${STRATA_BIND:-127.0.0.1}` をホスト側ポート公開アドレスに使います。Compose の `:-` 展開では未設定または空文字のとき `127.0.0.1` に fallback します。この Compose 側の規則は App Host の JavaScript にある nullish 判定とは異なります。

## 実行時の詳細

App Host はモジュール初期化時に `HOST` 定数へ値を読み込みます。その値を serving 状態の初期化に渡し、起動時の案内 URL に表示し、最後にメインサーバーの `server.listen(PORT, HOST, ...)` に渡します。起動後に環境値を書き換えても、すでに保持された `HOST` や listener は変わりません。listen エラー時は `listenProblem(error, PORT, HOST)` の結果を stderr に `[strata]` 付きで出して終了します。`EADDRNOTAVAIL` 以外のエラーでは、`Strata cannot listen on host:port (...)` 形式のメッセージになります。

この値は `STRATA_PORT` やサーバーの補助 listener の bind address を変更しません。補助 listener の空きポート探索は `findFreePort()` に個別の host（`0.0.0.0` または `127.0.0.1`）を渡しています。

## 根拠

- `apps/host/server/index.mjs:93-94` — `STRATA_PORT` と `STRATA_BIND` の起動時読み取り、既定値。
- `apps/host/server/index.mjs:211-216,253` — `HOST` を serving 初期化へ渡し、起動 URL に表示。
- `apps/host/server/index.mjs:914-916` — 補助 listener のポート探索は固定アドレスを指定。
- `apps/host/server/index.mjs:2177-2188` — メイン listener、エラー表示、終了コード、ready 通知。
- `apps/host/server/ports.mjs:4-10` — `EADDRNOTAVAIL` とその他の listen エラー文言。
- `apps/desktop/src-tauri/src/main.rs:451-466` — デスクトップが起動する子プロセスに `127.0.0.1` を明示設定。
- `docker/compose/docker-compose.nvidia.yml:14-16`, `docker/compose/docker-compose.amd.yml:14`, `docker/compose/docker-compose.intel.yml:14` — Compose のホスト側ポート公開アドレス。
- `docs/DOCKER.md:104-107`, `docs/SAFETY.md:82-88` — Docker 利用時のネットワーク公開とデスクトップ側の loopback 固定に関する説明。上記の実装と一致します。
