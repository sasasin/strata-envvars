# `E2E_BASE_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main` で `## main...origin/main` と表示され、未コミット変更はありません。

## 役割

`apps/host/scripts/context-e2e.mjs` 専用の設定です。値を空でない文字列にすると、スクリプトはその URL を既に稼働しているモデルサーバーの base URL として使います。この場合、スクリプトは `serve/server.py` を起動せず、既存サーバーを停止しません。未設定または空文字なら、スクリプトが自分の子プロセスとしてサーバーを起動し、`http://127.0.0.1:${E2E_PORT}`（`E2E_PORT` の既定値は `18590`）を使います。

これは Strata engine 本体や通常の host アプリの設定ではなく、実 engine / Harness を使った context E2E スクリプトの接続先切り替えです。スクリプトのヘッダーは scripted worker を使った GPU 不要の試行にも言及していますが、この変数自体は接続先の切り替えだけを行います。

## 値と判定

| 環境変数の状態 | 判定と動作 |
|---|---|
| 未設定 | `process.env.E2E_BASE_URL ?? ''` が `''` になる。スクリプトがローカルサーバーを起動する。 |
| 空文字 | `''` のまま。未設定と同じくローカルサーバーを起動する。 |
| 空でない文字列 | 文字列をそのまま `EXISTING` として保持し、既存サーバーモードにする。数値化、trim、URL 検証、末尾 `/` の正規化はしない。 |

判定は JavaScript の truthiness によります。したがって空白だけの値も既存サーバーモードになります。値はスクリプトのモジュール評価時に一度読み取られて `const EXISTING` に保持されるため、実行中に環境を変更しても判定は更新されません。

## 有効になる条件

この名前の読み取りは `apps/host/scripts/context-e2e.mjs` に一箇所だけあります。`node scripts/context-e2e.mjs` でこのスクリプトを実行した場合にだけ使われ、Strata の通常起動、CLI オプション、engine の backend や build macro からは参照されません。

`STRATA_HARNESS_DIR` は引き続き必須で、未設定なら `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード `2` で終了します。`E2E_BASE_URL` が空なら engine 実行ファイルとモデルファイルの存在確認、および起動前の空き RAM 20 GB 確認を行います。値が空でない場合はこの二つの事前確認を飛ばします。`E2E_PORT` は既定ポートでの自前起動に使われますが、`E2E_BASE_URL` が空でないときに接続 URL を上書きしません。

## 実行時の詳細

既存サーバーモードでは、`base` に `E2E_BASE_URL` の文字列を設定し、`${base}/health` を最大 120 回確認します。各 fetch の timeout は 2 秒で、未準備時には 2 秒待って再試行します。準備完了後は `${base}/v1/models` からモデル ID を取得し、token count 用 URL と agent bridge の `baseUrl` をそれぞれ `${base}/v1` に設定します。入力 URL に末尾 `/` があっても除去されないため、連結されるパスには `/` が重なる場合があります。

既存サーバーモードではスクリプト自身の `server` は `null` のままで、子サーバー起動、起動ログ収集、空き RAM 監視アラームは設定されません。E2E 終了時の `stopServer()` は子プロセスの PID がある場合だけ `taskkill` するため、既存サーバーは停止しません。未設定・空文字のときはこれらの逆で、自前の `serve/server.py` を起動し、ローカル base URL を使い、RAM 監視を行い、終了時に子サーバーを停止します。

準備確認に失敗した場合は、`the engine did not become ready:` と収集済み子サーバーログ末尾を stderr に出して `finish(4)` します。既存サーバーモードでは子サーバーログがないため、通常この部分は空です。準備確認の fetch エラー自体は catch され、失敗理由を個別表示せず再試行します。`/v1/models` の取得・JSON 解釈後、または後続シナリオの fetch / bridge 呼び出しが失敗した場合に、スクリプト独自の接続失敗ログや終了コードへ変換する処理はこの周辺にはありません。

## 根拠

- `apps/host/scripts/context-e2e.mjs:25-37`: env helper、関連 `E2E_*` の既定値、および `E2E_BASE_URL` の読み取り。
- `apps/host/scripts/context-e2e.mjs:47-49`: Harness 必須条件と、既存サーバーモード時に省略されるファイル・RAM 事前確認。
- `apps/host/scripts/context-e2e.mjs:63-85`: 子プロセス停止、条件付きサーバー起動、ログ捕捉、RAM アラーム。
- `apps/host/scripts/context-e2e.mjs:87-97`: base URL 選択、health 確認、準備失敗の表示と終了コード、モデル ID 取得。
- `apps/host/scripts/context-e2e.mjs:109-123`: `/v1` を使った token count と agent bridge の接続設定。
- `apps/host/server/agent/README.md:155`: このスクリプトが実 engine を使う context E2E run として案内されている。
