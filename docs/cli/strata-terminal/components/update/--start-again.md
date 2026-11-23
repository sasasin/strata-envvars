# `strata components update --start-again`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--start-again` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる。 |

## 役割

更新処理のために停止した、Strata が管理する実行中モデルを、更新後に保存済みの同じ設定で再起動する。更新が失敗した場合にも、停止済みモデルの再起動を試みる。モデルを停止する許可自体はこのフラグでは与えず、スクリプトで停止を許可するには `--stop-model` も指定する（`terminal/strata_cli/update_cmd.py:77-79,414-417`; `terminal/strata_control/engine_update.py:405-425`）。

## 使い方

```sh
# 更新時にモデルを止め、更新後は同じ設定で再起動する
strata components update --stop-model --start-again
```

## 値と既定値

`argparse` の `store_true` フラグで、値は不要、既定値は `False`。指定しない場合、スクリプトや機械出力の実行では停止したモデルを再起動せず、停止したままにする。対話端末では、停止後に再起動するかを別途質問する。引数として値を付ける形式は定義されていない（`terminal/strata_cli/update_cmd.py:70-79,400-417`; `terminal/strata_control/engine_update.py:373-388`）。

## 実行時の動作

このコマンドは `strata update` と同じ更新処理に入り、`--start-again` の値を `ModelGate.start_again` に渡す。更新のためにモデルを停止するのは、`--stop-model` で停止を許可した場合、または対話端末で停止確認に同意した場合である。`--start-again` だけではモデルの停止を許可しない。`--yes` は質問を省略するが、それだけではモデル停止の許可にならない（`terminal/strata_cli/update_cmd.py:60-79,400-417`; `terminal/strata_control/engine_update.py:300-325`）。

停止したモデルがあると、更新完了後にこのフラグが真なら再起動確認を省略して再起動する。`start_model` は保存済みプロファイルを使って起動し、実行設定の `engine_ready_s` を参照して待ち時間を決める。更新失敗時にも停止済みモデルの再起動処理を通る。再起動が失敗した場合は、プロファイルの停止・後始末を試み、理由を結果に記録する（`terminal/strata_control/engine_update.py:220-262,369-425`）。

## 適用条件と副作用

- 更新のために停止され、`ModelGate` が記録したモデルがある場合にだけ再起動処理が発生する。モデルが停止していなければ、このフラグによる再起動はない（`terminal/strata_control/engine_update.py:324-356,369-399`）。
- 別サービスや `strata serve` など、この CLI が起動していない実行中モデルは自動停止できず、更新は終了コード `7` で拒否される。更新中に新しく起動した未承認モデルが見つかった場合も停止を拒否する（`terminal/strata_control/engine_update.py:301-317,327-345`）。
- 再起動ではモデルの実行プロセスが起動し、保存済み選択に Cloudflare access が含まれる場合はトンネルの再開も試みる。トンネルだけ失敗したケースは「モデルは再稼働しているがトンネルは開かなかった」と報告する（`terminal/strata_control/engine_update.py:230-262`）。

## 出力とエラー

人間向け出力では再起動開始と結果を表示する。再起動に失敗して更新自体が成功扱い（終了コード `0`）だった場合、更新結果に終了コード `8` を返し、更新完了後に再起動できなかった旨を表示する。`--output json` / `jsonl` ではモデルの停止・再起動結果を含む JSON 系出力になる。更新失敗時は元の更新エラーコードが維持される（`terminal/strata_control/engine_update.py:33-35,390-398,405-425`; `terminal/strata_cli/update_cmd.py:307-312,367-386`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:70-79` — `components update` parser とフラグ定義。ルートの `strata update` にも同名フラグがあるが、本書の対象は索引で指定された `strata components update`。
- `terminal/strata_cli/update_cmd.py:400-417` — 対話質問の有無、`--stop-model` と `--start-again` を `ModelGate` に渡す処理。
- `terminal/strata_control/engine_update.py:301-356` — 停止許可、更新中のモデル確認、モデル停止処理。
- `terminal/strata_control/engine_update.py:220-262,369-425` — 保存済みモデルの再起動、失敗時の後始末、更新後の結果・終了コード。
- `terminal/strata_cli/update_cmd.py:307-312,367-386` — 人間向けエラーの stderr 出力、JSON 出力、更新結果の終了コード伝達。
