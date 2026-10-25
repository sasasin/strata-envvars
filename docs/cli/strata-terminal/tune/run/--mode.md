# `--mode`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `protocol` または `api` |

## 役割

候補設定の測定経路を選びます。`protocol` は既定値で、推論エンジン自身の serve プロトコルを使います。`api` は設定ファイルから worker を起動し、worker の HTTP API を通して測定します。後者はユーザーが待つ API 経路の確認用です。

## 使い方

```sh
strata tune run --engine ./strata --backend cuda --model example-model \
  --mode api --config ./strata-example-model.json \
  --api-expect 'expected phrase'
```

API 測定では `--config` と `--api-expect` も必要です。通常の bounded sweep は次のように実行できます。

```sh
strata tune run --engine ./strata --backend cuda --model example-model
```

## 値と既定値

- 受理値は `protocol` と `api` のみで、省略時は `protocol` です。`argparse` の `choices` による制約です。
- 値を付けない指定、別の値、値のない `--mode` は parser エラーになります。通常の argparse usage/error 経路で終了コードは 2 です。
- 同じオプションを複数回指定した場合、通常の `argparse` の格納動作により最後の値が使われます。

## 実行時の動作

- `protocol` のときは `tune_engine.make_measure()` を選び、候補ごとに engine を起動して固定 workload を engine の serve protocol で測ります。workload は `--prompt-tokens`、`--max-new`、seed `1`、temperature `0.0` です。`--api-prompt`、`--api-expect`、`--api-port`、`--config`、API 用 timeout の値はこの分岐では参照されません。
- `api` のときは `tune_api.make_api_measure()` を選びます。指定設定を読み、候補ごとの変更を一時 JSON に書き、`python -m serve.server --engine strata --config <一時JSON> --host 127.0.0.1 --port <port>` で worker を起動します。既定ポートは `8123` です。入力した設定ファイル自体はこの測定関数から変更されず、一時 JSON は測定後に削除を試みます。
- API モードは `--api-prompt`（既定文は parser 定義参照）、`--max-new`、`--api-expect`、`--api-port`、`--boot-timeout`、`--request-timeout` を測定関数に渡します。API は streamed chat completion を送り、回答または reasoning の出力に正規表現を照合します。照合は大文字小文字を無視し、複数行にも適用されます。
- モードに関係なく tune run は baseline と候補を測定し、結果を tuning job/report に記録します。推薦の適用は別の `strata tune apply` 操作であり、この run が profile を変更することはありません。

## 適用条件と副作用

- `--mode api` では `--config` が空だと終了コード 2 で拒否されます。また `--api-expect` を省略または空にすると、誤答を成功扱いしないため終了コード 2 で拒否されます。この2条件は worker 起動前に検査されます。
- API モードはローカル loopback の `127.0.0.1` で worker を起動し、各候補測定に worker の起動・HTTP リクエスト・停止を伴います。起動は `--boot-timeout`、測定 request は `--request-timeout` の制限を受けます（いずれも既定 600 秒）。ポート競合や worker/engine の起動失敗は候補測定失敗になり得ます。
- `--api-expect` の正規表現構文は CLI parser では事前検査されません。測定時の照合でエラーまたは不一致となった候補は測定成功として記録されません。出力が空、usage の completion token 数がない、reasoning のみで answer がない場合も API 測定は失敗します。
- API モードは応答内容をチェックしますが、API harness の測定で peak resident memory も取得し、worker の process tree を対象とします。プロセス起動と一時ファイル作成が伴うため、protocol モードより実行時の副作用が大きい経路です。

## 出力とエラー

- 人間向け出力では選択された測定経路を表示します。API モードは HTTP API と照合条件を表示し、protocol モードは engine 自身の serve protocol と表示します。完了時には job ID/state、測定概要、推薦または推薦なしの理由、status/apply への案内を表示します。
- `--output json` では成功時に job 結果を JSON として出力します。mode が API で必須引数が不足する場合は JSON エラー形式（`ok:false`、code `2`）です。engine path が存在しない場合も同じく code `2` で失敗します。
- 候補の起動・通信・回答検査などの失敗は通常、job 内の候補 failure として保存・報告されます。baseline が失敗すれば sweep は候補探索を行わず、推薦なしの結果になります。

## 根拠

- `strata_cli/cli.py:414-459` — `tune run` parser、`--mode` の選択値・既定値、および関連引数。
- `strata_cli/cli.py:1742-1786` — engine path 確認、workload、API モードの必須引数検査、測定関数の選択。
- `strata_cli/cli.py:1788-1847` — 選択モードの表示、job の実行、human/JSON 結果と推薦適用の分離。
- `strata_control/tune_engine.py:596-610` — protocol mode の候補測定 harness。
- `strata_control/tune_api.py:41-104` — API worker の loopback 起動と readiness timeout。
- `strata_control/tune_api.py:146-256` — HTTP request、stream 出力・expect 検査・測定値・process tree memory。
- `strata_control/tune_api.py:259-293` — 設定読み込み、候補用一時設定、測定後の worker 停止と一時ファイル削除。
- `strata_control/tuning.py:423-484`、`486-523` — baseline/candidate の進行、job 保存、例外の候補失敗化。
- `strata_cli/cli.py:527-533` — CLI エラーの stderr/JSON 出力形式。
