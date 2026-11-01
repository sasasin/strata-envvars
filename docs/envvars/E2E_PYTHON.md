# `E2E_PYTHON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/context-e2e.mjs` が実エンジン用のテストサーバー `serve/server.py` を子プロセスとして起動するときに使う Python 実行ファイル名を指定します。このスクリプトだけの E2E 用設定であり、Strata の通常起動やサーバー全般の Python 設定ではありません。リポジトリ内の候補名参照は同ファイルの1箇所で、そこで共通 helper を通じて `process.env` から値を読みます（`apps/host/scripts/context-e2e.mjs:26,30`）。

## 値と判定

| 環境変数の状態 | `PYTHON` 定数の値 | 結果 |
|---|---|---|
| 未設定 | `python` | `python` を子プロセスの実行ファイルとして使う既定値 |
| 空文字 | 空文字 | 既定値への置換は行わず、空文字を実行ファイル名として渡す |
| その他の設定値 | 設定された文字列そのまま | 文字列比較、数値変換、trim、範囲検査はしない |

helper は `process.env[name] ?? fallback` を返すため、fallback になるのは値が `null` または `undefined` の場合です。Node.js の `process.env` では通常、これは未設定の場合に当たります。空文字や文字列 `0` も設定値として保持されます（`apps/host/scripts/context-e2e.mjs:26,30`）。

## 有効になる条件

- スクリプト起動時、モジュール評価中に一度 `PYTHON` 定数へ読み込まれます。実行中に環境変数を変更しても、この定数は再評価されません（`apps/host/scripts/context-e2e.mjs:25-30`）。
- `STRATA_HARNESS_DIR` が設定されていない場合は、Python 起動より前に `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード 2 で終わります（`apps/host/scripts/context-e2e.mjs:47`）。
- `E2E_BASE_URL` が空または未設定で、スクリプト自身がサーバーを起動する場合にだけ `E2E_PYTHON` が使われます。`E2E_BASE_URL` が非空なら既存サーバーを使い、子サーバーを起動しないため、この変数は実行ファイル選択に影響しません（`apps/host/scripts/context-e2e.mjs:37,48-49,78`）。
- 自前起動の分岐では、`ENGINE` と GGUF ファイルの存在確認および空き RAM の確認も Python 起動前に行われます。ファイル不足または空き RAM が 20 GB 未満なら stderr に理由を出して終了コード 2 で終わります（`apps/host/scripts/context-e2e.mjs:48-49`）。
- `E2E_PYTHON` と CLI 引数の優先順位や、別の Python 設定との連携は実装されていません。サーバー起動時の引数は固定で、選択された実行ファイルに `serve/server.py --engine strata --config ... --port ... --no-api-key --ready-file ...` を渡します（`apps/host/scripts/context-e2e.mjs:78`）。

## 実行時の詳細

自前起動では `spawn(PYTHON, [...])` で子プロセスを作り、作業ディレクトリをリポジトリのルートにします。子プロセス環境は親の `process.env` を引き継ぎ、`PATH` を `E2E_CUDA_BIN`（未設定時はスクリプト内の CUDA bin 既定値）と親の `PATH` を連結した値に上書きし、`STRATA_DATA_DIR` を scratch ディレクトリ配下に設定します。したがって `E2E_PYTHON` は実行ファイルの選択に使われ、追加の interpreter 引数への分割や Python 自体のパス検証はこのスクリプトでは行われません（`apps/host/scripts/context-e2e.mjs:30,34,51,78-80`）。

子プロセスの stdout/stderr はスクリプト内の `sink` に集められます。子プロセスが終了すると `[server exited <code>]` が追加され、サーバーが ready にならなければ末尾ログを含む `the engine did not become ready:` を stderr に出し、終了コード 4 で終了します（`apps/host/scripts/context-e2e.mjs:81-95`）。通常のシナリオ完了時は失敗した期待値の数に応じて終了コード 0 または 1 になります（`apps/host/scripts/context-e2e.mjs:179-182`）。なお `spawn` の `error` イベントに対する明示的な listener はこのスクリプトにありません（`apps/host/scripts/context-e2e.mjs:78-82`）。

## 根拠

- 環境読み取り helper と既定値: `apps/host/scripts/context-e2e.mjs:25-30`
- 既存サーバー分岐、事前条件、Python 子プロセスの起動: `apps/host/scripts/context-e2e.mjs:37,47-49,78-80`
- 子プロセス終了記録、ready 判定と失敗終了: `apps/host/scripts/context-e2e.mjs:81-95`
- E2E スクリプトとしての位置付け: `apps/host/server/agent/README.md:155`
