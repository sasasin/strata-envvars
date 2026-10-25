# `--objective`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--objective` |
| 別名 | なし |
| 値 | `generation`、`prefill`、`latency` のいずれか。省略時は `generation` |

## 役割

探索計画に含める目的名を指定します。`strata tune plan` は選んだ値を計画に記録して表示しますが、このコマンド自体はベンチマークを実行せず、目的に対応した指標の選択もしません。計画だけを確認したいときに使用します（`strata_cli/cli.py:1632-1639,1715-1739`、`strata_control/tuning.py:723-768`）。

## 使い方

```sh
strata tune plan --engine /path/to/strata --backend cuda --model my-model --objective prefill
```

`--engine`、`--backend`、`--model` はこのコマンドで必須です。目的を省略すると `generation` が使われます（`strata_cli/cli.py:398-412`）。

## 値と既定値

| 値 | 意味 |
| --- | --- |
| `generation` | 生成スループットを目的とする指定 |
| `prefill` | prompt 処理スループットを目的とする指定 |
| `latency` | time-to-first-token（TTFT）を目的とする指定 |

parser はこの3値だけを `choices` で受理し、既定値を `generation` にします。大文字小文字の変換や独自の補正はありません。別の値を渡すと `argparse` が引数エラーとして拒否します（`strata_cli/cli.py:403-404`）。

この `plan` 経路では、値は `tuning.plan_tuning()` に渡され、`TuningPlan.objective` に保存されて JSON 出力または人間向け表示に載ります（`strata_cli/cli.py:1715-1727`、`strata_control/tuning.py:269-301,762-767`）。

## 実行時の動作

`plan` は選択した engine のフラグ一覧を得るため、engine を `--help` 付きで起動し、標準出力と標準エラーを読み取ります。照会には20秒の timeout があり、起動失敗・timeout 等、または利用できるフラグを抽出できない場合は一覧を `None` として扱います。その場合も計画は作成され、静的な設定表による候補を使ったことが `engine_flags_known` に記録されます（`strata_control/tuning.py:205-224,734-768`）。選んだ目的は、この照会や候補次元のフィルタには影響しません。

`strata tune run` にも同じ名前・値・既定値のオプションがありますが、これは別のコマンドスコープです。実行側では `generation` を `tokens_per_s`、`prefill` を `prefill_tokens_per_s`、`latency` を `ttft_ms` に対応させて測定結果の評価指標にします（`strata_cli/cli.py:414-420,1763-1768`、`strata_control/tuning.py:716-718`）。`--objective` の文書は索引の規約どおり `plan` と `run` で分かれます。

## 適用条件と副作用

このオプションは `strata tune plan` のみに適用されます。計画作成は測定を行わず、アクティブな profile も変更しません（`strata_control/tuning.py:723-733`、`strata_cli/cli.py:1632-1639`）。ただし、実際の `--engine` プログラムを `--help` で起動する副作用があります。engine を実行できない場合、候補を実バイナリの対応フラグと照合できず、その旨が計画に記録されます（`strata_control/tuning.py:205-224,734-768`）。

この値と他の plan オプションとの優先順位・相互作用は実装上確認できません。目的値は計画に保持されますが、plan 内の探索候補は backend と engine のフラグ一覧、`--hold` などに基づいて作られます（`strata_control/tuning.py:151-174,734-768`）。

## 出力とエラー

- 既定の human 出力では、plan の backend、objective、候補次元、除外理由などが標準出力に表示されます。`--output json` では plan オブジェクトが成功応答に含まれます（`strata_cli/cli.py:1715-1739`）。
- `--objective` に未対応の値を指定した場合は parser の選択肢検証で失敗します。必須の `--engine`、`--backend`、`--model` がない場合も parser が拒否します（`strata_cli/cli.py:398-404`）。
- `component:strata-engine` 形式の engine 参照を解決できない場合、`_engine_arg()` は `ProfileError`（終了コード5）に変換します（`strata_cli/cli.py:1621-1629`）。任意のファイルパスについて、plan コマンド内で存在確認して拒否する処理は確認できません。

## 根拠

- `strata_cli/cli.py:395-412` — `tune plan` parser、必須引数、`--objective` の値と既定値。
- `strata_cli/cli.py:1621-1629` — engine 引数のパス・component 参照解決。
- `strata_cli/cli.py:1632-1639,1715-1739` — tune の plan 分岐、`plan_tuning()` 呼び出し、human/JSON 出力、plan が測定をしない旨。
- `strata_control/tuning.py:205-224` — engine `--help` 照会、timeout と失敗時の扱い。
- `strata_control/tuning.py:269-301,723-768` — plan データ構造、objective の保持、候補計画の作成。
- `strata_cli/cli.py:414-420,1763-1768`、`strata_control/tuning.py:716-718` — `tune run` 側の同名オプションと評価指標への対応。
