# `ANTHROPIC_DEFAULT_SONNET_MODEL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata の推論サーバーやエンジンがこの環境変数を読み取る実装は見つからない。Strata がこの名前を使うのは、`strata connect claude-code` が Claude Code 用の `env` 設定を生成するときである。`claude_env()` は `ANTHROPIC_DEFAULT_SONNET_MODEL` の値として `Target.model` を設定し、同じ辞書を `~/.claude/settings.json` 用 JSON としても返す。したがって、これは Strata のモデル選択を制御する環境変数ではなく、Strata が外部アプリ用設定に値を記載する名前である（`terminal/strata_cli/launch/harness.py:158-167,293-295`）。

## 値と判定

Strata はこの変数の値を環境から読み取らず、文字列の判定・変換・検証もしない。設定生成時に、選択されたモデル名をそのまま `Target.model` からコピーする。`target()` は空のモデル名を `"strata"` に置き換えるが、空白除去、大文字小文字変換、モデル名としての妥当性確認はしない（`terminal/strata_cli/launch/harness.py:158-163,339-340`）。

| 条件 | 出力される値 |
|---|---|
| `strata connect claude-code` の `--model` に非空文字列を指定 | その文字列。`--model` が launch 情報より優先（`terminal/strata_cli/launch/cmd.py:1074-1080`） |
| `--model` が未指定または空文字 | `launch_info()` の戻り値の `model`。実行中 launch の設定 `model_name` が空なら `"strata"`（`terminal/strata_cli/launch/cmd.py:1077`; `terminal/strata_cli/launch/cmd.py:703-725`） |
| launch/preset 由来のモデル名が空文字 | `harness.target()` が `"strata"` に置換（`terminal/strata_cli/launch/harness.py:339-340`） |
| 他の値（空白を含む文字列など） | Strata 側では追加判定せず、そのまま出力 |

この名前自体に unset / 空文字 / `0` / `true` などを判定する規則はない。元になるモデル名の選択では Python の `or` による truthy 判定が使われるため、空文字は次の候補へ進み、非空文字列は内容を問わず採用される。`--preset` は `launch_info()` の対象選択に使われるが、その戻り値の `model` は実行中 launch の設定 `model_name` または `"strata"` であり、保存済み preset の `model` フィールドを直接参照するコードはこの経路にない（`terminal/strata_cli/launch/cmd.py:703-725,1074-1080`）。別の環境変数による上書きはこの生成経路にない。

## 有効になる条件

- `strata connect claude-code` の設定を表示または生成する経路でのみ、この名前が出力される。Claude Code harness は `claude_env` を使い、`~/.claude/settings.json` 向けファイルも `claude_file` から生成する（`terminal/strata_cli/launch/harness.py:158-167,293-295`）。
- `--model`、または `launch_info()` が返す実行中 launch の設定情報から `Target.model` が選ばれる。`--model` が truthy なら優先され、そうでなければ launch 情報、最後に `"strata"` が使われる。`--preset` は `launch_info()` に渡されるが、停止中 preset のモデル名はこの関数の `model` 戻り値に直接使われない（`terminal/strata_cli/launch/cmd.py:703-725,1074-1080`）。
- `strata connect` は設定を表示するだけでも環境設定値を表示する。ファイルへの反映には `--write` が必要で、確認または `--yes` を通過する必要がある（`terminal/strata_cli/launch/cmd.py:1123-1133,1156-1167`; `terminal/strata_cli/launch/cmd.py:1019-1050`）。
- `--write` 時は既存の `~/.claude/settings.json` の JSON をマージし、同じ `env` キーは新しい設定値で置き換える。書き込み前に既存ファイルのバックアップを作る（`terminal/strata_cli/launch/harness.py:355-399,423-429`; harness の merge 指定: `terminal/strata_cli/launch/harness.py:293-295`）。
- Strata は Claude Code を起動せず、実行中プロセスの環境変数も変更しない。表示または設定ファイルへの書き込みが、この値について Strata が行う処理である（`terminal/strata_cli/launch/cmd.py:1120-1167`）。

## 実行時の詳細

値は `run_connect()` が引数と `launch_info()` から URL・キー・モデル・context を決め、`harness.render()` が `claude_env(tgt)` を呼ぶ時点で組み立てられる。`claude_env()` はモデル名を4つの `ANTHROPIC_*MODEL` キーに割り当てており、この対象名にも `t.model` を直接代入する（`terminal/strata_cli/launch/cmd.py:1074-1080`; `terminal/strata_cli/launch/harness.py:158-163,339-347`）。この値に関する Strata 側の環境読み取りや cache はない。表示・JSON 出力・設定ファイル書き込みの各回で、渡された `Target` から生成する。

対象名のリポジトリ全参照を検索した結果、Strata 所有ソースでの参照は `terminal/strata_cli/launch/harness.py:160` の生成代入のみだった。Strata のサーバー側でこの変数を読んだり、リクエストのモデル選択に使ったりする経路は確認できない。そのため、生成後に外部アプリがこの設定をどう解釈するかは本書の対象外である。

## ログと測定値

環境の表示では `run_connect()` が `Environment:` の下に `NAME=value`（Windows では `set NAME=value`）形式で出力する。`--output json` では `env` フィールドと `files[].text` に設定内容を返す。キーを隠す分岐は API キーのマスキング用であり、このモデル名自体はその対象でない（`terminal/strata_cli/launch/cmd.py:1082-1086,1128-1133`）。この対象値に固有の警告・ログ・測定値はない。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-167,293-295` — Claude Code 用 env 辞書、JSON 設定、harness 登録。
- `terminal/strata_cli/launch/harness.py:339-347` — model fallback と harness レンダリング。
- `terminal/strata_cli/launch/cmd.py:703-725,1074-1080` — launch/preset 情報と `--model` 優先順位。
- `terminal/strata_cli/launch/cmd.py:1019-1050,1120-1167` — 表示・確認・書き込み経路。
- `terminal/strata_cli/launch/harness.py:355-399,423-429` — JSON 設定のマージ、バックアップ、書き込み。
- `docs/TERMINAL_LAUNCH.md:175-200` — `strata connect` の表示・書き込み・model 引数の説明。ソース実装と矛盾しない。
