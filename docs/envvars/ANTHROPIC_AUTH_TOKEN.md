# `ANTHROPIC_AUTH_TOKEN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata engine とサーバーがこの名前を直接読む実装はない。Strata CLI の `strata connect` が `--key-env ANTHROPIC_AUTH_TOKEN` と指定された場合に限り、環境から値を読み、接続先アプリ向けの API key として使う。`claude-code` harness では、そのキーを `ANTHROPIC_AUTH_TOKEN` という設定値にして表示・コピーし、`~/.claude/settings.json` の `env` に書き込む。別名の環境変数を指定した場合も読み取れるのは同じ `--key-env` 経由である。既定ではこの環境変数を参照しない。`terminal/strata_cli/launch/cmd.py:163-175,1074-1080`、`terminal/strata_cli/launch/harness.py:158-167,286-295,343-348`。

この値は接続用の Strata API key として渡される。Strata の案内も「Anthropic login or credential」は使わず、自分の Strata server が token を検査すると説明している（`terminal/strata_cli/launch/harness.py:234-241`）。MCP の `strata_connect_info` は、サーバー側で API key が必要なら設定ファイル由来の key を例に埋め込み、不要なら `none` として Claude Code 用の `env` 例を返す（`terminal/tools/strata_mcp.py:2969-2985`）。これは環境変数を読む処理ではない。

## 値と判定

`strata connect` の `--key-env NAME` は `NAME` を `os.environ.get()` に渡す。したがってこの候補名が読み取られるのは、呼び出し側が `--key-env ANTHROPIC_AUTH_TOKEN` を明示した場合だけである。値は文字列としてそのまま使われ、数値変換、空白除去、文字列比較はない。CLI の `--key` が非空ならそちらが優先される。環境値が未設定または空文字なら、起動中の launch（または `--preset` で選んだ preset）の key にフォールバックし、それも空なら `strata-local` が使われる（`terminal/strata_cli/launch/cmd.py:170-175,703-725,1074-1080`、`terminal/strata_cli/launch/harness.py:21,339-340`）。

| 条件 | unset | 有効になる値（例） | 無効・フォールバックになる値（例） |
|---|---|---|---|
| `strata connect ... --key-env ANTHROPIC_AUTH_TOKEN` を指定 | launch/preset の key、さらに無ければ `strata-local` | 非空の任意文字列（`abc`, `0`, `false`, 空白を含む文字列も加工せず採用） | 空文字は launch/preset の key、それも無ければ `strata-local` |
| `--key-env` を省略 | `ANTHROPIC_AUTH_TOKEN` は調べない。`--key`、launch/preset の key、空の場合の placeholder を使う | 該当なし | 該当なし |

`--key-env` に `ANTHROPIC_AUTH_TOKEN` を指定しつつ `--key` も与えた場合、非空の `--key` が先に採用され、環境値は優先されない。環境変数の値に境界値・無効文字列の検査はない（`terminal/strata_cli/launch/cmd.py:1076`）。

## 有効になる条件

- `strata connect` の `--key-env` の引数が正確に `ANTHROPIC_AUTH_TOKEN` であること。大文字小文字の補正は行わず、その名前で `os.environ.get()` を呼ぶ（`terminal/strata_cli/launch/cmd.py:170-171,1076`）。
- `claude-code` harness を選ぶと、解決された `Target.key` が生成する `ANTHROPIC_AUTH_TOKEN` 設定値になる。ほかの harness はこの名前を生成しない（`terminal/strata_cli/launch/harness.py:158-167,286-315`）。
- 値を表示またはコピーする場合は `strata connect claude-code` 等を実行する。設定ファイルへ永続化する場合は `--write` を指定する。Strata はこの操作で Claude Code 自体を起動しない（`terminal/strata_cli/launch/cmd.py:1120-1157`）。
- `--key-env` の値が空または未設定でもエラーにはならず、launch/preset の key または `strata-local` にフォールバックする（`terminal/strata_cli/launch/cmd.py:1074-1080`、`terminal/strata_cli/launch/harness.py:339-340`）。

## 実行時の詳細

`run_connect()` が引数と launch/preset 情報を解決するたびに環境を参照する。環境値をモジュール変数や関数内 `static` に cache する実装はない。プロセス起動後に環境を変更してから再度 `strata connect` を実行すれば、新しい値が読まれる。`--key`、環境値、launch/preset の key、placeholder の順で最初の truthy な値が採用される。`harness.target()` は最終的な空値を `strata-local` に置き換え、Claude Code の harness はその値を `ANTHROPIC_AUTH_TOKEN` に割り当てる（`terminal/strata_cli/launch/cmd.py:1074-1080`、`terminal/strata_cli/launch/harness.py:21,158-167,339-340`）。

通常出力では key をマスクし、`--show-key` がある場合は実値を出す。JSON 出力でも `harness.mask()` を通して key を含む文字列を隠す。`--write` は生成した設定ファイルを書き込み、既存ファイルは merge 指定に従って更新する。出力・書き込みでの I/O エラーは `strata: Could not write ...` と終了コード 1 で報告される（`terminal/strata_cli/launch/cmd.py:1020-1050,1081-1118,1123-1136`、`terminal/strata_cli/launch/harness.py:355-399,432-433`）。

Strata server はこの環境変数名を読まない。設定された `api_key` をクライアントがリクエストに載せた後の認証は Strata 側の API key 設定に従う。Claude Code 側の環境変数解釈や HTTP 送信の詳細は、この調査対象に含めない。関連する案内は `docs/DETAILS.md:733-740`。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-175` — `connect` の `--key` / `--key-env` 引数。
- `terminal/strata_cli/launch/cmd.py:703-725` — launch/preset から URL、key、model 等を解決。
- `terminal/strata_cli/launch/cmd.py:1074-1080` — CLI key、動的な環境名、launch/preset key の優先順位と harness 描画。
- `terminal/strata_cli/launch/cmd.py:1120-1157` — key の表示・マスクと設定ファイル書き込み。
- `terminal/strata_cli/launch/harness.py:21,158-167,234-241,286-315,339-348,355-399,432-433` — placeholder、Claude Code 用環境設定、注意書き、harness 選択、値の組み立て・出力・書き込み。
- `terminal/tools/strata_mcp.py:2957-2985` — MCP 接続情報が生成する Claude Code 向け環境設定例。
- `docs/DETAILS.md:733-740` — Claude Code 接続案内。
