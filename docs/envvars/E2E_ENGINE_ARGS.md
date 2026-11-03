# `E2E_ENGINE_ARGS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/agent-lost-e2e.mjs` がローカル起動する E2E 用 Strata engine に、追加の CLI 引数を渡します。エンジン本体や通常の `serve/server.py` 起動経路がこの環境変数を直接読むわけではありません。`E2E_BASE_URL` で既存サーバーを使う場合はローカル engine の設定を作らず、この変数も読みません（`apps/host/scripts/agent-lost-e2e.mjs:15-16,58-79`）。

## 値と判定

| 値 | スクリプトでの扱い |
|---|---|
| 未設定 | 条件が偽になり、追加引数なし。 |
| 空文字 | 条件が偽になり、追加引数なし。 |
| 空白だけ | truthy なので分割するが、空要素を除くため追加引数なし。 |
| その他 | 空白類一般ではなく、半角スペース `' '` だけで分割し、空要素を除いた各要素を追加する。 |

数値・真偽値としての parse、範囲検査、trim、shell による quote や escape の解釈はありません。したがって `--flag "two words"` は shell のように 2 引数へ解釈されず、空白で分かれた各断片がそのまま要素になります。タブは区切り文字にならず、要素内に残ります（`apps/host/scripts/agent-lost-e2e.mjs:71`）。

## 有効になる条件

- `STRATA_HARNESS_DIR` が設定されている必要があります。未設定ならスクリプトは `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード 2 となり、engine 設定作成まで進みません（`apps/host/scripts/agent-lost-e2e.mjs:44`）。
- `E2E_BASE_URL` が空または未設定で、ローカルサーバーを起動する経路でのみ参照されます。既存サーバーを指定すると、engine 実行ファイル・モデル等の検査とローカル用設定作成を含む分岐を通りません（`apps/host/scripts/agent-lost-e2e.mjs:34,58-79`）。
- ローカル起動では、必須ファイルの検査を通過した後に、固定の引数列の末尾へ追加されます。固定列は `--pack`, `--native`, `--ple-gguf`、条件付き `--expert-profile`、および prefill/spec/MTP/context/KV/cache 用引数です（`apps/host/scripts/agent-lost-e2e.mjs:58-72`）。このスクリプトに重複引数の除去や優先順位判定はありません。最終的な同一 CLI option の意味は engine 側の引数処理によります。
- サーバーは config の `args` を通常の引数処理に通します。たとえば `--reasoning-effort` は engine option から取り除いて config の reasoning 設定へ移され、結合形式の option は条件により分割されます（`serve/server.py:8930-8952,8971-8996,9610-9614,9651`）。

## 実行時の詳細

Node.js の E2E スクリプトがローカル用 `server.json` を作るときに値を一度読み、分割後の配列を `args` に書き込みます。その後 `serve/server.py --engine strata --config <server.json>` を子プロセスとして起動します（`apps/host/scripts/agent-lost-e2e.mjs:67-79`）。サーバーは config を読み、通常の引数生成を行って Strata engine を `[exe, "--serve", ...args]` で起動します（`serve/server.py:9610-9614,9805-9809,3492-3513,9114-9115,1152-1154`）。

この値はスクリプトによる config 作成時点のスナップショットです。その後の環境変更で作成済み config の配列は変わりません。環境変数自体はサーバー子プロセスへ継承されますが、調査したソースでは `E2E_ENGINE_ARGS` を読む箇所は上記スクリプトの 1 箇所だけです（完全一致検索および環境読み取り API の走査）。

スクリプトは子サーバーの stdout/stderr を収集し、子が終了すると `<E2E_OUT>/server.log` に終了コードと合わせて保存します。ローカルサーバーが準備完了にならなければ `the engine did not become ready` を stderr に出し、終了コード 4 で終了処理に入ります（`apps/host/scripts/agent-lost-e2e.mjs:80-93`）。任意の追加引数の妥当性検査をこのスクリプトが行うわけではありません。個別の未知・不正な engine option に対する結果は engine の引数実装に依存するため、ここでは一律に断定しません。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:3-21,58-79` — E2E 専用スクリプトであること、既存サーバー経路とローカル engine 設定、環境値の分割・引数追加、サーバー起動。
- `apps/host/scripts/agent-lost-e2e.mjs:80-95` — 子プロセスログ、準備完了待ち、失敗時のメッセージと終了処理。
- `serve/server.py:8930-8952,8971-8996,9610-9614` — config の引数列に対するサーバー側の変換。
- `serve/server.py:3492-3513,9114-9115,1152-1154,9805-9809` — engine 引数の組立てと `--serve` 付き起動。
