# `strata tune plan --hold`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--hold` |
| 別名 | なし |
| 値 | tuning dimension ID を1つ指定。値を取る。複数回指定可能。 |

## 役割

指定した tuning dimension を探索対象から外し、固定値のままにするよう計画します。`plan` は候補・除外理由を表示する確認用コマンドで、測定は行いません。実際に sweep する `strata tune run` にも同名オプションがありますが、別 parser・別文書のスコープです。

## 使い方

```sh
strata tune plan --engine component:strata-engine --backend cuda --model example-model \
  --hold kv --hold expert_cache
```

`--hold` は各回に dimension ID を1つ受け取ります。同じ ID を複数回指定しても、planner 内で集合に変換されるため結果は変わりません。

## 値と既定値

- 省略時は空リストで、どの dimension も `--hold` によって除外されません。
- parser は値を文字列として受け取り、ID の列挙チェックや大文字小文字の正規化はしません。値を省略すると `argparse` の引数エラーになります。
- planner は backend とエンジンが対応する dimension のうち、ID が指定値と一致したものを `dimensions`（探索対象）から除き、`fixed` に記録します。
- 指定名が backend で探索可能な dimension でなければ、エラーにはせず `excluded` に `held constant, or not a dimension of this backend` として載せます。したがってタイプミスも拒否されず、結果の `excluded` を確認する必要があります。
- ID はソースの dimension 表にある名前です。例: `ple_io`, `kv`, `kv_grow`, `expert_cache`, `host_core`, `pool_affinity`, `pool_workers`, `spec_min_p`, `vram_reserve`, `pcie_frac`, `prompt_cache_tail`。利用可能なものは backend と実エンジンの対応フラグによって変わります。

## 実行時の動作

`strata tune plan` は `a.hold` を `plan_tuning(..., hold=...)` に渡します。planner は実エンジンの `--help` から利用可能フラグを読み、backend とフラグに適合する dimension を作った後、指定 ID と一致する項目を探索一覧から外します。`--hold` 自体はエンジンに転送されません。

保持対象が有効 dimension であれば `fixed` に記録されます。通常の dimension の値は `null`、benchmark-only dimension は「エンジン自身の既定値」という説明文字列です。planner は保持値を CLI 引数として指定しないため、具体的な既定値まではこの文書の調査範囲で確定できません。未知・非対応 ID は実行時に無視されるのではなく、計画の `excluded` に理由を残します。

人間向け出力では `searches:` に探索 dimension、`excluded:` に除外理由を表示し、探索対象がなければその旨を表示します。`--output json` は plan 全体を JSON で出力します。計画の表示後、結果の適用は別手順であり、active profile を変更しないと明示されます。

## 適用条件と副作用

このオプションは `strata tune plan` の parser に属します。指定 backend が扱える dimension のみ探索候補になります。実エンジンの `--help` を最大20秒で実行してフラグを調べ、実行不能ならフラグ一覧不明として静的 dimension 表を使う計画を返します。プラン生成ではベンチマーク測定を行わず、設定ファイルや active profile を書き換えません。エンジンの help 起動自体は子プロセスを実行します。

`strata tune run --hold` にも同様の parser 定義がありますが、こちらは別スコープで、計測を行う run に渡されます。詳細は索引にある [run の `--hold`](../run/--hold.md) を参照してください。

## 出力とエラー

- 人間向け出力は標準出力、機械可読 JSON も標準出力です。通常完了は終了コード `0`。
- `--engine` の component 参照を解決できない場合は `ProfileError`（コード `5`）になり、通常形式では `strata: ...` を標準エラーへ、JSON 形式ではエラー object を標準出力へ出します。
- `--hold` の未知 ID や backend 非対応 ID 自体は失敗条件ではなく、除外理由として出力されます。
- エンジン help の起動に失敗した場合、planner は例外にせず `engine_flags_known` を false とし、静的表に基づく計画を返します。出力にもフラグを読み取れなかったことが示されます。

## 根拠

- 索引は `strata-terminal` の `tune/plan` にこのオプションを割り当てています: `docs/cli/README.md:726-739`（調査対象リポジトリ外）。
- parser は `action="append"`, `default=[]` で値を受け取ります: `strata_cli/cli.py:395-412`。
- `plan` 分岐から `a.hold` を `plan_tuning` に渡し、JSON/人間向けの plan 出力を行います: `strata_cli/cli.py:1715-1739`。
- backend とエンジンが受け付けるフラグで探索 dimension を制限し、エンジンの `--help` を両出力ストリームから収集します: `strata_control/tuning.py:89-121`, `151-174`, `205-224`。
- `hold` は集合にされ、dimension を探索一覧から除き、指定 ID が候補にない場合は `excluded` に記録します: `strata_control/tuning.py:723-768`。
- エンジン参照の解決とエラー表示形式: `strata_cli/cli.py:527-542`, `1621-1629`。
