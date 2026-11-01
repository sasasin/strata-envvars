# `ANTHROPIC_DEFAULT_SONNET_MODEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 自身がプロセス環境からこの名前の変数を読み取る実装は見つかりませんでした。Strata が生成する Claude Code 用の接続設定に、サーバーで使うモデル名を `ANTHROPIC_DEFAULT_SONNET_MODEL` として設定します。したがって、これは Strata サーバーのモデル選択や `/v1/messages` の処理を直接制御しません。

## 値と判定

Strata は環境変数の値を parse しません。`strata connect claude-code` の設定生成時に、選択済みモデル名 `t.model` をそのまま値にします。モデル名は `--model` があればそれを使い、なければ保存済み起動情報のモデル名、さらにそれがなければ `strata` です。接続先情報の `model` が空文字の場合も `strata` にフォールバックします。

| 状況 | 生成される値 |
|---|---|
| `--model NAME` を指定 | `NAME` |
| `--model` なし、起動情報にモデル名あり | 起動情報のモデル名 |
| どちらもモデル名なし、または選択値が空 | `strata` |

利用者のシェルに元から設定された `ANTHROPIC_DEFAULT_SONNET_MODEL` を参照したり、値の妥当性を検証したりする処理はありません。

## 有効になる条件

この設定を出力するのは `claude-code`（別名 `claude`）の接続設定を描画するときです。モデル名は `strata connect` の `--model`、保存済み起動情報、既定値の順で決まります。別の環境変数による優先順位、Strata の CLI 起動引数やサーバーモードによるこの値の切替は実装されていません。

## 実行時の詳細

`claude_env()` は `ANTHROPIC_DEFAULT_SONNET_MODEL` を含む環境設定辞書を作り、同じ辞書を `~/.claude/settings.json` 用の `env` オブジェクトにも使います。`strata connect claude-code` は設定内容を標準出力または `--output json` で表示し、`--write` 時は設定ファイルを書き込みます。人間向け表示には `ANTHROPIC_DEFAULT_SONNET_MODEL=<モデル名>` の行が含まれます。`--write` がこの値を書き込む先は Claude Code の設定ファイルであり、Strata のプロセス環境を書き換える処理ではありません。

生成処理は `render()` の呼び出しごとに行われ、対象変数を Strata 内で cache する処理はありません。Strata がこの設定値を読み取った後に起こすログ、終了、失敗経路はありません。Claude Code 側がこの設定値をどう解釈するかは本調査の対象外です。

## 根拠

- `strata_cli/launch/harness.py:111-120` は Claude 用環境辞書に `ANTHROPIC_DEFAULT_SONNET_MODEL: t.model` を設定し、その辞書を JSON の `env` に入れます。
- `strata_cli/launch/harness.py:229-231,276-281` は Claude Code harness の登録と、環境辞書・設定ファイルの生成を示します。
- `strata_cli/launch/harness.py:272-274` は空のモデル名を `strata` にする既定値を示します。
- `strata_cli/launch/cmd.py:162-167,945-951` は `--model` と preset の指定、および `--model`、起動情報、`strata` の優先順で対象を作って設定を描画する処理を示します。
- `strata_cli/launch/cmd.py:953-959,978-991,1011-1028` は JSON/標準出力への表示と `--write` によるファイル出力を示します。
- `strata_cli/launch/harness.py:288-311` は書き込み対象が指定された設定ファイルであることを示します。

`000_envvers.md` の候補一覧には名前がありますが、Strata ソース内の完全一致参照は上記の設定生成箇所だけです。Strata が実行環境からこの変数を読むという根拠はなく、候補一覧の「環境変数」は Strata が接続先アプリ向けに出力する設定名として現れています。
