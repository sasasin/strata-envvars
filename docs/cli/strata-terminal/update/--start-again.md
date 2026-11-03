# `--start-again`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--start-again` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False` |

## 役割

更新のために停止したモデルを、更新後に保存済みの設定で自動的に再起動します。更新自体が失敗した場合も、停止済みモデルを旧 engine で再起動する対象です。再起動の対象は更新処理が停止させたモデルだけです（`strata_cli/update_cmd.py:69`、`strata_control/engine_update.py:376-405`）。

## 使い方

スクリプトでモデルを停止し、更新後に再起動する例です。

```sh
strata update --yes --stop-model --start-again
```

`--start-again` は停止の許可を兼ねません。スクリプトではモデル停止を許す `--stop-model` も指定します。`--yes` は通常の確認を省略しますが、それだけではモデルを止めません（`strata_cli/update_cmd.py:67-69`、`strata_control/engine_update.py:317-324`）。

## 値と既定値

値引数なしの `argparse` `store_true` です。指定すれば真、未指定なら偽となり、独自の型変換や値範囲検証はありません。繰り返し指定しても真のままです（`strata_cli/update_cmd.py:69`）。

## 実行時の動作

`strata update` は `_gate_for()` でフラグを `ModelGate.start_again` に渡し、engine update を `update_with_models()` 経由で実行します（`strata_cli/update_cmd.py:347-350,299-301`）。

モデルが更新処理のため停止されると、更新成功時は同じ設定での起動、更新失敗時は旧 engine での起動を試みます。`--start-again` があると再起動確認を省略して起動を選びます。モデルが停止されなかった場合、このフラグによる起動処理はありません（`strata_control/engine_update.py:376-405,412-432`）。

再起動には保存済み profile を使います。実際の起動待ち時間は profile の `engine_ready_s` に 60 秒を加えた値（最大 1800 秒）で、設定を読めない場合は 960 秒です。Cloudflare access を使う profile では起動後に tunnel の再開も試みます（`strata_control/engine_update.py:227-269`）。

## 適用条件と副作用

- スクリプトや非対話実行で稼働モデルがあると、`--stop-model` がない限り更新は停止前に拒否され、終了コード 7 になります。`--start-again` 単独ではモデルを停止しません（`strata_control/engine_update.py:308-324`）。
- 対話端末では、停止確認に同意してモデルが実際に停止した場合に再起動対象になります。`--start-again` を指定すると、再起動の質問には自動で「はい」と答える扱いです（`strata_cli/update_cmd.py:333-344`、`strata_control/engine_update.py:317-330,385-390`）。
- 更新のダウンロード中は既存モデルの serving が続き、その後 clean stop します。進行中の応答は終了します（`strata_control/engine_update.py:325-328,334-363`）。
- 起動に失敗すると profile の stop と cleanup を試し、再起動失敗を記録します。更新が成功してモデルだけ再起動できない場合は終了コード 8 です。更新自体が終了コード 6 で失敗した場合は、再起動失敗があっても 6 のままです（`strata_control/engine_update.py:262-269,412-432`）。

## 出力とエラー

通常出力では再起動開始時に `Starting <model> again...` を表示し、成功／失敗の文を続けます。再起動に失敗した場合、更新が完了していても「モデルが再起動しなかった」旨を出して終了コード 8 を返します（`strata_control/engine_update.py:397-405`、`strata_cli/update_cmd.py:303-306`）。

`--output jsonl` では、モデルの `restarting`、`restarted` または `restart-failed` イベントが個別レコードとして出力されます。`--output json` では個別イベントを出さず、最終 JSON に停止・再起動結果が含まれます（`strata_cli/update_cmd.py:98-107,303`、`strata_control/engine_update.py:397-409`）。再起動失敗時の起動理由は可能な範囲で説明文にし、例外 traceback ではなく失敗文として返します（`strata_control/engine_update.py:257-269`）。

## 根拠

- parser 定義・既定値: `strata_cli/update_cmd.py:60-69`
- `strata update` でのフラグ転送、更新呼び出し、出力・終了コード: `strata_cli/update_cmd.py:299-311,347-350`
- 停止前の同意と再起動条件: `strata_control/engine_update.py:308-363,376-405`
- 保存済み設定による起動と失敗時 cleanup: `strata_control/engine_update.py:227-269`
- 更新結果と再起動失敗の終了コード: `strata_control/engine_update.py:412-432`

調査範囲は上記 commit の checkout にある Terminal CLI と Control 実装です。別スコープの `strata components update` にも同名フラグがありますが、本書は索引で指定された `strata update` のスコープを記述しています（`strata_cli/update_cmd.py:70-79`）。
