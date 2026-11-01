# `ANTHROPIC_AUTH_TOKEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata がこの名前を通常の起動設定として直接読む実装はない。Strata は `strata connect claude-code` の設定出力先としてこの名前を使い、`--key-env` で明示された場合に限り、動的な環境変数名として読み取る。

## 役割

Strata サーバーに接続する Claude Code 用の設定に、サーバーの API キーを入れる環境変数名です。Strata の推奨接続設定では Claude Code の `settings.json` の `env` オブジェクトに書き出されます。また `strata connect claude-code` の表示・JSON 出力にも含まれます。Strata サーバー自身が起動時に `ANTHROPIC_AUTH_TOKEN` を探索するわけではありません。(`strata_cli/launch/harness.py:111-120`, `strata_cli/launch/cmd.py:976-991`)

## 値と判定

| 経路 | 未設定・空文字 | 値の処理 |
|---|---|---|
| `strata connect claude-code` の既定動作 | `ANTHROPIC_AUTH_TOKEN` を読みません。キーの取得元にもなりません | 出力先の名前として固定され、`Target.key` の値が設定されます |
| `strata connect claude-code --key-env ANTHROPIC_AUTH_TOKEN` | 指定名の環境変数が未設定または空文字なら、実行中起動情報のキー、さらにそれもなければプレースホルダーへフォールバックします | `os.environ.get(a.key_env)` で取得し、文字列変換・形式検証なしでキー候補にします |
| `strata connect claude-code --key KEY` | 空文字は Python の `or` により次の候補へ進みます | `--key` が最優先です。指定値をそのまま使います |

キーの優先順位は `--key`、`--key-env` で指定した環境変数、検出した実行中起動情報、空文字です。最後に `target()` が falsy なキー（未設定・空文字）を `strata-local` に置き換えます。`--key-env` の環境変数が空でも専用エラーにはならず、この優先順位に従って次のキー候補へ進みます。(`strata_cli/launch/cmd.py:945-950`, `strata_cli/launch/harness.py:22,272-273`)

## 有効になる条件

- 出力経路は `strata connect claude-code` を選んだ場合です。通常の `strata launch` やサーバープロセスが、この名前を自動的に読む条件はありません。Claude Code 用の環境設定は `claude_env()` が組み立てます。(`strata_cli/launch/harness.py:111-120,222-231`)
- Strata が入力としてこの名前を読むのは、`strata connect` に `--key-env ANTHROPIC_AUTH_TOKEN` を明示した場合だけです。`--key-env` は任意の環境変数名を渡す汎用 CLI 引数です。(`strata_cli/launch/cmd.py:161-165,947`)
- API キーがないサーバーに対しては、既定のキーが `strata-local` になります。キーが必要なサーバーでは、出力された値がサーバー設定の API キーと一致する必要があります。Strata の接続案内も、キーが必要な場合は `strata-<model>.json` の `api_key` を使うと説明しています。(`strata_cli/launch/harness.py:22,273`; `tools/strata_mcp.py:2660-2675`; `serve/server.py:7007-7014`)

## 実行時の詳細

`run_connect()` は `--key`、指定された場合の `os.environ.get(a.key_env)`、実行中起動情報の順でキーを選び、`Target` を作ります。起動情報のキーは実行中サーバー設定の `api_key`（値が `none` の場合は除く）または保存済み preset から得ます。(`strata_cli/launch/cmd.py:645-658,945-950`)

`claude_env()` は `t.key` を `ANTHROPIC_AUTH_TOKEN` に割り当てます。`claude_file()` はこの環境設定一式を JSON の `env` オブジェクトにし、`strata connect` は設定内容を表示できます。`--write` を指定すると `~/.claude/settings.json` へ書き込み、既存 JSON ならマージし、既存ファイルを先にバックアップします。書き込み後は可能な環境で mode `0600` を設定します。表示では通常キーをマスクし、`--show-key` 指定時は実値を表示します。(`strata_cli/launch/harness.py:111-120,288-309`; `strata_cli/launch/cmd.py:951-991,1011-1028`)

この設定値はクライアントに渡す Strata サーバー用キーです。サーバー側は設定された `svc.api_key` に対して `/v1/*` の Bearer または `x-api-key` を照合します。これは Strata サーバーの API キー処理であり、サーバーが `ANTHROPIC_AUTH_TOKEN` という名前を読む処理ではありません。(`serve/server.py:4194,7007-7014`)

## 根拠

- `strata_cli/launch/harness.py:111-120,272-280` — Claude Code 用環境辞書、設定ファイル生成、空キーのプレースホルダー、描画用データ。
- `strata_cli/launch/cmd.py:161-165,645-658,945-950` — `--key-env` の動的読み取り、実行中起動情報からのキー取得、優先順位。
- `strata_cli/launch/cmd.py:951-991,1011-1028` — 表示・JSON 出力、キーのマスク、設定ファイル書き込み経路。
- `strata_cli/launch/harness.py:288-309` — 設定 JSON のマージ、バックアップ、書き込み権限。
- `tools/strata_mcp.py:2657-2675` — 接続情報ツールが返す Claude Code 用の例と、Strata 設定のキー案内。
- `serve/server.py:7007-7014` — サーバー API キーを受信リクエストの認証情報と照合する処理。
- `docs/DETAILS.md:648-650` — 接続ガイドの説明。モデル名は Strata が無視する旨と、`ANTHROPIC_AUTH_TOKEN` または `api_key` の案内がある。
