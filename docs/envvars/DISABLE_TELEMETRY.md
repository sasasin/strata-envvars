# `DISABLE_TELEMETRY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

Strata 自身の設定値として読み取られる環境変数ではない。Strata は `strata connect claude-code` の設定生成時に、Claude Code 用の環境設定として `DISABLE_TELEMETRY` に文字列 `"1"` を固定で割り当てる。設定ファイル `~/.claude/settings.json` の `env` オブジェクトと、表示される環境設定の両方に含まれる（`terminal/strata_cli/launch/harness.py:158-167,293-295,343-347`）。

したがって、この名前を Strata プロセスの環境に設定しても、Strata の分岐やモデル処理が変わる根拠はない。値が Claude Code 側で何を制御するかは本調査の対象外であり、Strata のコードからは断定しない。

## 値と判定

Strata は `os.environ` 等からこの名前の値を読み取らない。Claude Code 用の設定生成時にキーを無条件で追加し、値を文字列 `"1"` とする（`terminal/strata_cli/launch/harness.py:158-167`）。

| 条件 | Strata プロセス側で未設定 | Strata プロセス側で空文字 | Strata プロセス側で `0` / `false` 等 | 生成される Claude Code 設定 |
|---|---|---|---|---|
| `claude-code` harness を選択 | 読み取りなし | 読み取りなし | 読み取りなし | `DISABLE_TELEMETRY: "1"` |
| 他の harness を選択 | 読み取りなし | 読み取りなし | 読み取りなし | この harness 定義からは出力されない |

値の大文字小文字、空白、数値変換、無効値 fallback といった判定はない。Strata が出力する値は常に文字列 `"1"` で、CLI 引数や他の環境変数による上書き箇所もない（同 `harness.py:158-167,286-315`）。

## 有効になる条件

- `claude-code` harness の設定を表示・コピー・書込みする経路で、この設定項目が生成される。登録された Claude Code harness は `claude_env` と `claude_file` を使う（`terminal/strata_cli/launch/harness.py:158-167,293-295`）。
- `strata connect` は選択した harness を描画し、通常出力では生成ファイルと環境設定を表示する。`--write` の場合だけファイル書込みを試みる（`terminal/strata_cli/launch/cmd.py:1067-1080,1123-1133,1156-1167`）。
- CUDA/HIP/SYCL、OS、サーバーモード、モデル状態による Strata 側の分岐は、この値の生成箇所にはない。

## 実行時の詳細

この名前は Strata の起動時やリクエスト時に読む設定ではない。`claude_env(Target)` が辞書を作るたびに固定値を返し、`claude_file(Target)` はそれを JSON の `env` に格納する（`terminal/strata_cli/launch/harness.py:158-167,343-347`）。Strata プロセス実行中の環境変更による再評価や cache は該当しない。

既存の Claude Code 設定へ `--write` する場合、JSON の merge は新しい値を優先するため、既存の `env.DISABLE_TELEMETRY` が別値でも生成値 `"1"` に置き換わる。既存ファイルは merge 前にバックアップされる。`--dry-run` では書込みを行わない（`terminal/strata_cli/launch/harness.py:355-399,423-429`; 呼出しと `--dry-run` の扱いは `terminal/strata_cli/launch/cmd.py:1019-1050,1108-1118`）。

## ログと測定値

Strata は `strata connect claude-code` の通常表示で `Environment:` 以下に `DISABLE_TELEMETRY=1` を表示する。JSON 出力では生成設定の `env` に含める。書込みが選ばれた場合は結果を表示・返却するが、この変数の値に起因する Strata の警告、終了、失敗経路はない（`terminal/strata_cli/launch/cmd.py:1128-1133,1156-1167`; JSON 出力は `1108-1118`）。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-167` — Claude Code 用の環境辞書に `DISABLE_TELEMETRY: "1"` を設定し、JSON `env` に組み込む。
- `terminal/strata_cli/launch/harness.py:286-315,343-347` — Claude Code harness の登録と、設定ファイル・環境辞書の描画。
- `terminal/strata_cli/launch/harness.py:355-399,423-429` — 既存 JSON の merge、書込み、バックアップ、生成値の優先。
- `terminal/strata_cli/launch/cmd.py:1067-1080,1123-1133,1156-1167` — harness 選択、表示、任意の書込み。
