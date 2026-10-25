# `--backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | `metal`、`cuda`、`hip`、`sycl`、`cpu` のいずれか（必須） |

## 役割

測定対象 engine の backend family を tune sweep に宣言します。この値は検索する設定項目の絞り込み、測定記録の比較キー、および `--engine component:strata-engine` 形式の engine component 解決に使われます。GPU の自動検出や明示的なデバイス選択を行うオプションではありません。

## 使い方

```sh
strata tune run --engine component:strata-engine --backend cuda --model my-model
```

`--engine` と `--model` も必須です。通常の `--engine` 値には engine のパスを指定でき、`component:strata-engine` はインストール済み Strata engine component を指します。HTTP API 経由で測定する場合は、たとえば `--mode api --config ./run.json --api-expect '期待する回答の正規表現'` を加えます。

## 値と既定値

`--backend` は値を1つ取ります。受理される値は `metal`、`cuda`、`hip`、`sycl`、`cpu` で、省略時の既定値はありません。parser で必須指定かつ `choices` 制約付きです。値の別名や大文字小文字の変換はありません。複数回指定した場合は `argparse` の通常の `store` 動作で最後の値が残ります（`strata_cli/cli.py:414-418`、同 `:21-23`、`strata_control/tuning.py:66-68`）。

## 実行時の動作

指定値は `_tune_run` から `plan_tuning` に渡され、backend ごとに検索可能な tuning dimension を絞ります。さらに engine の `--help` から抽出したフラグ一覧と照合し、そのバイナリが必要フラグを受理しない dimension は除外されます。`--help` を起動できずフラグ一覧を取得できない場合、静的 dimension 表と backend の対応による絞り込みは行われますが、実バイナリのフラグ対応確認はできません（`strata_cli/cli.py:1759-1768`、`strata_control/tuning.py:151-174`、同 `:205-224`）。

選ばれた backend は測定の comparison key に記録されるため、異なる backend の測定記録は別条件として扱われます（`strata_control/tuning.py:753-765`、`strata_control/tune_history.py:99-118`）。`--engine component:strata-engine` を指定した場合は backend を component 展開処理に渡し、その backend 用の engine を解決します。engine のパスを直接指定した場合、`--backend` と実バイナリの backend が一致するかをこの段階で直接検査する処理はありません（`strata_cli/cli.py:1621-1629`、`strata_control/engine_component.py:957-966`）。

protocol mode では測定 harness が engine を候補ごとに `--serve` 付きで起動します（`strata_control/tune_engine.py:388-420`）。api mode では候補 args を `--config` で指定した設定のコピーへ反映し、worker を起動します。このとき `--backend` は dimension の選別・記録に使われますが、`--config` の engine backend を上書きしません。したがって両者が異なると、宣言した backend の検索条件と実測定対象が合わない可能性があります（`strata_cli/cli.py:1771-1786`、`strata_control/tune_api.py:259-293`）。

backend ごとの dimension 制約例として、`expert_cache` は `cuda`・`hip`・`sycl`、`vram_reserve` は `cuda`・`hip`、共通の `kv` や `spec_min_p` は5 backend 全てが候補です（`strata_control/tuning.py:91-120`）。これは候補検索の制約であり、engine が実際にそれらの設定を受け付けるかは別途フラグ一覧で確認されます。

## 適用条件と副作用

`--backend` の値と engine が不整合でも、明示パスを渡した場合に backend 不一致だけで即時拒否する処理は確認できません。実バイナリのフラグ一覧と選択 backend の dimension が一つも交差しない場合、計画には不一致の可能性が記録されますが、run は baseline 測定を行い、その後「検索項目なし」として終了する経路があります（`strata_control/tuning.py:735-751`、同 `:423-460`）。

run は baseline・候補 engine の起動と測定を行い、job state と report を state directory 以下に保存します。backend はこの測定処理の対象選択・記録に関与しますが、明示パス時にデバイスを選ぶ値として使われるわけではありません（`strata_cli/cli.py:1742-1768`、`strata_control/tuning.py:317-341`、同 `:423-476`）。測定中の候補起動失敗や timeout は候補の失敗理由として記録され、成功候補の選択から除外されます（`strata_control/tuning.py:486-523`）。

## 出力とエラー

- 未指定、または choices 外の値は argparse の usage error になります（終了コード 2）。parser の必須指定と choices 定義は `strata_cli/cli.py:414-418` にあります。
- engine path が存在しない場合は `strata: no engine binary at ...` を stderr に出し、終了コード 2 で戻ります（`strata_cli/cli.py:1759-1762`）。component reference の解決失敗は `_engine_arg` で `ProfileError` に変換されます（同 `:1621-1629`）。
- 通常の human 出力には測定開始時に `backend <値>` が含まれます。job report には backend と除外 dimension の理由が記録されます（`strata_cli/cli.py:1788-1800`、`strata_control/tuning.py:279-297`）。`--output json` では job 結果を JSON として返します（`strata_cli/cli.py:1802-1806`）。
- `--mode api` で `--config` または `--api-expect` がなければ stderr（JSON 出力時は JSON error）で説明し、終了コード 2 になります（`strata_cli/cli.py:1771-1779`）。

## 根拠

- 索引上のコマンド階層・対象リンク: `docs/cli/README.md:741-767`（調査対象 strata-envvars repo）。
- parser、必須値、choices: `strata_cli/cli.py:21-23,414-459`。
- backend から engine 解決への転送: `strata_cli/cli.py:1621-1629`、`strata_control/engine_component.py:957-966`。
- dimension 選択と実バイナリのフラグ照合: `strata_control/tuning.py:66-120,138-174,205-224,723-768`。
- 実行・出力・失敗記録: `strata_cli/cli.py:1742-1847`、`strata_control/tuning.py:317-341,423-523`、`strata_control/tune_engine.py:388-471`。
- API mode が設定ファイルのコピーを測定に使う動作: `strata_control/tune_api.py:259-293`。

調査範囲は上記 revision の checkout に含まれる Terminal CLI と `strata_control` の実装です。各 backend の GPU・driver・OS 上での実測、配布 Release artifact との照合、および `--mode api` の構成別実行確認は行っていません。
