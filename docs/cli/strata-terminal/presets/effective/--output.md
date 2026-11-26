# `strata presets effective --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets effective` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

指定した設定で起動するときの実効値を確認するコマンドの出力形式を選びます。`json` は後続処理しやすい JSON、`human` は適用中のプリセットと各設定値の由来を説明するテキストです。

## 使い方

```sh
# プロファイルまたは run configuration の実効値を人間向けに表示
strata presets effective my-profile

# 同じ情報を JSON で取得
strata presets effective my-profile --output json
```

位置引数 `target` には保存済みプロファイル名、run configuration の JSON パス、または一意に特定できるインストール済みモデル名を指定できます（`terminal/strata_cli/tune_commands.py:84-85,117-140`）。

## 値と既定値

- `--output` は `human` / `json` の二択で、省略時は `human` です。`presets` 配下の各コマンドで共通 parser helper がこの設定を登録します（`terminal/strata_cli/tune_commands.py:55-61,84-85`）。
- それ以外の値は parser の `choices` により受け付けられず、コマンド処理に入りません。
- このサブコマンドには `--json` 別名は登録されていません。

## 実行時の動作

`strata presets effective` は `presets_command` から `_effective` を呼び出します（`terminal/strata_cli/cli.py:2229-2230`、`terminal/strata_cli/tune_commands.py:472-488`）。`_effective` は対象設定を読み、保存中の有効な調整プリセットを設定に重ねた結果と元設定を比較します。JSON 出力では `schema_version: 1` と `ok: true` を含むオブジェクトに、適用状態、プリセット、理由・警告、実効 `args` / `env` / `sampling`、変更箇所、設定元を含めます。人間向け出力では、プリセットが適用されているかと、明示された設定の由来を表示します（`terminal/strata_cli/tune_commands.py:544-567,101-106`）。

この処理は実効設定の確認であり、マージした設定をその場でファイルへ保存したり、エンジンを起動したりしません。プリセット overlay はストアを読み、適用条件を判定して設定辞書を組み立てます。プリセットストアを読めない場合も overlay は例外を外へ出さず元設定を返す実装です（`terminal/strata_control/presets.py:488-546`）。

## 適用条件と副作用

値の選択は出力形式だけに作用し、プリセット適用の可否は設定の選択肢と現在のマシン・モデル等の識別情報に基づく overlay 側の判定で決まります。適合しないプリセットは適用されず、JSON には `why_not` や状態・理由が含まれます。設定の読込とプリセット状態の参照は行いますが、このコマンドの処理経路にファイル書込やエンジン起動はありません（`terminal/strata_cli/tune_commands.py:548-567`、`terminal/strata_control/presets.py:488-546`）。

## 出力とエラー

- `human` は標準出力に説明文を出します。プリセットが適用されない場合、理由があれば説明に追加されます（`terminal/strata_cli/tune_commands.py:563-567,101-106`）。
- `json` は標準出力に `schema_version: 1` / `ok: true` を含む JSON を1件出します（`terminal/strata_cli/tune_commands.py:101-104,559-562`）。
- 対象が解決できないなどのエラーは、人間向けでは `strata: ...` を標準エラーへ、JSON 指定時は `ok: false` とエラー情報を標準出力へ出します。失敗時の終了コードは例外の `exit_code` があればそれを使い、なければ `2` です（`terminal/strata_cli/tune_commands.py:109-114,527-530`、`terminal/strata_cli/cli.py:2248-2255`）。
- overlay 内で発生した読み取り・評価エラーは overlay が捕捉して元設定を返します。`_effective` の payload は `info.error` を含めないため、その失敗が独立したエラーとして表示されるかはこのコマンドの当該実装から確認できません（`terminal/strata_control/presets.py:544-546`、`terminal/strata_cli/tune_commands.py:559-567`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61,84-85` — 共通 `--output` parser 定義、選択肢・既定値、および `effective` の位置引数。
- `terminal/strata_cli/cli.py:514-515,2229-2230` — parser 登録と `presets_command` へのディスパッチ。
- `terminal/strata_cli/tune_commands.py:544-567` — 対象の解決後に overlay を呼び、出力 payload と人間向け説明を生成。
- `terminal/strata_cli/tune_commands.py:101-114,472-531` — 成功・失敗時の標準出力/標準エラーとプリセットコマンドの例外処理。
- `terminal/strata_control/presets.py:488-546` — overlay の適用条件、設定の組み立て、ストア読取エラー時の fallback。
