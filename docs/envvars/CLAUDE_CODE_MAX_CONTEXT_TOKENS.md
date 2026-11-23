# `CLAUDE_CODE_MAX_CONTEXT_TOKENS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 自身はプロセス環境からこの変数を読み取らない。`strata connect claude-code` の設定生成時に、Strata が接続先サーバーの context を10進文字列にし、Claude Code 向け `~/.claude/settings.json` の `env` に設定する。同じ値はコマンド出力の Environment 欄にも表示される。実装は `claude_env()` と `claude_file()` で行われる（`terminal/strata_cli/launch/harness.py:158-167`）。

この値は Strata サーバーの context や推論処理を変更しない。Claude Code の設定として生成・表示される値であり、Strata が Claude Code を起動したり、この変数を子プロセスへ設定したりする処理ではない（`terminal/strata_cli/launch/harness.py:343-348`; `terminal/strata_cli/launch/cmd.py:1120-1146`）。

## 値と判定

Strata は `os.environ`、`getenv` などで既存の `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 値を読んだり、空文字・数値文字列・無効値を判定したりしない。この変数の既存の環境値は生成値の選択に関与しない。代わりに `str(t.context)` をそのまま設定値にするため、出力は整数の10進表記となる（`terminal/strata_cli/launch/harness.py:158-163`）。

| 条件 | 入力の未設定・空 | 生成される値 | 無効値・境界 |
|---|---|---|---|
| `strata connect claude-code` | `--context` がなく、実行中起動情報にも context がなければ `32768`。空文字の環境変数は参照しない | 最終的な `Target.context` を10進文字列にした値。既定時は `32768` | この環境変数自体の値を検証しない。`strata connect --context` の引数は別の parser で処理され、整数トークン数または `k` / `m` 表記を受け付け、1024 未満を拒否する（`terminal/strata_cli/launch/settings.py:71-81`）。 |

`--context` が与えられた場合はそれを優先し、なければ起動中サーバー情報の context、次に `32768` を使う（`terminal/strata_cli/launch/cmd.py:1074-1080`）。`Target` の生成でも falsy な context は `32768` に置き換わる（`terminal/strata_cli/launch/harness.py:339-340`）。

## 有効になる条件

- `strata connect claude-code`（別名 `claude` も検索可能）を選び、設定を表示・取得・書き込みする経路で生成される。Claude Code harness は `claude_env` と `claude_file` を使う（`terminal/strata_cli/launch/harness.py:286-295`）。
- `--context` が指定されたときはその値、未指定時は実行中 launch / preset から得た context があればその値、なければ 32768 が使われる。CLI の context 値は `parse_context()` が解釈する（`terminal/strata_cli/launch/cmd.py:1074-1080`; `terminal/strata_cli/launch/settings.py:71-81`）。
- OS、GPU backend、build macro、モデル状態による分岐はこの値の生成にない。`claude_env()` は `Target.context` から直接文字列を作る（`terminal/strata_cli/launch/harness.py:158-163`）。
- この設定は `strata connect` のレンダー結果である。`--write` を使わない場合は表示・JSON 出力されるだけで、設定ファイルには保存されない。書き込み時は `~/.claude/settings.json` の既存 JSON と merge され、同じ `env` キーは新しい値で置き換わる。ファイル書き込み前には通常確認があり、拒否すれば何も書かない（`terminal/strata_cli/launch/harness.py:166-167, 355-399, 423-429`; `terminal/strata_cli/launch/cmd.py:1019-1050, 1123-1157`）。

## 実行時の詳細

`run_connect()` は `--context`、実行中 launch 情報、既定値の順に context を選び、`harness.target()` と `harness.render()` に渡す。`render()` は毎回 harness の `env` 関数を呼び、Claude Code の環境設定を組み立てるため、この生成値に Strata 側の永続 cache はない（`terminal/strata_cli/launch/cmd.py:1074-1080`; `terminal/strata_cli/launch/harness.py:339-348`）。

出力先は `~/.claude/settings.json` 内の `env` と、画面 / JSON の `env` 情報である。`--write` で既存ファイルを書き換える場合はバックアップを作り、JSON merge 後に書き込む。失敗時は対象パスとエラーを返し、後続ファイルがあれば未書き込みとして報告する（`terminal/strata_cli/launch/harness.py:355-399`; `terminal/strata_cli/launch/cmd.py:1039-1050`）。Strata のコードは生成された値を実行中の Claude Code プロセスへ注入しない。

## ログと測定値

通常のテキスト出力では `Environment:` の下に変数名と値を表示する。Claude Code 向けの `Good to know` には、context と `CLAUDE_CODE_MAX_OUTPUT_TOKENS` を設定するよう促す案内文が含まれる。これは Strata が出す案内であり、接続先アプリの実際の読み取り・動作を Strata が検証したことを示すものではない（`terminal/strata_cli/launch/cmd.py:1128-1141`; `terminal/strata_cli/launch/harness.py:234-237`）。

この変数についての Strata 側の測定値は該当しない。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-167` — context 値を環境設定と Claude Code 用 JSON に組み立てる。
- `terminal/strata_cli/launch/harness.py:286-295, 339-348` — Claude Code harness の登録、target の既定値、毎回のレンダー。
- `terminal/strata_cli/launch/cmd.py:163-183, 1074-1080` — `strata connect` の context 引数と優先順。
- `terminal/strata_cli/launch/settings.py:71-81` — CLI context 値の変換・最小値判定。
- `terminal/strata_cli/launch/harness.py:355-399, 423-429`; `terminal/strata_cli/launch/cmd.py:1019-1050, 1120-1157` — 設定ファイルへの書き込み、表示、エラー経路。
- `terminal/strata_cli/launch/harness.py:234-244` — Claude Code 向け案内文。
