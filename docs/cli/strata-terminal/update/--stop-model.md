# `strata update --stop-model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--stop-model` |
| 別名 | なし |
| 値 | 取らないフラグ（`store_true`）。未指定時は `False`。 |

## 役割

更新対象の engine または Control に変更があり、Strata が管理するモデルが稼働中の場合に、そのモデルを更新前に停止することを許可する。とくに対話入力できないスクリプトや JSON 出力では、`--yes` だけではモデル停止の同意にならないため、このフラグが必要になる。モデルを再起動するかは別の `--start-again` で指定する。

## 使い方

```sh
# スクリプトで、稼働中モデルの停止を許可して更新する
strata update --yes --stop-model

# 更新後、停止したモデルも同じ設定で再起動する
strata update --yes --stop-model --start-again
```

## 値と既定値

値を取りません。parser は `action="store_true"` で登録しており、省略時は `False`、指定時は `True` です。別名や値の validation はありません。`--check` は feed の確認後に早期 return するため、このフラグによるモデル停止処理には進みません。

## 実行時の動作

`strata update` は、更新対象に実際の変更があるかを確認し、変更があってモデルが稼働中ならモデル gate の同意処理を呼びます。`--stop-model` は gate の `allow_stop` に渡され、同意確認を満たしたモデルを記録します。更新データのダウンロード中はモデルの serving を継続し、ダウンロード後、最初の staging または test-start の前にモデルを停止します。進行中の応答は停止時に終了します。

`--yes` は質問への応答を無効にするだけで、停止許可を与えません。したがって、スクリプトでは `--yes --stop-model` のように両方が必要です。`--stop-model` だけを指定した対話端末では、停止への同意はこのフラグで与えられますが、停止後の再起動については別途質問されます。非対話実行で `--start-again` がなければ停止状態のままとなり、起動方法が案内されます。更新が失敗した場合も、停止済みモデルには再起動の機会があります。

`strata update --check` は変更を行わない確認モードで、モデル gate を経由しません。オプションは `strata components update` にも別 parser 定義で存在しますが、その文書スコープは索引に従い `components/update/--stop-model.md` です。

## 適用条件と副作用

- 更新対象に変更がなくモデルも稼働していなければ、このフラグによる停止処理はありません。
- `strata serve`、サービス、別プログラムなど、この Terminal CLI の管理下にないサーバーは停止できず、フラグがあっても拒否されます。
- 同意後、ダウンロード中に新たに起動したモデルは最初の同意の対象外です。非対話でそのモデルが見つかった場合、更新は停止処理へ進まず拒否され、ダウンロード済みデータは保持されます。
- 停止に失敗した場合、または停止後も GPU/共有 lease が解放されない場合は更新を先へ進めず、exit code 7 になります。
- モデル停止後に `--start-again` を指定しない非対話実行では、モデルが停止したままになることがあります。再起動に失敗した場合、更新が成功していれば exit code 8 になります。

## 出力とエラー

人が操作する通常出力では、拒否理由は `stderr` に `strata: ...` として出力されます。`--output json` または `--output jsonl` では、同じ失敗経路が JSON のエラー出力になります。稼働中モデルがあり、停止許可がない場合は exit code 7 で何も変更せず、`--stop-model` を付けて再実行する案内が出ます。停止拒否、停止失敗、更新中に未同意のモデルが起動した場合も、モデル gate のエラー経路を通ります。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-69` — `strata update` parser と `--stop-model` の `store_true` 定義、および `--yes`・`--start-again` との区別。
- `terminal/strata_cli/update_cmd.py:303-321` — `--check` の早期 return、通常更新での gate 接続、および machine output 判定。
- `terminal/strata_cli/update_cmd.py:374-386,400-417` — エラー出力先・終了コードの返却と、`--stop-model` / `--start-again` の gate への受け渡し。
- `terminal/strata_control/updater.py:2060-2074,395-401` — 変更がある場合の稼働確認、同意処理の呼び出し、ダウンロード後の停止処理の位置。
- `terminal/strata_control/engine_update.py:182-202,285-325` — 管理可能なモデルと停止不能な server の識別、および `allow_stop` による同意条件。
- `terminal/strata_control/engine_update.py:327-367` — ダウンロード後の再確認、未同意モデル・停止失敗・解放待ちの拒否経路。
- `terminal/strata_control/engine_update.py:369-425` — 停止後の再起動判断、失敗時の扱い、exit code 8 への変換。
