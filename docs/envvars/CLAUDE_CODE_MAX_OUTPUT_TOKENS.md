# `CLAUDE_CODE_MAX_OUTPUT_TOKENS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata はこの名前の値を自分のプロセス環境から読み取って推論設定に適用するのではなく、`strata connect claude-code` が Claude Code 用に生成する設定値として `4096` を出力します。生成先は `~/.claude/settings.json` の `env` セクションで、同じ値は表示・コピー用の環境変数一覧にも含まれます。Strata 自身のモデル出力上限やサーバー応答をこの変数が変更する実装は確認できません。`strata connect` が表示する説明では、Claude Code 側のコンテキスト管理に必要な設定の一つとして案内されています。

## 値と判定

Strata の設定生成では `OUTPUT_CAP = 4096` を定数として定義し、`claude_env()` が `str(t.context)` などとともに `"CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(OUTPUT_CAP)` を辞書へ入れます。したがって生成値は常に文字列 `"4096"` です。値の parse、未設定・空文字・無効値の判定、clamp はありません。利用者のシェルで同名変数を設定していても、Strata がその値を取り込む処理はありません。

| 状況 | Strata が出力する値 |
|---|---|
| `strata connect claude-code` の通常表示・JSON 出力・画面上のコピー | `4096` |
| `~/.claude/settings.json` を生成 | `env.CLAUDE_CODE_MAX_OUTPUT_TOKENS` に文字列 `"4096"` |
| `--context`、preset、サーバー情報でコンテキストを変更 | この変数は引き続き `4096`。別の `CLAUDE_CODE_MAX_CONTEXT_TOKENS` の値が変わる |
| 既存の設定 JSON を `--write` で merge | マージは新しい値を優先するため、このキーは `"4096"` に置き換わる |

## 有効になる条件

`claude-code` ハーネスを選び、Strata がその設定を描画または生成するときに出力されます。OS、CUDA/HIP/SYCL backend、build macro、サーバーモード、モデルの実行状態による分岐はありません。別の環境変数による上書きや、CLI 引数で出力上限を指定する経路も確認できません。`Target.context` は CLI の `--context`、preset、または既定値 `32768` から決まりますが、この値は出力上限ではなく別のコンテキスト設定に使われます。

## 実行時の詳細

`strata connect` は harness を選択し、対象 URL・key・model・context から `Target` を作って `render()` を呼びます。Claude Code harness は `claude_env` を環境辞書生成関数として登録しており、その辞書を `~/.claude/settings.json` の `env` と `render()` の `env` 欄の両方に使用します。通常表示は JSON ファイル内容と環境行を出力し、`--output json` はその値を含む JSON を返します。画面のコピー機能も同じファイル内容と環境行をクリップボード向けに組み立てます。

`--write` を使う場合は（`--yes` を付けなければ確認後に）設定ファイルを書き込みます。既存ファイルは先にバックアップされ、JSON の merge では新しい設定値が同じキーの既存値に勝ちます。Strata は Claude Code 自体をこの処理で起動せず、親プロセスに既存の環境変数を設定する処理もありません。従って、この値の読み取り時期・キャッシュ・Strata 子プロセスへの転送は該当せず、Strata のログ・終了・失敗経路をこの値が制御することもありません。

ソース全体の完全一致検索では、実装上の参照は `strata_cli/launch/harness.py` の生成処理と利用者向け説明文です。その他はテストの期待値です。環境読み取り API を通じてこの名前を読む箇所は確認できません。これは Strata が Claude Code 用に値を出力する設定キーとしての用法です。

## 根拠

- `strata_cli/launch/harness.py:22-25` — `OUTPUT_CAP = 4096` の定義。
- `strata_cli/launch/harness.py:111-120` — Claude Code 向け環境辞書で固定値を作り、設定ファイルの `env` にシリアライズ。
- `strata_cli/launch/harness.py:222-231,276-281` — `claude-code` harness への登録と render の出力。
- `strata_cli/launch/harness.py:288-320` — 既存 JSON 設定を merge する際に新しいキー値を優先。
- `strata_cli/launch/cmd.py:923-952,978-991,1011-1028` — `strata connect` の対象生成、表示、`--write` 経路。
- `strata_cli/launch/monitor_ext.py:136-149,155-178,319-323` — 画面の設定表示、コピー、確認後の書き込み。
- `strata_cli/launch/harness.py:178-185` — Claude Code 向けの説明文。別の context 値と本変数の `4096` を併記。
