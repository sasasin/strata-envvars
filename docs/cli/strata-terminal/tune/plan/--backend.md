# `strata tune plan --backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | `metal`、`cuda`、`hip`、`sycl`、`cpu` のいずれか。必須 |

## 役割

計画対象 engine の backend family を指定します。この値に基づいて、計画に含める tuning dimension と除外理由を決めます。実機 GPU を検出して backend を選択するオプションではありません。parser は backend 名を必須値として受け取り、後段はそれを「engine package が主張する backend」として扱います（`strata_cli/cli.py:398-402`）。

## 使い方

```sh
strata tune plan --engine /path/to/strata --backend cuda --model example-model
```

`--engine` と `--model` も必須です。`--backend` の値は小文字で指定します（`strata_cli/cli.py:398-402`）。

## 値と既定値

- `--backend` は必須で、既定値はありません。受理値は `metal`、`cuda`、`hip`、`sycl`、`cpu` です（`strata_cli/cli.py:23`, `strata_cli/cli.py:400-401`）。
- `choices` にない値は `argparse` が拒否し、usage と引数エラーを表示して終了コード 2 を返します。未知の余剰引数も `main` の `ap.error` により拒否されます（`strata_cli/cli.py:2223-2231`）。
- このオプションは `store` の通常値です。同じオプションを複数回指定した場合の個別処理はなく、`argparse` の通常の単一値引数として最後に指定した値が残ります（`strata_cli/cli.py:400-401`）。

## 実行時の動作

`strata tune plan` の dispatch 後、`_tune` は backend 値を `_engine_arg` と `tuning.plan_tuning` の両方へ渡します。通常の filesystem path はそのまま `Path` として使われます。`component:strata-engine` 形式なら、backend を指定してローカルの component engine を解決します（`strata_cli/cli.py:1621-1629`, `strata_cli/cli.py:1715-1721`）。

`plan_tuning` は engine の `--help` を subprocess で実行して認識 flags を集め、backend に対応する dimension を選びます。各 dimension の backend 対応表に加え、実 engine がその dimension の全 flags を受理するかも照合します。したがって指定 backend が持つ dimension でも、engine の help から必要な flag が確認できない場合は計画から除外されます（`strata_control/tuning.py:151-174`, `strata_control/tuning.py:205-224`, `strata_control/tuning.py:723-768`）。

Metal は CUDA/HIP/SYCL と異なる dimension を持ちます。たとえば `expert_cache`、`vram_reserve`、`pcie_frac` は CUDA/HIP/SYCL 側の表に含まれ、Metal では除外理由を付けて対象外になります（`strata_control/tuning.py:91-120`, `strata_control/tuning.py:137-149`）。同じ backend 値は tuning plan の比較 identity にも記録されます（`strata_control/tuning.py:753-765`）。

## 適用条件と副作用

- 値は `strata tune plan` のみで有効です。`strata tune run` にも同名の別スコープ option がありますが、この文書の対象外です（`strata_cli/cli.py:398-412`, `strata_cli/cli.py:414-419`）。
- engine が `component:strata-engine` の場合は、指定 backend でローカル package を選ぶ材料になります。通常の engine path の場合、コードは path から backend を検出・照合せず、指定値で dimension を絞り込みます（`strata_cli/cli.py:1621-1629`, `strata_cli/cli.py:1715-1721`）。
- `engine_flag_inventory` は `--help` を最大20秒で起動し、stdout と stderr の両方から flags を読みます。起動不能・timeout 等の場合は flags 不明として静的 dimension 表を使い、plan に `engine_flags_known=false` を記録します（`strata_control/tuning.py:205-224`, `strata_control/tuning.py:734-768`）。
- plan は tuning の測定を実行せず、active profile も変更しません。結果の plan は human または JSON stdout に返され、plan用の UUID は作られますが、この経路で job/store への書き込みはありません（`strata_control/tuning.py:723-733`, `strata_cli/cli.py:1715-1739`）。engine `--help` subprocess の起動と engine ファイルの identity 読み取りは行います（`strata_control/tuning.py:205-224`, `strata_control/tuning.py:753-768`, `strata_control/tune_history.py:48-81`）。

## 出力とエラー

- 既定の human 出力では backend, objective, repeat 数、探索 dimension、除外理由を stdout に表示し、plan に dimension がなければその旨を出して終了コード 0 を返します（`strata_cli/cli.py:1723-1739`）。
- `--output json` を併用すると `plan` オブジェクトを含む JSON を stdout に出します（`strata_cli/cli.py:412`, `strata_cli/cli.py:1641`, `strata_cli/cli.py:1722-1723`）。
- `component:strata-engine` の解決に失敗すると `EngineMissing` が `ProfileError` に変換され、CLI の通常エラー処理でメッセージが stderr（JSON出力指定時は JSON）に出て、終了コード 5 になります（`strata_cli/cli.py:1621-1629`, `strata_cli/cli.py:2166-2173`）。
- `--backend` 自体はここで受理値検証されますが、任意の engine path の実際の backend と指定値との一致を検証する専用エラー経路は確認できません。engine flags の照合によって一部または全部の dimension が除外されることがあります（`strata_cli/cli.py:400-401`, `strata_control/tuning.py:151-174`）。

## 根拠

- `strata_cli/cli.py:23` — CLI が参照する backend 候補。
- `strata_cli/cli.py:395-412` — `tune plan` parser と `--backend` の必須・choices 定義。
- `strata_cli/cli.py:1621-1629` — engine path または component reference の解決。
- `strata_cli/cli.py:1715-1739` — backend の plan への受け渡しと表示。
- `strata_control/tuning.py:68`, `strata_control/tuning.py:91-174` — backend 一覧、dimension 表、backend ごとの選別。
- `strata_control/tuning.py:205-224`, `strata_control/tuning.py:723-768` — engine help の照会、flag 照合、plan 構築。
- `strata_control/tune_history.py:48-81` — engine/model ファイル identity の読み取り。
