# `--repeats`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--repeats` |
| 別名 | なし |
| 値 | 整数。省略時 `3`。実行計画では最小 `1` に補正され、上限は設けられていません。 |

## 役割

候補設定ごとに必要とする測定反復回数を、確認用チューニング計画に記録します。`plan` は実測やジョブ開始をせず、計画を表示するコマンドです。そのため、このコマンドで指定した値は計画の `repeats` 欄と表示に反映されますが、測定そのものは行いません。測定する `strata tune run` にも独立した `--repeats` があり、同じ既定値を持ちます（`strata_cli/cli.py:398-412,414-426,1715-1727`）。

## 使い方

```sh
strata tune plan --engine /path/to/strata --backend cuda --model MODEL_ID --repeats 5
```

`--engine`、`--backend`、`--model` は必須です。`--output json` を付けると、同じ計画を JSON で出力します（`strata_cli/cli.py:398-412,1715-1727`）。

## 値と既定値

- parser は `int` として読み取り、未指定時は `3` です。整数に変換できない文字列は `argparse` の引数エラーになります（`strata_cli/cli.py:408-409`）。
- 計画生成時に `max(1, int(repeats))` が適用されます。したがって `0` と負数は拒否されず `1` として記録されます。正の整数はそのまま使われ、ソース上に上限値はありません（`strata_control/tuning.py:762-768`）。
- 同じオプションを複数回書いた場合は、`argparse` の通常の単一値引数として最後に指定した値が採用されます。`--hold` のような複数回蓄積する引数ではありません（`strata_cli/cli.py:408-411`）。

## 実行時の動作

`strata tune plan` の処理は `a.repeats` を `tuning.plan_tuning(..., repeats=...)` に渡し、生成された `TuningPlan.repeats` に正規化済み値を格納します。人間向け出力は `repeats N` と表示し、JSON 出力は計画オブジェクトの `repeats` フィールドに含めます（`strata_cli/cli.py:1715-1727`, `strata_control/tuning.py:723-728,762-768`）。

計画コマンドは実測を開始しません。ただし計画に含める engine の対応フラグを調べるため、`plan_tuning` は engine に `--help` を渡す subprocess を起動します。最大20秒で、起動失敗・タイムアウト等の場合はフラグ一覧を取得できなかったものとして静的な backend 表を使い、その状態を計画に記録します（`strata_control/tuning.py:205-225,729-735`）。この `--repeats` 自体が engine に転送されるわけではありません。

実測側の `strata tune run` では、各候補の warm-up を1回行ったあと、指定回数の測定を行います。レポートで候補を推薦対象にするには、指定回数以上の測定が成功している必要があります。従って「反復回数」は warm-up を含まない測定回数です（`strata_cli/cli.py:414-426`, `strata_control/tuning.py:486-520,579-605`）。この文書の対象である `plan` の指定値は、その後に別途実行する `run` へ自動転送されません。`run` にも希望する値を指定してください。

## 適用条件と副作用

- `plan` では指定回数にかかわらず測定・GPU workload・チューニングジョブの保存は行われません。engine の `--help` 確認 subprocess と、plan 作成時の engine/model identity 読み取りは行われます（`strata_control/tuning.py:205-225,729-768`）。
- `--backend` と engine binary が提供するフラグによって検索対象 dimensions が決まります。`--repeats` は検索 dimensions や候補値を変えず、計画内の反復数だけを指定します（`strata_control/tuning.py:734-752,762-768`）。
- `--hold` は検索対象を固定する別オプションです。`--repeats` と併用しても、反復数の扱いは変わりません（`strata_cli/cli.py:408-412`, `strata_control/tuning.py:736-743`）。

## 出力とエラー

- 通常出力では engine、フラグ調査結果、backend・objective・repeats、探索・除外 dimension を表示します。`--output json` では plan オブジェクトを JSON で返します（`strata_cli/cli.py:1722-1736` および後続の表示処理）。
- 整数として解釈できない値や、必須引数の欠落、`--backend` の choices 外の値は parser エラーとなります。`main` は未認識引数も `argparse` のエラーとして扱います（`strata_cli/cli.py:398-412,2217-2232`）。
- `--repeats 0` や負数はエラー出力にならず、計画では `1` に補正されます（`strata_control/tuning.py:766-767`）。

## 根拠

- parser 定義・既定値・型: `strata_cli/cli.py:398-412`
- `plan` から計画生成・表示への引き渡し: `strata_cli/cli.py:1715-1736`
- 値の最小値補正と計画への格納: `strata_control/tuning.py:723-768`
- engine help の取得、タイムアウト、取得不能時の扱い: `strata_control/tuning.py:205-225,729-735`
- 実測側の warm-up、反復測定、推薦最低測定数: `strata_control/tuning.py:486-520,579-605`

調査範囲は上記 commit のソースコードです。同一 revision の CLI `--help` や Release 配布物は実行・照合していません。行番号は当該 revision のファイルに基づきます。
