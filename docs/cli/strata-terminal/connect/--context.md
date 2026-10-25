# `--context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <アプリ>` |
| オプション | `--context` |
| 別名 | なし |
| 値 | `SIZE`。トークン数、または `k` / `m` 単位付きサイズ |

## 役割

接続先アプリ向けに `strata connect` が表示または書き出す設定で、サーバーのコンテキスト長として使う値を指定します。このオプション自体は Strata サーバーを起動・再設定しません。接続設定の生成に使う `Target.context` を上書きします（`strata_cli/launch/cmd.py:148-165, 864-870`; `strata_cli/launch/harness.py:27-42, 259-267`）。

## 使い方

```sh
strata connect opencode --context 128k
```

設定の表示だけなら `--write` は不要です。既定の接続情報ではなく別サーバーに接続する設定を作る場合は、同じ `connect` コマンドで `--url` なども指定します。

## 値と既定値

`SIZE` は整数または小数の数値で、末尾に `k` / `m`（大文字小文字を区別しない）を付けられます。`k` は 1,024 トークン、`m` は 1,048,576 トークンとして整数へ変換されます。前後の空白は除去され、内部の空白・カンマ・アンダースコアも取り除いてから解釈されます。変換後に 1,024 未満となる値は拒否されます。1,024 以上の上限は parser に定義されていません（`strata_cli/launch/settings.py:47-57`）。

省略時は、`--preset` で選んだ起動情報（実行中の同名 launch があればその設定）または既定で選ばれた実行中 launch の設定から `--max-context` の値を読み取ります。その値が得られない場合は 32,768 トークン（32k）です。明示した `--context` はこの値に優先します（`strata_cli/launch/cmd.py:595-627, 864-869`）。ヘルプの説明も「実行中 launch の値、なければ 32k」としています（同 `cmd.py:158`）。

## 実行時の動作

値は共通変換関数 `_context` から `settings.parse_context` に渡され、トークン数の整数になります。選択したアプリの設定 renderer に同じ `Target.context` が渡され、アプリごとの設定値や補助値に反映されます。たとえば OpenCode の `limit.context`、Codex の `model_context_window`、Claude Code の `CLAUDE_CODE_MAX_CONTEXT_TOKENS`、Pi の `contextWindow`、Hermes の `context_length` に使われます。OpenCode の入力上限や設定内の compaction buffer/reserve、OpenClaw の `contextTokens` もこの値から算出されます（`strata_cli/launch/cmd.py:48-52, 868-870`; `strata_cli/launch/harness.py:40-42, 80-104, 124-139, 142-149`）。

`--check` を付けても、この値を使った設定表示・JSON生成は行われますが、チェックリクエスト自体には context を渡しません。チェック処理へ渡されるのはアプリ ID、URL、key、model です（`strata_cli/launch/cmd.py:880-896, 921-929`）。

`--write` を付けると、生成設定をアプリの設定ファイルに書き込みます。既存ファイルは書き込み前にバックアップされ、JSON の merge 対象では既存キーを保って新しい値を適用します。非対話入力で `--yes` がなければ書き込み前に終了コード 2 で拒否されます。したがって、明示した context は書き込んだクライアント設定にも残ります（`strata_cli/launch/cmd.py:930-947`; `strata_cli/launch/harness.py:275-298`）。

## 適用条件と副作用

`<アプリ>` を指定した場合に、そのアプリ用の設定生成へ適用されます。アプリ名を省略して一覧を出す経路はアプリ一覧だけを出力し、context は設定に反映されません（`strata_cli/launch/cmd.py:842-856`）。`deepseek-harness` は組み込みアプリとして登録され、独自の設定ファイル生成関数を持たないため、context を含む設定ファイル・環境変数は生成しません（`strata_cli/launch/harness.py:222-234, 263-268`）。

無効な形式、または 1,024 トークン未満は parser の型変換時にエラーになります。`parse_context` の `ValueError` は `argparse.ArgumentTypeError` に変換されます（`strata_cli/launch/cmd.py:48-52`; `strata_cli/launch/settings.py:50-56`）。実行時に扱えるコンテキスト上限や、接続先サーバーの実際の上限との照合は、この parser / connect 処理では確認できません。

## 出力とエラー

- context 値の形式エラーまたは最小値未満は引数エラーになります。対象 CLI のトップレベル parser は未知引数を `strata connect` 向けメッセージとして stderr に出し終了コード 2 を返します。型エラーも argparse による引数処理で拒否されます（`strata_cli/cli.py:2223-2231`; `strata_cli/launch/cmd.py:48-52`）。
- 有効なアプリ名がない場合は、候補名を含むエラーを stderr に出して終了コード 2 を返します（`strata_cli/launch/cmd.py:857-863`）。
- `--output json` では、context を含む生成設定を JSON に出力します。秘密鍵は通常マスクされ、`--show-key` の指定で表示されます（`strata_cli/launch/cmd.py:871-879, 897-910`）。
- `--write` によるファイル変更、バックアップ、確認動作は上記「実行時の動作」のとおりです。書き込み対象のないアプリでは `Nothing to write for this app.` を表示して終了します（`strata_cli/launch/cmd.py:930-947`）。

## 根拠

- parser、値変換、既定値選択、生成処理: `strata_cli/launch/cmd.py:48-52, 148-165, 595-627, 842-947`
- サイズ解析と最小値: `strata_cli/launch/settings.py:47-57`
- 各アプリ向け設定への反映とファイル書き込み: `strata_cli/launch/harness.py:27-42, 80-149, 222-268, 275-298`
- CLI の未知引数処理: `strata_cli/cli.py:2223-2231`
