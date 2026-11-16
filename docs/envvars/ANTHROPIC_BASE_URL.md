# `ANTHROPIC_BASE_URL`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata のエンジンやサーバーは、プロセス環境の `ANTHROPIC_BASE_URL` を設定として読み取りません。Strata がこの名前を使うのは、Claude Code 向け接続情報を生成するときです。`strata connect claude-code` は、選択した Strata サーバーの root URL を `ANTHROPIC_BASE_URL` という名前で環境設定例に表示し、`~/.claude/settings.json` の `env` にも書ける JSON を生成します。値はクライアント用設定であり、Strata 自身の動作を切り替えません（`strata_cli/launch/harness.py:119-128, 237-239`; `strata_cli/launch/cmd.py:157-173, 1026-1039`）。

## 値と判定

Strata による読み取り値の判定はありません。`strata connect` の対象 URL（CLI の `--url`、実行中 launch の情報、または既定値）を加工して生成します。`server_root()` は前後空白と末尾 `/` を取り除き、末尾が大文字小文字を区別せず `/v1` ならそれも一度取り除きます。その root URL を `claude_env()` が末尾 `/` なしで出力します（`strata_cli/launch/cmd.py:993-999`; `strata_cli/launch/harness.py:274-281, 119-124`）。

| 条件 | Strata がすること | 例 |
|---|---|---|
| `strata connect claude-code` の生成 | 実行中 launch の URL を使う。接続情報がなければ `http://127.0.0.1:8080` | `http://127.0.0.1:8080` → `http://127.0.0.1:8080` |
| `--url URL` を指定 | `--url` が launch 情報より優先。前後空白・末尾 `/` を除き、末尾 `/v1` も除く | ` https://host/api/v1/ ` → `https://host/api` |
| クライアント側で変数が未設定、空、または不正な文字列 | Strata はその値を読まないため判定・fallback・警告をしない | Strata の URL 生成には影響しない |
| `--key-env NAME` に `ANTHROPIC_BASE_URL` を指定 | この汎用オプションは指定名の環境値を API key として読む。URL の上書きには使わない | 非空値は `ANTHROPIC_AUTH_TOKEN` 用。空なら通常の key 優先処理へ進む |

URL の妥当性、scheme、空文字の拒否、URL の数値境界などをこの処理は検査しません。空の URL を明示しても `a.url or ...` により launch 情報または既定 URL が使われます。キーは CLI `--key`、`--key-env NAME` で指定した値、launch 情報、空値の順で選ばれ、生成時に空なら `strata-local` が placeholder になります。これらは URL ではなく、別の `ANTHROPIC_AUTH_TOKEN` の値です（`strata_cli/launch/cmd.py:993-998`; `strata_cli/launch/harness.py:21, 274-281`）。

## 有効になる条件

- `strata connect claude-code` または alias `claude` を選ぶと、Claude Code 用の環境例と `~/.claude/settings.json` 用設定が生成されます（`strata_cli/launch/harness.py:237-239, 259-263`）。
- `--output json` は `env` と設定ファイル本文を JSON に含めます。人向け出力は `Environment:` 欄に値を表示します（`strata_cli/launch/cmd.py:1000-1008, 1026-1039`）。
- `--write` を指定すると設定ファイルを書きます。通常は確認を求め、`--yes` で確認を省略します。既存の JSON 設定は merge され、同じキーは生成値が優先されます。環境欄の表示だけではプロセス環境を書き換えたり子プロセスを起動したりしません（`strata_cli/launch/cmd.py:1059-1076`; `strata_cli/launch/harness.py:296-321, 343-349`）。
- OS、GPU backend、build macro、モデルのロード状態は URL の生成条件ではありません。

## 実行時の詳細

`run_connect()` は `--url`、launch 情報、既定 URL の順で URL を決め、`harness.target()` に渡します。ここで server root を正規化し、`render()` が Claude Code harness の `env` 関数と設定ファイル関数を呼びます。`claude_env()` は root URL を `ANTHROPIC_BASE_URL` として返し、設定ファイル関数は同じ環境辞書を JSON の `env` に格納します（`strata_cli/launch/cmd.py:993-999`; `strata_cli/launch/harness.py:119-128, 274-289`）。

この変数自体に対する `getenv`, `os.environ.get`, `os.environ[...]` の直接読み取りや cache はありません。`run_connect()` の `--key-env` は名前を動的に `os.environ.get()` へ渡しますが、その結果を API key として扱います。仮に `--key-env ANTHROPIC_BASE_URL` としても、接続先 URL は `--url` / launch 情報から別に作られます（`strata_cli/launch/cmd.py:163-168, 993-999`）。設定値を生成するだけで、Strata が Claude Code のプロセスを起動したり、環境変数を現在のプロセスへ設定したりする経路はありません。

Strata の接続案内は URL を `/v1` なしで示し、Claude Code 用設定も末尾 `/v1` なしの root URL を出力します。MCP の `strata_connect_info` も同じく root URL を `ANTHROPIC_BASE_URL` の例として返します（`strata_cli/launch/harness.py:186-191`; `tools/strata_mcp.py:2581-2591`; `strata_cli/launch/cmd.py:939`）。

## ログと測定値

通常の人向け `strata connect claude-code` は `Environment:` の下に `ANTHROPIC_BASE_URL=<生成した root URL>` を表示します。`--show-key` がない場合は生成文字列内の API key と一致する部分をマスクします。MCP 情報は JSON の `examples.claude_code.env` に URL を返します。変数の unset や値の不正に対する警告・終了経路はありません（`strata_cli/launch/cmd.py:1034-1039`; `strata_cli/launch/harness.py:352-353`; `tools/strata_mcp.py:2581-2591`）。

`docs/DETAILS.md` は Claude Code の設定例として `http://127.0.0.1:8080` を示しています。実装では固定ポートだけでなく、launch 情報または `--url` から root URL を生成します（`docs/DETAILS.md:673-679`; `strata_cli/launch/cmd.py:993-999`; `strata_cli/launch/harness.py:274-281`）。

## 根拠

- `strata_cli/launch/harness.py:21, 31-39, 119-128, 186-194, 230-239, 259-289, 296-321, 343-353`
- `strata_cli/launch/cmd.py:157-173, 939, 971-1008, 1026-1077`
- `tools/strata_mcp.py:2563-2591`
- `docs/DETAILS.md:673-679`
