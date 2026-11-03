# `strata components update --yes`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `False`、指定時 `True` |

## 役割

更新中に Terminal から確認できる場合でも、モデル停止などの確認質問を表示しないようにします。スクリプトや自動実行から利用できます。ただし、このフラグだけでは稼働中モデルを停止する許可にはなりません。

## 使い方

```sh
strata components update --yes
```

このコマンドは更新を実行し、対象コンポーネントの取得・検証・適用を行い得ます。モデルを更新処理に停止させる場合は `--stop-model` も指定し、完了後に同じ設定で再起動する場合は `--start-again` も指定します。

## 値と既定値

- `argparse` の `store_true` フラグです。引数値は不要で、既定値は `False` です。`--yes` を複数回指定しても値は `True` のままです。`--yes=true` のような値付き指定は受理されません（`strata_cli/update_cmd.py:70-79`）。
- `strata update` にも同じ定義があります。本文書の対象は `strata components update` です（`strata_cli/update_cmd.py:59-69`）。

## 実行時の動作

- `--yes` があると `_ask_factory` は質問関数を返さず、確認を自動承認するのではなく「質問できる人はいない」状態にします。JSON/JSONL 出力時、または stdin/stdout が対話端末でない場合も同様に質問関数はありません（`strata_cli/update_cmd.py:333-344`）。
- 更新処理は `--yes` を `ModelGate` の質問可否に反映し、モデル停止の許可は別の `--stop-model` から渡します（`strata_cli/update_cmd.py:347-350`）。
- 稼働中モデルがあり `--stop-model` がない場合、更新前に停止確認が必要です。`--yes` により質問できないため、更新せず終了コード `7` になります。モデルは稼働を続けます（`strata_control/engine_update.py:307-324`）。
- `--yes --stop-model` を指定すると、停止可能なモデルはダウンロード中は稼働を続け、適用前に停止されます。再起動を望む場合は `--start-again` も必要です。これがなければ更新後も停止状態となり、起動方法が案内されます（`strata_control/engine_update.py:334-363,376-405`）。
- 更新ダウンロード中に新たに稼働したモデルは、最初の同意には含まれません。質問なしの実行では停止できず、終了コード `7` で処理が止まります。この場合ダウンロードは保持されます（`strata_control/engine_update.py:334-352`）。
- `--check` を同時に指定すると、feed の確認後に戻るため更新処理やモデル停止ゲートには進みません（`strata_cli/update_cmd.py:290-301`）。

## 適用条件と副作用

`--yes` 自体はファイル変更を行いませんが、通常の `strata components update` は署名付き feed からコンポーネントを取得して更新する処理です。`--stop-model` を併用した場合、更新前に停止可能な稼働モデルを停止します。更新失敗時にも停止済みモデルの再起動処理は行われますが、`--start-again` がなければ再起動せず、停止したままになります（`strata_cli/update_cmd.py:284-306`、`strata_control/engine_update.py:412-431`）。

このコマンドでの `--json` / `--quiet` は `strata_cli/cli.py` が共通で後付けします。`--json` は `--output json` として処理され、`--output jsonl` も machine 出力として質問を行いません。どちらの場合もモデル停止を許可するには引き続き `--stop-model` が必要です（`strata_cli/cli.py:508-515,2249-2254`、`strata_cli/update_cmd.py:333-350`）。

## 出力とエラー

- 人向け出力ではエラー文を stderr に `strata: ...` と表示し、JSON/JSONL では JSON の `ok: false` と `error` を出力します（`strata_cli/update_cmd.py:233-242,307-319`）。
- `--yes` だけで稼働中モデルに遭遇した場合や、停止できないモデルがある場合は終了コード `7` です。`--yes --stop-model` でも、他のプロセスが更新中に開始したモデルなど、停止同意の対象外のモデルがあれば同じく拒否されます（`strata_control/engine_update.py:34,307-324,334-352`）。
- 停止確認を対話的に行い、利用者が「いいえ」と答えた場合は何も変更せず終了コード `0` です（`strata_control/engine_update.py:325-330`、`strata_cli/update_cmd.py:307-311`）。
- 更新後のモデル再起動に失敗した場合は更新自体が完了していても終了コード `8` になり得ます（`strata_control/engine_update.py:376-405,426-431`）。署名・取得拒否などの全失敗コードは個別原因に依存し、ここでは `--yes` 固有の検証エラーは定義されていません。

## 根拠

- `strata_cli/update_cmd.py:70-79` — `components update` parser と `--yes` / `--stop-model` / `--start-again` の定義。
- `strata_cli/update_cmd.py:333-350` — `--yes` と machine 出力、TTY 条件による確認関数の選択、model gate への値の受け渡し。
- `strata_cli/update_cmd.py:290-306,307-319` — `--check` の早期終了、更新呼び出し、出力・例外処理。
- `strata_control/engine_update.py:307-363,376-431` — 停止同意、更新中に開始したモデルの扱い、再起動と終了コード。
- `strata_cli/cli.py:508-515,2249-2254` — `--json` / `--quiet` の後付けと `--json` から JSON 出力への切り替え。

調査日は `2026-11-03`。調査開始時の `git status --short --branch` は `## main...origin/main` で、working tree に未コミット変更はありませんでした。
