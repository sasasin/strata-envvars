# `ANTHROPIC_SMALL_FAST_MODEL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata 自身がこの名前をプロセス環境から読み取る箇所はありません。Claude Code 用の `strata connect` アダプターが、設定 JSON の `env` オブジェクトに `ANTHROPIC_SMALL_FAST_MODEL` を含め、その値として接続先モデル名 `Target.model` を出力します。モデル選択そのものをこの環境変数で制御する処理ではありません。アダプターの環境設定は `claude_env()`、Claude Code の設定ファイル生成は `claude_file()` で行います（`terminal/strata_cli/launch/harness.py:158-167`）。

## 値と判定

この名前の値は `os.environ` や `getenv` から読み取られず、Strata 内で値の parse、大小文字変換、空白除去、数値判定もされません。したがって Strata プロセス側で unset・空文字・任意の値を設定しても、出力には影響しません。生成値は `Target.model` そのものです。

| 状況 | Strata が出力する値 |
|---|---|
| `strata connect claude-code` の `--model NAME` を指定 | `NAME`（実行中 launch や preset のモデルより優先） |
| `--model` なしで launch 情報がある | launch 設定の `model_name`。それが空なら `strata` |
| launch 情報がなく preset もない | `strata` |
| Strata プロセス環境の `ANTHROPIC_SMALL_FAST_MODEL` が unset・空・任意の値 | 上記のモデル選択に影響しない |

CLI の `--model` は launch 情報より先に選ばれ、`target()` は偽値のモデル名を `strata` に置き換えます（`terminal/strata_cli/launch/cmd.py:1074-1079`、`terminal/strata_cli/launch/harness.py:339-340`）。launch 情報のモデルは保存された設定の `model_name` がなければ `strata` です（`terminal/strata_cli/launch/cmd.py:703-725`）。

## 有効になる条件

- `strata connect claude-code`、または同じアダプターの alias `claude` を選ぶ必要があります。登録内容は `claude-code` に `claude_env` と `claude_file` を割り当てています（`terminal/strata_cli/launch/harness.py:286-315`）。
- 設定を表示する場合は `strata connect claude-code` の実行で環境行が表示されます。JSON 出力では `env` フィールドに含まれます（`terminal/strata_cli/launch/cmd.py:1120-1133`、`terminal/strata_cli/launch/harness.py:343-348`）。
- `~/.claude/settings.json` に保存する場合は `--write` が必要です。Claude Code 用ファイルは JSON の `env` オブジェクトを生成し、既存ファイルがあれば既存の他のキーとマージし、同じキーは新しい生成値で置き換えます（`terminal/strata_cli/launch/harness.py:166-167, 293-295, 355-399, 423-429`）。書き込み前の確認を省くには `--yes` が必要です（`terminal/strata_cli/launch/cmd.py:1019-1050`）。
- `strata connect` は Claude Code 自体を起動せず、Strata サーバーの設定やリクエストへこの変数を渡しません。`--check` もアプリのリクエスト検査であり、生成設定の表示・保存とは別経路です（`terminal/strata_cli/launch/cmd.py:1087-1119, 1147-1157`）。
- OS、backend、build macro、モデル状態によるこのキーの判定分岐はありません。

## 実行時の詳細

`run_connect()` は CLI 指定値または launch/preset 情報からモデル名を選び、`Target` を作って `harness.render()` に渡します。Claude Code の `claude_env()` はそのモデル名を対象キーへ直接設定し、`claude_file()` が `{"env": ...}` として JSON 化します（`terminal/strata_cli/launch/cmd.py:1074-1080`、`terminal/strata_cli/launch/harness.py:158-167, 343-348`）。

これは `strata connect` の呼び出しごとの設定生成であり、Strata 内の起動時読み取りや cache はありません。`--write` 時は既存の `~/.claude/settings.json` を読み、JSON マージ後にファイルへ書きます。Strata は Claude Code プロセスを起動しないため、起動後の環境変更や子プロセスへの継承は扱いません（`terminal/strata_cli/launch/harness.py:355-399`）。

## ログと測定値

通常表示では `Environment:` の下に `ANTHROPIC_SMALL_FAST_MODEL=<選択されたモデル名>` を含む環境設定が表示されます。JSON 出力では `env` オブジェクトに含まれます。`--write` が成功すると対象ファイルの書き込み結果が表示されます。対象キー専用の警告・エラー・測定値はありません（`terminal/strata_cli/launch/cmd.py:1128-1133, 1156-1167`）。

## 文書との照合

`docs/TERMINAL_LAUNCH.md:175-200` は `strata connect` が接続アプリ向けの設定表示・書き込みをすることと Claude Code の前提を説明していますが、このキー個別の値規則は記載していません。`docs/DETAILS.md:754-760` は Claude Code の API 接続に関する `ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`、`ANTHROPIC_AUTH_TOKEN` を説明しています。この記載はサーバー API 側の説明であり、`strata connect` が Claude Code 設定へこのキーを生成する事実とは対象が異なります。

## 根拠

- 候補名の唯一の完全一致参照と値の割当て、Claude Code 設定生成: `terminal/strata_cli/launch/harness.py:158-167`
- Claude Code adapter 登録と alias: `terminal/strata_cli/launch/harness.py:286-315`
- adapter の選択・モデル値の優先順位・Target 生成: `terminal/strata_cli/launch/cmd.py:1067-1080`; `terminal/strata_cli/launch/harness.py:318-323, 339-348`
- ファイルのマージ・保存: `terminal/strata_cli/launch/harness.py:355-399, 423-429`
- `--write` と表示・結果の分岐: `terminal/strata_cli/launch/cmd.py:1019-1050, 1120-1167`
- 接続ガイドと API 側の説明: `docs/TERMINAL_LAUNCH.md:175-200`; `docs/DETAILS.md:754-760`
