# `E2E_OUT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/agent-lost-e2e.mjs` が E2E 実行の出力先ディレクトリとして使います。サーバー設定、ログ、agent bridge のデータ、各 scenario の JSON/SSE ファイル、最終結果 `result.json` をこのディレクトリ配下に作成します。Strata エンジン本体の設定ではなく、この Node.js E2E スクリプト用です（`apps/host/scripts/agent-lost-e2e.mjs:18-21,36,42,67-78,101-105,135,157,207`）。

## 値と判定

`env(name, fallback)` は `process.env[name] ?? fallback` を返すため、環境変数が未設定 (`undefined`) または null の場合にだけ fallback が使われます。Node.js の環境変数値は文字列です。空文字は未設定扱いにならず、そのまま `OUT` に使われます。値を parse、trim、展開、正規化する処理や、専用の無効値判定はありません（`apps/host/scripts/agent-lost-e2e.mjs:29-30,36`）。

| 状態 | `OUT` と結果 |
| --- | --- |
| `E2E_OUT` 未設定 | `os.tmpdir()` の下に `strata-agent-lost-` 接頭辞の一時ディレクトリを `mkdtempSync` で作成し、そのパスを使う（`apps/host/scripts/agent-lost-e2e.mjs:24-25,36`）。 |
| 空文字 | 空文字をそのまま使い、直後の `mkdirSync(OUT, { recursive: true })` に渡す。空文字を既定値に置き換える分岐はなく、ディレクトリ作成が失敗すればスクリプトはその時点で停止する（`apps/host/scripts/agent-lost-e2e.mjs:36,42`）。 |
| その他の文字列 | その文字列を出力先として `mkdirSync(..., { recursive: true })` に渡す。相対パスはプロセスの作業ディレクトリ基準で解決される。 |

なお `mkdtempSync(...)` は `env(...)` の fallback 引数として呼び出し式に直接書かれています。JavaScript は関数呼び出し前に引数を評価するため、`E2E_OUT` が設定済みでも一時ディレクトリの作成自体は先に行われます。ただし、その場合 `OUT` として採用されず、このスクリプトがその一時ディレクトリへ成果物を書くこともありません（`apps/host/scripts/agent-lost-e2e.mjs:36`）。

## 有効になる条件

この値を読むのは `apps/host/scripts/agent-lost-e2e.mjs` の実行経路だけです。ソース中の使用箇所は、同スクリプト冒頭の環境変数一覧コメントと、`OUT` の初期化です（`apps/host/scripts/agent-lost-e2e.mjs:18-21,36`）。E2E スクリプトを起動しなければ、この読み取りや出力先作成は行われません。`E2E_OUT` と CLI 引数、別の環境変数との上書き優先順位は実装されていません。scenario の CLI 引数は実行する scenario を選ぶだけです（`apps/host/scripts/agent-lost-e2e.mjs:40-42,141,161,179,185,194`）。

## 実行時の詳細

`OUT` はモジュール初期化時に一度決まり、その直後に再帰的にディレクトリ作成されます。後から `process.env.E2E_OUT` を変更しても `OUT` は再評価されません（`apps/host/scripts/agent-lost-e2e.mjs:29-42`）。

出力には、起動する server の設定 `server.json`、engine のログ指定 `engine.log`、ready ファイルのパス、agent bridge のデータ、各 turn の JSON、`raw` scenario の `raw-sse.txt`、最後の `result.json` が含まれます（`apps/host/scripts/agent-lost-e2e.mjs:67-78,101-108,135,157,207`）。正常・失敗・シグナル終了時には、終了処理が `result folder: <OUT>` を標準出力へ表示します（`apps/host/scripts/agent-lost-e2e.mjs:48-53`）。

スクリプトが server を起動する場合、子プロセス環境は `process.env` のコピーを基に作られるため、設定されていれば `E2E_OUT` 自体も子へ継承されます。ただし、確認したこのスクリプト内では server 起動引数や設定へ `E2E_OUT` を別途設定・転送する処理はなく、成果物パスは親スクリプト内の `OUT` から組み立てています（`apps/host/scripts/agent-lost-e2e.mjs:77-79`）。既存 server (`E2E_BASE_URL` 設定時) を使う経路では、このスクリプトから server 子プロセスを起動しません（`apps/host/scripts/agent-lost-e2e.mjs:34,58-84`）。

## 根拠

- 全参照: `apps/host/scripts/agent-lost-e2e.mjs:18-21,36`。`E2E_OUT` の実読み取りは `env('E2E_OUT', ...)` であり、`env` helper は同ファイル `:29-30`。
- 出力先の作成・使用: `apps/host/scripts/agent-lost-e2e.mjs:42,48-53,67-78,101-108,135,157,207`。
