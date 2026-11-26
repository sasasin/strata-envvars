# `strata update --wait`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。`float` として解析される。 |

## 役割

エンジンが稼働中のとき、停止するまで最大指定秒数だけ待ってから更新を続けます。待機中にエンジンを停止する機能ではありません。指定時間内に停止しなければ、更新を拒否して終了します。

## 使い方

```sh
# 最大5分、稼働中のエンジンが停止するのを待って更新する
strata update --wait 300
```

## 値と既定値

- `SECONDS` は `float` で解析されます。既定値は parser 上 `None` で、実行コンテキストへ渡す際に `0.0` になります（`terminal/strata_cli/update_cmd.py:51-52, 323-325`）。
- 数値形式以外は parser の型変換で受理されません。Strata 独自の正数・有限値・最大値の検証はこの宣言にはありません。
- 0 以下は待機しません。エンジンが稼働中なら、その時点で busy として拒否されます。エンジンが稼働していなければ待機は発生しません（`terminal/strata_control/updater.py:383-390`）。

## 実行時の動作

更新処理は署名付き feed を読み、対象のエンジンまたは Control に更新予定がある場合、ダウンロード前に `--wait` の秒数を使って稼働状態を確認します（`terminal/strata_control/updater.py:2082-2096, 2109-2122`）。稼働中なら最大3秒間隔で状態を再確認し、待機イベントを出します。待機処理は更新前の確認に加え、更新後に最初の staging・test start・切替を行う直前にも呼ばれます（`terminal/strata_control/updater.py:383-403, 1529, 1542, 1590, 1947`）。各呼び出しで期限を作るため、この秒数は更新全体を通した単一の総時間上限ではありません。

稼働状態の確認対象は、Strata owner runtime の管理対象インスタンスと共有 activity lease を保持しているサーバーです（`terminal/strata_control/updater.py:354-380`）。`--wait` はそれらへ停止要求を送りません。指定時間内に停止した場合は後続の更新へ進みます。待機中に稼働状態が解消しない場合は `Busy` になります（`terminal/strata_control/updater.py:383-394`）。

このオプションは `--stop-model` による停止同意の代わりにはなりません。事前確認で `--wait` が期限切れになると busy エラーとなり、同意ゲートには進みません。待機なしで稼働モデルがある場合は、対話端末なら停止への同意を尋ね、スクリプトや機械出力では停止同意がないため拒否します（`terminal/strata_control/updater.py:2088-2096`; `terminal/strata_control/engine_update.py:285-325`）。

`--check` は feed の確認だけで戻り、更新処理を呼ばないため、併記した `--wait` は待機に使われません（`terminal/strata_cli/update_cmd.py:361-367, 370-372`）。`--wait` は `update_cmd._common()` で登録され、`strata components update` にも同じ定義が適用されます（`terminal/strata_cli/update_cmd.py:47-52, 59-72`）。

## 適用条件と副作用

- 待つ対象のエンジンが稼働している場合に限り、時間待ちと再確認が発生します。更新対象がなければ `_model_check` は待機せず戻ります（`terminal/strata_control/updater.py:2085-2089`）。
- 待機は稼働中モデルを停止せず、稼働が続けば更新を進めません。更新予定のエンジンまたは Control がある場合、稼働中モデルの停止同意を得る経路は `--wait` が指定されていると先に待機するため、期限切れ時には変更処理へ進みません（`terminal/strata_control/updater.py:2082-2096`）。
- 待機検出は `serving_now()` を呼びます。この関数は停止済み owner host の stale 記録を回収できる場合にクリアします（`terminal/strata_control/updater.py:354-365`）。
- このオプションの秒数に上限を設ける処理は確認できません。更新全体の feed 読み込みやダウンロード時間を制限する値でもありません。

## 出力とエラー

- 待機中は human 出力では `An engine is serving; waiting for it to stop before updating.` を表示します。`--output jsonl` では `event: waiting` と稼働対象を含む JSONL イベントを出力します。`--output json` では中間イベントを出力しません（`terminal/strata_control/updater.py:391-393`; `terminal/strata_cli/update_cmd.py:117-139`）。
- 制限時間後も稼働中なら、対象名を含む busy メッセージを stderr に出して exit 7 になります。機械出力では同じエラーを `ok: false` の JSON として stdout に出し、終了コード 7 を返します（`terminal/strata_control/updater.py:72-83, 389-390`; `terminal/strata_cli/update_cmd.py:311-316, 378-382`）。
- 数値に変換できない値は argparse の引数解析で拒否されます。option の宣言は `terminal/strata_cli/update_cmd.py:51-52`、CLI parser の入口は `terminal/strata_cli/cli.py:62-66, 160-161` です。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-72` — 共通 parser 登録と `strata update` / `strata components update` の option scope。
- `terminal/strata_cli/update_cmd.py:307-325, 361-390` — 値のコンテキストへの受け渡し、`--check` の早期終了、更新呼び出し、エラー出力と終了コード。
- `terminal/strata_control/updater.py:354-403` — 稼働状態の検出、待機期限・ポーリング・busy 判定、更新直前の idle gate。
- `terminal/strata_control/updater.py:2082-2122` — 更新予定がある場合の事前待機と、更新処理の順序。
- `terminal/strata_control/engine_update.py:285-325` — 稼働モデルがある場合の停止同意ゲート。
