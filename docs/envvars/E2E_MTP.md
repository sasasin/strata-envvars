# `E2E_MTP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`E2E_MTP` は、ホストアプリの AGENT-LOST end-to-end スクリプト `apps/host/scripts/agent-lost-e2e.mjs` が、テスト用モデルサーバー設定の `--mtp` に渡すパスを指定する変数です。Strata engine 自体が通常起動時に読む設定ではなく、この E2E スクリプトがサーバー起動用設定を組み立てるときだけ参照します（`apps/host/scripts/agent-lost-e2e.mjs:3-5,18-19,58-76`）。

## 値と判定

`env('E2E_MTP', fallback)` は `process.env[name] ?? fallback` です。未設定 (`undefined`) の場合だけ `$HOME/pr1426/mtp-rt`（`HOME` も未設定なら相対パス `pr1426/mtp-rt`）を使います。空文字は nullish fallback の対象ではないため、そのまま `mtp` に入り、`existsSync('')` の検査で不足扱いになります。文字列比較、数値変換、trim、大小文字変換はありません。設定値はパスとして存在確認され、存在しない場合は `missing: <値>` を stderr に出して終了コード 2 で終了します（`apps/host/scripts/agent-lost-e2e.mjs:29-30,31,58-66`）。

| 実行条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `E2E_BASE_URL` が空で、スクリプトが自分でサーバーを起動する場合 | `$HOME/pr1426/mtp-rt` | `existsSync` が存在を確認できるパス文字列（例: `/models/mtp-rt`） | 空文字、存在しないパス（例: `/missing/mtp-rt`）。`missing: ...` を出して終了コード 2 |
| `E2E_BASE_URL` が空でない場合 | 読み取りなし | 該当なし | 該当なし。既存サーバーを使う経路ではこの変数を参照しない |

ファイルかディレクトリか、またパスの内容が MTP 用として妥当かをこのスクリプトは検証しません。ここで確認できるのは `existsSync` による存在だけです（`apps/host/scripts/agent-lost-e2e.mjs:62-66`）。

## 有効になる条件

- スクリプトがサーバーを起動すること、すなわち `E2E_BASE_URL` が空であることが必要です。`E2E_BASE_URL` が空でない場合は `E2E_MTP` を含むローカル起動用パス群を読まず、既存サーバーを利用します（`apps/host/scripts/agent-lost-e2e.mjs:34,58-59,62-78,86`）。
- 自前起動経路では、`E2E_MTP` で指定したパス（または既定パス）が存在する必要があります。存在しないとサーバー設定を書き出す前に終了します（`apps/host/scripts/agent-lost-e2e.mjs:62-67`）。
- `E2E_PACK`、`E2E_GGUF1`、`E2E_GGUF2`、`E2E_ENGINE` も同じ存在確認ループの対象です。いずれかが欠けると個別の `missing: ...` を出して同様に終了するため、MTP パスだけが存在しても起動が保証されるわけではありません（`apps/host/scripts/agent-lost-e2e.mjs:59-66`）。
- 対象スクリプトは Node.js の E2E 用スクリプトです。通常の CLI、Python サーバー、engine の環境変数としてこの名前を読む箇所は、Strata checkout 内の完全一致検索では見つかりません。

## 実行時の詳細

`E2E_MTP` は `!EXISTING` 分岐に入ったとき、サーバー設定ファイルを作成する直前に読み取られます。スクリプト開始後の環境変更を監視する処理や cache はなく、この実行で使う値は `mtp` ローカル定数に保持されます（`apps/host/scripts/agent-lost-e2e.mjs:29-30,34,58-67`）。

値は生成する `server.json` の `args` 配列に `['--mtp', mtp]` として渡されます。`E2E_ENGINE_ARGS` が設定されていれば、その分割済み引数もこの配列の後ろに追加されます。続いて Python の `serve/server.py` を子プロセスとして起動し、書き出した設定ファイルのパスを `--config` に渡します（`apps/host/scripts/agent-lost-e2e.mjs:67-78`）。このスクリプト内での `E2E_MTP` の効果は、この設定値の組み立てと存在確認までです。

## ログと測定値

MTP パスが存在しない場合は stderr に `missing: ${f}` を出し、終了コード 2 で終了します。MTP パス固有の成功ログはありません（`apps/host/scripts/agent-lost-e2e.mjs:66`）。この変数に関する測定値は該当する Strata 資料で確認できませんでした。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:18-19` — E2E スクリプトの環境変数一覧コメント。
- `apps/host/scripts/agent-lost-e2e.mjs:29-37` — env helper と実行時設定値の初期化。
- `apps/host/scripts/agent-lost-e2e.mjs:58-78` — 既存サーバー利用との分岐、MTP パス既定値・存在確認、設定ファイルおよび子プロセス起動。
