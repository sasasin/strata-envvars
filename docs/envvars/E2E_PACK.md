# `E2E_PACK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`E2E_PACK` は `apps/host/scripts/agent-lost-e2e.mjs` が自前の Strata サーバーを起動するときに使う、E2E 用 pack のパス指定です。Strata の engine や通常のサーバー設定が環境から直接読む変数ではありません。スクリプトがこの値を `--pack` の値と tokenizer ディレクトリの親としてサーバー設定へ書き込みます。

このスクリプトは `AGENT-LOST end to end` のシナリオ実行用で、`STRATA_HARNESS_DIR` を要求します。`E2E_BASE_URL` が空でない場合は既存サーバーへ接続するため、自前サーバー用の設定ブロックに入らず、`E2E_PACK` も読みません（`apps/host/scripts/agent-lost-e2e.mjs:3-5,15-19,44,58-79`）。

## 値と判定

| 状態 | 値の選択・処理 |
|---|---|
| `E2E_BASE_URL` が空でない | `E2E_PACK` は評価されず、pack のパス確認も設定生成も行わない |
| 自前サーバー起動、`E2E_PACK` 未設定 | `join(HOME, '026q/pack-iq3s')` を使う。`HOME` も未設定なら空文字を使うため、既定パスは相対パス `026q/pack-iq3s` になる |
| 自前サーバー起動、`E2E_PACK` 設定済み | 値をそのまま pack パスとして使う。文字列の trim、展開、形式検証、範囲制限はしない |
| 明示的な空文字 | `??` は空文字を fallback とみなさないため、空文字のまま使う。`existsSync('')` が false となり、通常は `missing: ` を stderr に出して終了コード 2 で終わる |
| 存在しないパス | `missing: <値>` を stderr に出して終了コード 2 で終了 |
| 存在するパス | `existsSync` を通過し、設定へ進む。コードはディレクトリであることや pack の内容をここでは検証しない |

`process.env.E2E_PACK ?? fallback` による取得で、値を数値や真偽値に変換しません。空白、大文字小文字、文字列全体の構文検査もありません（`apps/host/scripts/agent-lost-e2e.mjs:29-31,58-66`）。

## 有効になる条件

- `STRATA_HARNESS_DIR` が設定されている必要があります。未設定なら `STRATA_HARNESS_DIR is not set` を stderr に出し、終了コード 2 で終了します（`apps/host/scripts/agent-lost-e2e.mjs:44`）。
- `E2E_BASE_URL` が空文字または未設定のときだけ、スクリプトは自前サーバー用の設定を作ります。この経路では pack、2 個の GGUF、MTP、engine の各パスを `existsSync` で確認し、どれかが存在しなければ `missing: <path>` を出して終了コード 2 になります（`apps/host/scripts/agent-lost-e2e.mjs:34,58-67`）。
- 既定値は `HOME` に依存します。`HOME` は `process.env.HOME ?? ''` で取得され、CLI 引数や別設定による `E2E_PACK` の上書き処理はありません（`apps/host/scripts/agent-lost-e2e.mjs:30-31,59`）。
- `E2E_PACK` はスクリプトの起動時にトップレベルの処理で一度評価されます。実行中にプロセス環境を変えても pack パスは再評価されません（`apps/host/scripts/agent-lost-e2e.mjs:58-60`）。

## 実行時の詳細

自前サーバー経路では、選ばれた pack パスを設定 JSON の `args` 配列に `--pack`, `<path>` として入れ、`tokenizer` に `join(pack, 'tokenizer')` を設定します。生成された設定で `serve/server.py --engine strata --config <config>` を子プロセス起動します（`apps/host/scripts/agent-lost-e2e.mjs:58-79`）。サーバーは `cfg["args"]` を engine 引数として使い、`StrataEngine` の起動時には `[exe, "--serve", *args]` を実行します（`serve/server.py:3492-3499,9107-9115,1152-1154`）。この経路で環境変数の値が渡される形は、設定ファイル中のパスと engine のコマンドライン引数です。

`E2E_PACK` 自身に関する専用のログや警告はありません。値が存在しないときの `missing: ...` はスクリプトの stderr 出力です。サーバーが 360 回の health check 後も ready にならない場合は `the engine did not become ready` を出して終了コード 4 になりますが、これは一般的な起動失敗経路であり、`E2E_PACK` 固有の失敗とは限りません（`apps/host/scripts/agent-lost-e2e.mjs:66,80-93`）。スクリプトが自前起動したサーバーの stdout/stderr は収集され、子プロセス終了時に `server.log` に保存されます（`apps/host/scripts/agent-lost-e2e.mjs:80-83`）。

## 根拠

- 候補名と用途の注記: `apps/host/scripts/agent-lost-e2e.mjs:18-21`。
- 環境値 helper、`HOME`、E2E 接続先の条件: `apps/host/scripts/agent-lost-e2e.mjs:29-37`。
- `E2E_PACK` の既定値、存在確認、`--pack` と tokenizer への設定: `apps/host/scripts/agent-lost-e2e.mjs:58-76`。
- 子サーバー起動とログ、ready 待ち: `apps/host/scripts/agent-lost-e2e.mjs:77-93`。
- サーバー設定引数の engine 起動への受け渡し: `serve/server.py:3492-3499,9107-9115,1152-1154`。
