# `--trials`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--trials` |
| 別名 | なし |
| 値 | 整数（`argparse` の `type=int`）。parser 自体に範囲指定はありません |

## 役割

計画に記録する、探索候補の最大数を指定します。実行上限であり、指定数の候補が必ず存在したり実測されたりすることを保証しません。この文書のスコープは `strata tune plan` です。同じ名前の `strata tune run --trials` は別 parser のオプションです（`strata_cli/cli.py:398-405,414-422`）。

## 使い方

```sh
strata tune plan --engine /path/to/strata-engine --backend cuda --model example-model --trials 8
```

`--engine`、`--backend`、`--model` はこのコマンドで必須です。例の `/path/to/strata-engine` は実際に確認対象とする engine のパスに置き換えてください（`strata_cli/cli.py:398-402`）。

## 値と既定値

- 省略時は `16` です（`strata_cli/cli.py:405`）。
- `type=int` で変換されます。整数に変換できない値は `argparse` が引数エラーとして拒否し、通常の usage/error 表示と終了コード2になります（parser 定義: `strata_cli/cli.py:405`、parser の `parse_known_args` 呼び出し: `strata_cli/cli.py:2223-2231`）。
- parser に最小値・最大値の validation はありません。計画生成では `max(0, int(max_trials))` が使われるため、負の整数は拒否されず `0` に丸められます。0も受理されます（`strata_control/tuning.py:723-728,762-767`）。
- 同じオプションを複数回指定した場合の独自処理はありません。`argparse` の通常の単一値引数として最後に解析された値が使われます（`strata_cli/cli.py:405`）。

## 実行時の動作

`_tune` はこの値を `max_trials` として `tuning.plan_tuning` に渡し、生成された計画の `max_trials` に格納します。human 出力では「at most N trials」、JSON 出力では plan オブジェクトの値として表示されます。候補の次元や値の一覧は backend、engine が提示する flag、`--hold` などで決まり、`--trials` 自体は探索範囲を増減させません（`strata_cli/cli.py:1715-1739`、`strata_control/tuning.py:734-768`）。

この `plan` 経路は計測を開始しません。計画を作る際、Strata は engine を `--help` 付きで起動して flag 一覧を読み、backend ごとに利用可能な探索次元を選別します。engine を実行できない、または flag 一覧を得られない場合は静的な次元表に基づく計画となり、human 出力の `flags` 行にはその旨が表示されます（`strata_control/tuning.py:205-224,723-738`、`strata_cli/cli.py:1717-1736`）。計画の JSON 出力は `--output json` で選びます（parser: `strata_cli/cli.py:412`、出力分岐: `strata_cli/cli.py:1722-1723`）。

後続の sweep 実行では `max_trials` を上限として候補を開始し、候補数または時間上限に達すると新しい候補を開始しません。baseline の測定はこの候補上限の外であり、候補が成功した場合は最後の baseline 再測定も行います。これは tuner の実行経路の挙動で、`strata tune plan` の実行ではありません（`strata_control/tuning.py:423-469`）。

## 適用条件と副作用

- 指定値は `strata tune plan` の計画に適用されます。値は `--time` の時間上限、`--repeats` の反復数、`--hold` の探索次元固定とは別の計画フィールドです（`strata_cli/cli.py:405-412,1717-1721`、`strata_control/tuning.py:723-768`）。
- 計画表示は engine の `--help` プロセスを起動する場合があります。実行できない場合、Strata は `engine_flags_known` を false として記録し、静的表を利用します（`strata_control/tuning.py:205-224,734-735,762-767`）。
- `plan` の末尾は、結果の適用は別手順であり sweep が active profile を書き換えないと案内します（`strata_cli/cli.py:1738`）。このオプション単独で profile を変更する処理は確認できません。

## 出力とエラー

- 正常時は終了コード0です。human 出力では計画の探索上限・探索次元・除外理由を表示し、JSON 出力では `{"ok":true,"plan":...}` 形式の計画を出力します（`strata_cli/cli.py:1722-1739`、JSON 包装: `strata_cli/cli.py:535-541`）。
- 整数に変換できない値は parser エラーです。余分な未知引数も parser がエラーにします（`strata_cli/cli.py:2223-2231`）。
- engine component 参照の解決に失敗すると `_engine_arg` が `ProfileError` を送出します。engine のファイル読み取りなどで `OSError` が発生した場合、CLI はエラーを stderr（JSON 出力指定時は JSON）に出し、コード6で返します（`strata_cli/cli.py:1621-1629,2176-2183`）。engine を起動できないケースは `engine_flag_inventory` 内で捕捉され、通常はエラー終了ではなく静的表へフォールバックします（`strata_control/tuning.py:205-224`）。

## 根拠

- parser と既定値、同一名称の別スコープ: `strata_cli/cli.py:395-422`
- 値の受け渡し、計画の human/JSON 出力: `strata_cli/cli.py:1715-1739`
- 計画生成時の探索次元、engine flag inventory、上限値の丸め: `strata_control/tuning.py:151-174,205-224,723-768`
- 実行時に候補上限と時間上限を判定する箇所（plan 表示とは別経路）: `strata_control/tuning.py:423-469`
- parser 実行と parser error 経路、CLI の `OSError` 出力: `strata_cli/cli.py:2223-2231,2176-2183`
