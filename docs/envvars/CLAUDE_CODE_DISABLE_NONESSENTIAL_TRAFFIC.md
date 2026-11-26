# `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata 自身の処理を切り替える環境変数ではない。Strata は `strata connect claude-code` 用の環境設定を生成するとき、この名前に文字列 `"1"` を割り当て、Claude Code の `~/.claude/settings.json` に入れる設定内容として表示・保存する。Strata プロセスの環境からこの名前の値を読み取る処理はないため、Strata のサーバー動作やリクエスト処理は変わらない。`claude_env`、`claude_file` と `claude-code` ハーネスの登録が生成元である（`terminal/strata_cli/launch/harness.py:158-167,293-295`）。

## 値と判定

Strata は入力環境変数を判定しない。`claude_env` が生成する辞書では、このキーの値は常に文字列 `"1"` であり、未設定・空文字・`0`・`false` などの入力値を読む経路や、変換・無効値判定・fallback はない（`terminal/strata_cli/launch/harness.py:158-163`）。

| 条件 | Strata が入力環境から読む値 | 生成する設定値 |
|---|---|---|
| Claude Code の設定を生成 | 読み取らない（設定の有無や内容に依存しない） | `"1"` |

## 有効になる条件

- `claude-code` ハーネスを選んで接続情報を生成する場合に限り、このキーが `env` 設定に含まれる。`Harness` 登録では `claude_env` が環境設定生成関数、`claude_file` が `~/.claude/settings.json` の生成関数として使われる（`terminal/strata_cli/launch/harness.py:166-167,293-295`）。
- `strata connect claude-code` の通常表示では生成した環境設定が `Environment:` 以下に出力される。JSON 出力では描画結果の `env` が含まれる（`terminal/strata_cli/launch/cmd.py:1080-1086,1128-1133`）。
- `--write` を指定すると、環境変数を Strata のプロセスやシェルに設定するのではなく、ハーネスのファイル一覧を保存する。Claude Code のファイルは `~/.claude/settings.json` で、`env` オブジェクトにこのキーが入る（`terminal/strata_cli/launch/harness.py:166-167,293-295`; `terminal/strata_cli/launch/cmd.py:1019-1049,1156-1167`）。既存 JSON との merge では、新しく生成した同名キーの値が優先される（`terminal/strata_cli/launch/harness.py:355-371,423-429`）。
- OS、backend、build macro、サーバーモード、モデル状態、他の環境変数による条件分岐は、このキーの生成処理にはない。人向け表示の環境変数行は Windows では `set NAME=value`、それ以外では `NAME=value` の形になるが、生成値は同じである（`terminal/strata_cli/launch/cmd.py:1128-1133`）。

## 実行時の詳細

このキーは `claude_env(t)` が辞書を作るたびに固定値として生成される。環境変数読み取りや cache はなく、Strata 実行中に外部から同名変数を変更しても、この生成値には反映されない（`terminal/strata_cli/launch/harness.py:158-167,343-348`）。

`claude_file(t)` は辞書を JSON 化して `env` オブジェクトに格納する。`--write` のときはファイル仕様の `text` を `write_file` に渡して保存するため、`out["env"]` の一覧を現在のシェル環境や子プロセスへ export する処理ではない（`terminal/strata_cli/launch/harness.py:94-95,158-167,355-399`; `terminal/strata_cli/launch/cmd.py:1041-1049,1080-1085`）。

## ログと測定値

値自体の Strata ログや測定値はない。人向けの通常表示では `Environment:` の後に `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`（Windows では `set CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`）が出る。JSON 出力では `env` の値として現れ、設定ファイル本文には JSON の `env` オブジェクトとして現れる（`terminal/strata_cli/launch/cmd.py:1128-1133,1082-1086`; `terminal/strata_cli/launch/harness.py:158-167`）。

`--write` が確認を求める場面で端末入力がないと、終了コード 2 と `--write asks first; run it in a terminal or add --yes.` を返す。書き込み失敗時は該当ファイルのエラーを返し終了コード 1 になる（`terminal/strata_cli/launch/cmd.py:1025-1049`）。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-167` — 固定値の辞書生成と Claude Code 設定 JSON。
- `terminal/strata_cli/launch/harness.py:293-295,343-348` — ハーネス登録と描画経路。
- `terminal/strata_cli/launch/harness.py:355-399,423-429` — 設定ファイル保存と既存 JSON への merge。
- `terminal/strata_cli/launch/cmd.py:1019-1049,1052-1086,1128-1133,1156-1167` — 接続 CLI の生成結果表示、JSON 出力、保存、観測可能な失敗経路。
