# `STRATA_PORT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

App Host の HTTP サーバーが listen する TCP ポートを指定する。host を直接起動すると未設定時は `8791`。開発用 `dev.mjs` も環境変数を読み、host の子プロセスへ渡す。デスクトップアプリはシェルが選んだポートでこの環境変数を上書きするため、起動元の `STRATA_PORT` は採用されない。いずれも設定変更は host の listen 先に作用し、モデルのポート設定とは別である（`app/host/server/index.mjs:109-110,295,2569`、`app/host/scripts/dev.mjs:16,63-65`、`app/desktop/src-tauri/src/main.rs:299-314,522-537`）。

Docker Compose の Intel / AMD / NVIDIA 定義にも `${STRATA_PORT:-8080}` があり、コンテナの固定ポート `8080` に対するホスト側の公開ポートとして記述されている。これは Compose 定義上のポート割当であり、Strata host プロセスがこの値を読む箇所とは別経路である（`tools/docker/compose/docker-compose.intel.yml:13-14`、`docker-compose.amd.yml:13-14`、`docker-compose.nvidia.yml:14-15`）。

## 値と判定

host はモジュール初期化時に `Number(process.env.STRATA_PORT ?? 8791)` を評価する。未設定（`undefined`）だけが `8791` になる。空文字は nullish fallback の対象ではなく `Number('')` で `0` になり、空白だけの文字列も `0` になる。全体を数値変換するため `8080` や `1e3` はそれぞれ数値 `8080`、`1000` になる一方、`0anything`、`true`、`false` は `NaN` になる。負数、小数、65535 超も変換後に値域検査・clamp されない（`app/host/server/index.mjs:109`）。

| 経路 | unset | 有効になる値（例） | 無効値・境界の扱い |
|---|---|---|---|
| host 直接起動 | `8791` | 数値として変換でき、listen が受け付けるポート番号。`8080` は `8080` | `''` は `0`。`0anything`・`true` は `NaN`。負数、小数、65535 超を Strata は検査せず listen に渡す。 |
| `app/host/scripts/dev.mjs` 経由 | スクリプトが文字列 `'8791'` を子 host に渡す | 設定値を文字列のまま渡し、host 側で上記と同じ変換 | 明示的な空文字も `??` の fallback を通らず渡され、host 側で `0` になる。 |
| デスクトップシェル経由 | 保存済みポート、なければ優先ポート `47831`。使用中ならシェルが別の空きポートを選択 | シェルが選んだポート番号を10進文字列で子 host に設定 | 親プロセスの `STRATA_PORT` は子コマンドの `.env(...)` で上書きされる。 |

Strata host は1〜65535などのアプリ独自ポート範囲を検証せず、変換値を `server.listen(PORT, HOST)` に渡す。したがって不正値に対する Strata 独自の fallback や正規化はない（`app/host/server/index.mjs:109-110,2563-2569`）。

## 有効になる条件

- host を直接起動する経路では、起動時のプロセス環境に値があること。別の CLI ポート引数による上書きはない。`--dist` は UI ディレクトリ指定で、ポート指定には使われない（`app/host/server/index.mjs:97-109`）。
- `npm run dev` 相当の `dev.mjs` 経由では、そのスクリプトの起動環境が使われ、同じ値が host に渡される。Vite の `/api` proxy 先も同じ `HOST_PORT` から組み立てられる（`app/host/scripts/dev.mjs:16,63-65`）。
- デスクトップアプリでは `pick_stable_port()` が設定ファイルのポート、または既定の `47831` を選ぶ。希望ポートが使われている場合は `pick_port()` の結果を使い、その値を host 起動コマンドに設定する。したがってアプリ利用時は親の `STRATA_PORT` よりシェルの選択が優先される（`app/desktop/src-tauri/src/shell.rs:51-58`、`app/desktop/src-tauri/src/main.rs:282-314,522-537`）。
- OS、CUDA/HIP/SYCL backend、モデルのロード状態による分岐は、この host listen ポートの読み取りにはない。ポートが使用中、または OS が bind を拒否した場合は listen 失敗経路に入る（`app/host/server/index.mjs:2563-2569`）。

## 実行時の詳細

host は起動時のモジュール評価で値を数値化して `PORT` 定数に保持し、`serving.init`、shell state、host URL、各種内部 URL、最後の `server.listen` で同じ値を使う。実行中に環境変数を変えても反映されない。ポートを設定する専用 CLI 引数はなく、`--dist` は別用途である（`app/host/server/index.mjs:97-110,153-163,220,295,2569`）。

listen 成功時、プロセス IPC がある場合は `{ type: 'strata-ready', port: PORT }` を送る。起動後に別ポートへ切り替える処理はない（`app/host/server/index.mjs:2569-2570`）。

デスクトップシェルは `shell-prefs.json` のポート設定を読み、既定では `47831` を希望する。希望ポートが空いていれば採用し、使用中なら別ポートを選ぶ。host の親環境値を引き継いだまま使うのではなく、コマンド生成時に `STRATA_PORT` を明示設定する（`app/host/server/shell-prefs.mjs:14,24-35`、`app/desktop/src-tauri/src/shell.rs:51-58`、`app/desktop/src-tauri/src/main.rs:282-314,522-537`）。

Docker Compose の3 backend 定義では `${STRATA_PORT:-8080}:8080` と記述され、ホスト側公開ポートを設定する形になっている。コンテナ側は固定 `8080`。この補間は Compose 定義の設定であり、Strata host の `process.env.STRATA_PORT` 読み取りに値が転送されるとは記載されていない（各 compose ファイルの上記行）。

## ログと測定値

host 起動時に `strata host  ·  http://${HOST}:${PORT}` を標準出力へ出す。listen 中にエラーを受け取ると `[strata] ` に続けて理由を標準エラーへ出し、終了コード `1` で終了する。`EADDRINUSE` は `Port ${port} is already in use. Strata may already be running; close it or the other program, or start Strata with another port (STRATA_PORT).`、非 Windows の `EACCES` は `This system does not let Strata use port ${port}. On Linux and macOS, ports below 1024 need administrator rights. Start Strata with another port (STRATA_PORT), for example 8801.` を出す。Windows の `EACCES` には Windows / firewall / Hyper-V / WSL / Docker の予約範囲について別文言を出す（`app/host/server/index.mjs:310,2563-2568`、`app/host/server/ports.mjs:8-14`）。

ポート動作に関する測定値は該当しない。

## 根拠

- `app/host/server/index.mjs:97-110,153-163,220,295,310,2563-2570`
- `app/host/scripts/dev.mjs:15-16,24-28,61-65`
- `app/host/server/ports.mjs:8-14`
- `app/host/server/shell-prefs.mjs:14,18,24-35`
- `app/desktop/src-tauri/src/shell.rs:51-58`
- `app/desktop/src-tauri/src/main.rs:289-314,522-537`
- `tools/docker/compose/docker-compose.intel.yml:13-14`
- `tools/docker/compose/docker-compose.amd.yml:13-14`
- `tools/docker/compose/docker-compose.nvidia.yml:14-15`
