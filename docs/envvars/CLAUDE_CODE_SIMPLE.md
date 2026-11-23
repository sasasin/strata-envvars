# `CLAUDE_CODE_SIMPLE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 自身は `CLAUDE_CODE_SIMPLE` を親プロセスの環境から読み取りません。`strata connect claude-code` の表示・設定生成処理が、Claude Code 用 `~/.claude/settings.json` の `env` オブジェクトへこの名前を条件付きで出力します。対象 context が 40,960 以下なら値 `"1"` を生成し、それより大きければ新しい生成内容にはキーを含めません。従って、Strata 内部の推論・サーバー処理を切り替える環境変数ではなく、外部アプリへ設定を渡す用途です（`terminal/strata_cli/launch/harness.py:158-167,293-295`; `terminal/strata_cli/launch/cmd.py:1074-1080,1123-1141`）。

## 値と判定

Strata はこの名前について `os.environ`、`getenv`、または値 parse helper を呼びません。したがって、利用者が起動元環境に設定した任意の値（未設定、空文字、`0`、`true` 等）を Strata が有効・無効判定する規則はありません。Strata が生成する値は context による次の二通りです。

| 生成条件 | unset | 生成する値 | 生成しない値 |
|---|---|---|---|
| context `<= 40960` | 該当なし。キーを生成する | 文字列 `"1"` | 該当なし。別の値は生成しない |
| context `> 40960` | 新規生成内容ではキーを省略 | 該当なし | 該当なし。キーを生成しない |

`claude_env()` が `t.context <= 40960` を整数比較し、真の場合だけ `{"CLAUDE_CODE_SIMPLE": "1"}` を環境辞書へ加えます。文字列値の変換や空文字・大文字小文字の検査はありません（`terminal/strata_cli/launch/harness.py:158-163`）。

## 有効になる条件

- 選択 harness が `claude-code`（別名 `claude`）であること。Claude Code の harness にだけ `claude_env` が割り当てられます（`terminal/strata_cli/launch/harness.py:293-295,318-323`）。
- 生成対象 context が `40960` 以下であること。`strata connect` では `--context`、起動中サーバー情報、または既定値 `32768` から対象 context が決まります（`terminal/strata_cli/launch/cmd.py:173,1074-1080`; `terminal/strata_cli/launch/harness.py:339-340`）。
- 生成内容を確認する場合は `strata connect claude-code`、または monitor の Connect 表示・コピー経路を使います。`--write` はファイルを書き、通常は確認を求めます（`terminal/strata_cli/launch/cmd.py:163-182,1120-1141`; `terminal/strata_cli/launch/monitor_ext.py:240-253,259-282`）。
- 外部設定ファイルが既に存在し JSON merge が行われる場合、生成側がキーを省略しても、既存の `env.CLAUDE_CODE_SIMPLE` は再帰マージで残ります。context が 40,960 以下なら生成値 `"1"` が既存値を上書きします。マージ対象は `~/.claude/settings.json` です（`terminal/strata_cli/launch/harness.py:166-167,293-295,355-370,423-429`）。

## 実行時の詳細

このキーを Strata が評価するのは `render()` が harness の環境生成関数を呼ぶときです。`strata connect` は context を決めてから `render()` を呼び、環境辞書を画面または JSON 出力に含めます。ファイル書き込みを選んだ場合は、同じ生成値を `settings.json` の `env` 内へ書き込みます。これは `claude` プロセスを Strata が起動して環境を注入する処理ではありません。実行中に親環境を変更したときの再読込やキャッシュもありません（`terminal/strata_cli/launch/cmd.py:1074-1085,1120-1141`; `terminal/strata_cli/launch/harness.py:343-348,355-399`）。

context が既定値 `32768` で設定ファイルを新規生成する場合、このキーは `"1"` です。context が `40960` を超える場合は生成した JSON から省略されますが、前述のとおり merge では既存キーを削除しません。既存の `CLAUDE_CODE_MAX_OUTPUT_TOKENS` には `_keep_output_cap()` による個別保持処理がありますが、`CLAUDE_CODE_SIMPLE` には同等の保持・削除処理がありません（`terminal/strata_cli/launch/harness.py:402-420`）。

## ログと測定値

この変数専用の警告・エラー・終了経路はありません。人間向け connect 出力では生成した環境変数を `Environment:` の下に表示し、JSON 出力では `env` フィールドに含めます（`terminal/strata_cli/launch/cmd.py:1082-1086,1128-1133`）。

`_limits_claude()` は context が 40,960 以下のとき、「32K window では `CLAUDE_CODE_SIMPLE=1` とし、20 tools / 15.6K tokens の full prompt が 3 tools / 1.25K tokens になる」と説明する案内文を追加します（`terminal/strata_cli/launch/harness.py:234-244`）。これは connect に表示する説明文であり、このソースだけでは外部アプリでの解釈や実行時の効果を確認できません。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-167` — Claude Code 用環境辞書と JSON 設定生成。
- `terminal/strata_cli/launch/harness.py:234-244,293-295` — 条件付き案内文と harness 登録。
- `terminal/strata_cli/launch/harness.py:339-348,355-399,402-429` — context 既定、レンダリング、JSON 書き込み・merge。
- `terminal/strata_cli/launch/cmd.py:163-182,1074-1085,1120-1141` — connect CLI と表示・JSON 出力。
- `terminal/strata_cli/launch/monitor_ext.py:240-253,259-282` — monitor での表示・コピー・設定書き込み。

