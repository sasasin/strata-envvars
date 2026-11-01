# `CLAUDE_CODE_MAX_CONTEXT_TOKENS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部アプリの環境変数の解釈は対象外。

## 役割

Strata 自身の実行設定を変える環境変数ではありません。`strata connect claude-code` が Claude Code 用設定を生成するとき、稼働中または指定された Strata サーバーの context サイズを `CLAUDE_CODE_MAX_CONTEXT_TOKENS` の値として出力します。Strata は通常、この名前の既存環境値を読まず、サーバーに設定済みの context を使います。

例外として、`strata connect ... --key-env CLAUDE_CODE_MAX_CONTEXT_TOKENS` と明示した場合は、共通の `--key-env` 処理がこの環境変数を API key として読みます。この用途は Claude Code の context 設定とは無関係です。

## 値と判定

通常の Claude Code 設定生成では、環境から値を parse しません。context の整数を `str(t.context)` で10進文字列にし、生成する環境辞書と `~/.claude/settings.json` の `env` オブジェクトに設定します。したがって、未設定・空文字・任意文字列を含む利用者側の同名環境値はこの出力値の決定に関与せず、生成結果は Strata 側の context で置き換わります。Strata が Claude Code を起動する処理は確認できません。

context 値の優先順位は次のとおりです。

| 入力 | 採用される値 |
| --- | --- |
| `strata connect` の `--context SIZE` | 最優先。`_context()` が `parse_context()` に渡し、1024 未満や形式不正は CLI 引数エラーになる |
| `--context` 省略時、実行中 launch の設定 | `launch_info()` が得た `context`。設定の `args` にある `--max-context` の次の引数を整数変換できた場合に取得 |
| 上記がない、または context が偽値 | 32768 tokens |

最後の選択は `a.context or info.get("context") or 32768` です。`--context` は `parse_context()` で最低1024 tokensが必要です。`harness.target()` も `context or 32768` を用います。したがって生成されるこの環境設定の値は整数の十進表記で、通常の有効な `--context` では空文字や任意の文字列にはなりません。CLI 形式の詳細は `strata_cli/launch/settings.py:65-75`、context 選択は `strata_cli/launch/cmd.py:48-52,945-950`、稼働中設定からの取得は同 `cmd.py:626-633,636-658`、文字列化は `strata_cli/launch/harness.py:111-120,272-280` にあります。

`--key-env` 経由で読む場合は別扱いです。`os.environ.get(a.key_env)` の戻り値は API key 候補として使われ、優先順位は `--key`、指定された環境変数、launch 情報の key、空文字の順です。空の環境値は Python の `or` により次候補へ進みます。これを context 値として変換することはありません（`strata_cli/launch/cmd.py:163-166,945-950`）。

## 有効になる条件

- Claude Code 用の値を生成するのは `strata connect claude-code`（別名 `claude`）です。`claude_env()` がこのキーを含む環境辞書を返し、Claude Code の設定ファイル生成も同じ辞書を使います (`strata_cli/launch/harness.py:111-120,222-231`)。
- context の値は `--context` があればその引数、なければ実行中 launch の設定から読めた値、最後に 32768 tokens です。preset を指定しても、preset の context 自体をこの経路で取得する処理はありません。`--context` は `SIZE` 形式を `parse_context()` で変換し、1024 tokens 未満を拒否します (`strata_cli/launch/cmd.py:161-166,945-950,626-658`; `strata_cli/launch/settings.py:65-75`)。
- OS、GPU backend、build macro、モデル状態による分岐はこの生成コードにはありません。`t.context <= 40960` の場合は別の `CLAUDE_CODE_SIMPLE=1` も加わりますが、対象変数自体の値は同じ context のままです (`strata_cli/launch/harness.py:111-116`)。
- `--key-env CLAUDE_CODE_MAX_CONTEXT_TOKENS` を使う場合だけ、同じ名前が API key の入力になります。`--key` があればそちらが優先され、空値なら launch 情報の key 等にフォールバックします (`strata_cli/launch/cmd.py:163-166,945-950`)。

## 実行時の詳細

`strata connect` は URL・key・model・context を決めて `harness.render()` を呼び、Claude 用ファイルと `env` 辞書を生成します (`strata_cli/launch/cmd.py:945-951`; `strata_cli/launch/harness.py:111-120,276-281`)。通常表示では `Environment:` 以下に値を出し、`--output json` では `env` フィールドに含めます (`strata_cli/launch/cmd.py:953-960,986-991`)。`--write` を指定した場合は生成した `~/.claude/settings.json` の `env` 設定を保存します。既存 JSON は merge され、同じキーは新しい設定値で置き換わります (`strata_cli/launch/harness.py:119-120,229-231,288-305`)。ファイル保存前に確認し、`--yes` で確認を省略できます (`strata_cli/launch/cmd.py:1011-1028`)。

この処理は `strata connect` の実行時に設定を生成するもので、環境値を cache して後のサーバー実行へ反映する経路ではありません。`--check` は別途サーバーへの prompt と tool call を確認します。Claude Code 自体は起動されず、生成された環境値を利用した後の挙動・ログ・失敗は Strata のコードからは確認できません (`strata_cli/launch/cmd.py:961-977,1002-1010`)。人間向け表示には Claude Code に context と output cap を設定する旨の案内が含まれます (`strata_cli/launch/harness.py:178-186`)。

## 根拠

- 候補名の全参照を Strata リポジトリで検索した結果、本番コードの直接参照は `strata_cli/launch/harness.py:115`（出力値）と `strata_cli/launch/harness.py:180-181`（案内文）です。テスト・文書上の記載もありますが、実行時挙動は上記実装に基づきます。
- 動的な環境名の読み取り箇所は `strata_cli/launch/cmd.py:947` の `os.environ.get(a.key_env)` です。引数名の定義は同 `cmd.py:163-166` です。
- `docs/TERMINAL_LAUNCH.md:170-195` は `strata connect` がサーバーの context を使って設定を表示・書き込み、Claude Code に `CLAUDE_CODE_MAX_CONTEXT_TOKENS` が必要と説明しています。実装も `harness.py:111-120,178-186` で一致します。Strata がこの変数を自分の context 設定として読む説明はありません。
