# `ANTHROPIC_DEFAULT_HAIKU_MODEL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この名前を Strata のプロセス環境から読む箇所はない。端末 CLI の `strata connect claude-code` が Claude Code 用の設定を生成するとき、接続先モデル名を `ANTHROPIC_DEFAULT_HAIKU_MODEL` の値として出力する。これは Strata サーバーのモデル選択や実行時の環境変数設定ではなく、接続設定の生成である。`claude_env` は同じモデル名を `ANTHROPIC_MODEL`、`ANTHROPIC_SMALL_FAST_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL`、`ANTHROPIC_DEFAULT_OPUS_MODEL` にも割り当てる（`terminal/strata_cli/launch/harness.py:158-163`）。

## 値と判定

このキーの値自体を Strata は parse・検証しない。`claude_env` は `Target.model` をそのまま値にする。`run_connect` では `--model`、選択中の launch または preset のモデル名、最後に文字列 `strata` の順でモデル名を決める。`target` も空のモデル名を `strata` に置き換える（`terminal/strata_cli/launch/cmd.py:1074-1080`、`terminal/strata_cli/launch/harness.py:339-340`）。

| 実行条件 | OS 環境変数が未設定 | 出力される値 | 空文字・無効値 |
|---|---|---|---|
| `strata connect claude-code` | 未設定でも影響なし。Strata はこのキーを読み取らない | `--model` が非空ならその値（例: `qwen`, `0`, `true` も文字列のまま）、そうでなければ launch / preset のモデル名、どちらもなければ `strata` | このキーの値として入力する経路はない。`--model ""` は優先値にならず後続の既定値へ進む。`--model false` や空白だけの値も無効判定されず、そのままモデル名として出力される |

## 有効になる条件

- `claude-code`（または alias `claude`）の接続設定を生成した場合に限り、このキーが `claude_env` の出力に含まれる。harness 登録では Claude Code 用にこの関数と `~/.claude/settings.json` の JSON 設定が指定されている（`terminal/strata_cli/launch/harness.py:286-295`）。
- `--write` を指定すると生成 JSON を設定ファイルに書き込む。既存 JSON がある場合はマージし、同じキーは新しい生成値で置き換える。表示だけならファイルは更新されない（`terminal/strata_cli/launch/cmd.py:1019-1049`、`terminal/strata_cli/launch/harness.py:355-399,423-429`）。
- backend、OS、build macro、サーバーモードによる分岐は、この値の生成箇所にはない。

## 実行時の詳細

値は `run_connect` が引数と launch / preset 情報から `Target` を作り、`render` が `h.env(t)` を呼ぶたびに組み立てられる。プロセス環境を読む・書き換える・cache する処理はなく、このキーについて起動後の環境変更が値に反映されることもない（`terminal/strata_cli/launch/cmd.py:1074-1080`、`terminal/strata_cli/launch/harness.py:158-163,343-348`）。

`strata connect claude-code` の人向け出力では Environment 欄に値を表示し、`--output json` では `env` オブジェクトに含める。`--write` 時は `~/.claude/settings.json` の `env` に格納される。Strata はその後の Claude Code による値の解釈やモデル選択を行わない（`terminal/strata_cli/launch/cmd.py:1082-1086,1128-1133`、`terminal/strata_cli/launch/harness.py:166-167,293-295`）。

## ログと測定値

このキー固有の警告・エラー・測定値はない。接続設定の書き込みを求めても、非対話入力で `--yes` がなければ終了コード 2 と `--write asks first; run it in a terminal or add --yes.` を返す。ファイル書き込みに失敗した場合は終了コード 1 と `Could not write <path>: <error>.` を報告する。これらは設定ファイルの書き込み経路の結果であり、キー値の検証結果ではない（`terminal/strata_cli/launch/cmd.py:1019-1049,1156-1167`）。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-167` — モデル名を当該キーに割り当て、Claude Code 設定の `env` JSON を生成する。
- `terminal/strata_cli/launch/harness.py:286-295,339-348` — Claude Code harness の登録、空値の既定モデル、描画時の生成。
- `terminal/strata_cli/launch/harness.py:355-399,423-429` — 既存設定 JSON へのマージとファイル書き込み。
- `terminal/strata_cli/launch/cmd.py:163-183,1019-1049,1052-1086,1120-1133,1156-1167` — `connect` の引数、接続先モデルの優先順位、表示・JSON・書き込み処理と失敗時の終了。
