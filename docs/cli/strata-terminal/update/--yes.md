# `--yes`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。`git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時 `True`、省略時 `False` |

## 役割

`strata update` が端末で行う確認、すなわち稼働中モデルを停止してよいか、更新後に同じ設定で起動し直すかを尋ねずに更新を進めるためのフラグです。確認を自動的に「はい」にするのではなく、質問関数そのものを無効にします（`terminal/strata_cli/update_cmd.py:400-411`）。スクリプトから更新を実行するときに使います。

同じ実装の `strata components update` にも同名のフラグがあります（`terminal/strata_cli/update_cmd.py:70-79`）。

## 使い方

```sh
# 稼働中モデルがない状態で、端末への質問を出さずに更新する
strata update --yes

# 稼働中モデルの停止も許可し、更新後に同じ設定で起動し直す
strata update --yes --stop-model --start-again
```

## 値と既定値

値や引数は取りません。`argparse` の `action="store_true"` で登録され、省略時は偽です。別名、値の検証、数値の境界はありません。同じフラグを複数回指定しても真偽値として扱われます。登録は `terminal/strata_cli/update_cmd.py:67` です。

## 実行時の動作

`--yes` は `_ask_factory` に渡され、指定があると `ModelGate` の質問関数を `None` にします（`terminal/strata_cli/update_cmd.py:402-403,414-417`）。`ModelGate` は engine または Control の更新対象があり、かつモデルが稼働している場合に、ダウンロード前の停止同意を求めます（`terminal/strata_control/updater.py:2060-2074`）。

- `--stop-model` がない場合、停止同意の質問ができないため、更新はダウンロード前に exit code 7 で中断します。コンポーネントを変更せず、モデル名と `--stop-model` / `--start-again` を使う再実行方法を表示します（`terminal/strata_control/engine_update.py:310-317`）。
- `--stop-model` がある場合、質問なしで停止に同意したものとして、モデルを稼働させたままダウンロードし、その後に停止して更新します（`terminal/strata_control/engine_update.py:318-325,327-356`）。
- 更新後、停止したモデルを再起動するかは `--start-again` だけで決まります。`--yes` だけでは質問できないため再起動せず、モデルは停止したまま、起動方法が表示されます（`terminal/strata_control/engine_update.py:369-388`）。`--start-again` があれば同じ設定で再起動します（同 `:378-399`）。

`--check` は `ModelGate` を呼ぶ前の確認モードで終了するため、`--yes` による違いはありません（`terminal/strata_cli/update_cmd.py:357-363`）。更新対象がない場合も `ModelGate` は呼ばれません（`terminal/strata_control/updater.py:2063-2065`）。

## 適用条件と副作用

`--yes` が抑止するのはモデルに関する質問だけです。署名・ハッシュ・feed の検証、取得禁止の確認はそのまま行われ、`--force` のような再試行の強制や検証の省略はしません（`terminal/strata_cli/update_cmd.py:319-320,351-356,374-386`）。稼働中モデルが Strata の管理外で起動されている場合も、停止許可にかかわらず exit code 7 になります（`terminal/strata_control/engine_update.py:302-307`）。

ダウンロード中に別のモデルが起動した場合、`--yes` と `--stop-model` があってもその新しいモデルの停止には同意していないため、更新は exit code 7 で中断します。このときダウンロード済みの内容は保持されます（`terminal/strata_control/engine_update.py:332-345`）。

`--wait` を指定して稼働中モデルが待ち時間内に停止した場合、停止同意の質問自体が発生しないため、`--stop-model` は不要です（`terminal/strata_control/updater.py:2066-2070`）。また `--output json` / `jsonl` では元から質問しないため、`--yes` の有無は質問の抑止に追加の違いをもたらしません（`terminal/strata_cli/update_cmd.py:305,402-403`）。標準入力と標準出力の両方が端末でない場合も質問しないため、`--yes` は端末環境でも同じ動作を明示する指定です（同 `:402-403`）。

## 出力とエラー

`--yes` 自体はメッセージを出しません。通常出力では、更新結果の表示後に、停止したモデルを再起動しなかった旨と起動方法が表示されます。停止同意がないままモデルが稼働している場合は、stderr に `strata: ...` 形式でモデル名と再実行方法を表示して exit code 7 を返します（`terminal/strata_cli/update_cmd.py:307-312,374-378`）。

JSON/JSONL 出力では、失敗を `ok: false` とエラーコードを含む JSON で返します（`terminal/strata_cli/update_cmd.py:307-309`）。終了コードは、成功または更新不要が `0`、使用条件エラーが `2`、署名・ハッシュ・取得禁止などの拒否が `5`、更新失敗が `6`、稼働中モデルにより未変更が `7`、停止したモデルの再起動失敗が `8`、中断が `130` です（`terminal/strata_cli/update_cmd.py:12-15`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:60-69` — `strata update` の parser と `--yes` の登録。
- `terminal/strata_cli/update_cmd.py:70-79` — `strata components update` の同名フラグ。
- `terminal/strata_cli/update_cmd.py:400-417` — `--yes` による質問関数の抑止と、停止・再起動許可の別々の伝達。
- `terminal/strata_cli/update_cmd.py:351-386` — 更新処理への進行、確認モード、失敗時の出力と終了コード。
- `terminal/strata_control/updater.py:2060-2074` — ダウンロード前の待機・停止同意の判定。
- `terminal/strata_control/engine_update.py:300-325,327-356` — 稼働中モデルの停止同意、更新中の新規モデル、停止処理。
- `terminal/strata_control/engine_update.py:369-425` — 停止モデルの再起動条件と exit code 8 への変換。
- `terminal/strata_cli/cli.py:2210-2212` — `strata update` を `update_cmd.run` へ渡す dispatch。
