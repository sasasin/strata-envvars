# `--force`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False`。 |

## 役割

通常は前回の test start に失敗した候補や、初回起動時に自動 rollback された候補を保留します。このフラグを付けると、保留中の feed 候補をもう一度試せます。更新対象エンジンを必ず入れ替える指定ではなく、feed の判定で再試行可能な候補があるときに限って意味があります。

## 使い方

```sh
strata components update --force
```

## 値と既定値

`argparse` の `store_true` で定義されているため、値の指定は不要です。省略時は無効です。無効な値を受け取る形式ではなく、たとえば `--force yes` の `yes` はこのオプションの値としては消費されず、別引数として parser に拒否されます（`terminal/strata_cli/update_cmd.py:47-56`）。

## 実行時の動作

- `strata components update` 用 parser は共通オプション群を登録し、実行時にその値を `updater.Context.force` に渡します（`terminal/strata_cli/update_cmd.py:47-56`, `terminal/strata_cli/update_cmd.py:70-79`, `terminal/strata_cli/update_cmd.py:314-321`）。
- feed の候補が通常 `available` でも、同じ version・manifest の test start 失敗記録が有効な間は `failed-before` として保留されます。`--force` がある場合はこの保留判定を通過し、更新処理へ進みます（`terminal/strata_control/updater.py:720-730`, `terminal/strata_control/updater.py:1484-1514`）。別の Control が残した特定の古い runtime host 起因の失敗や、1日より古い失敗記録は通常判定でも保留解除されます（`terminal/strata_control/updater.py:720-746`）。
- メモリ不足のためモデルを読み込まずに候補を確認し、その候補の最初の実起動が失敗して自動 rollback された場合も、候補は `failed_unproven` に記録されます。後の update では通常 `failed-before` となりますが、強制時は既にインストール済みの候補へ切り替え、`unproven` として再記録します。次の実起動でモデルを起動できなければ rollback が再度行われ得ます（`terminal/strata_control/updater.py:707-719`, `terminal/strata_control/updater.py:1517-1534`, `terminal/strata_control/updater.py:1812-1833`）。
- 強制は test start の省略を意味しません。新しい package は署名・ファイル完全性・hardware 適合性を検証され、ステージ上のエンジンを test start してから切り替えます（`terminal/strata_control/updater.py:830-845`, `terminal/strata_control/updater.py:1538-1566`）。保留解除によって処理対象となる候補が生じるため、ダウンロードやローカル engine の切り替えが起きることがあります。以前のエンジンは保持されます（`terminal/strata_control/updater.py:1496-1514`, `terminal/strata_control/updater.py:1615-1624`）。
- `--check` と併用した場合は force を反映した feed 判定を表示しますが、engine 更新は行いません（`terminal/strata_cli/update_cmd.py:357-363`, `terminal/strata_control/updater.py:767-778`）。`--no-engine` を指定すると engine 更新工程自体が無効になり、このフラグによる engine 再試行もありません（`terminal/strata_cli/update_cmd.py:65-79`, `terminal/strata_cli/update_cmd.py:366-368`）。

## 適用条件と副作用

このオプションは feed ベースの update の再試行判定に作用します。通常の更新候補がなく、保留中の候補もない場合は更新を強制しません。また、feed が現在のインストールより古い場合の downgrade、署名や package 検証の失敗、対象 PC に合わない package、稼働中モデルとの競合を回避する機能ではありません。これらはそれぞれ version 判定、stage 時の検証、make guard、更新前の model check で扱われます（`terminal/strata_control/updater.py:670-730`, `terminal/strata_control/updater.py:830-845`, `terminal/strata_control/updater.py:1484-1508`, `terminal/strata_control/updater.py:2044-2074`）。

モデルがロード中の場合、このフラグだけでモデルを停止しません。通常の対話確認、`--stop-model`、`--wait` などの model gate の制御に従います（`terminal/strata_cli/update_cmd.py:47-56`, `terminal/strata_cli/update_cmd.py:400-415`; `terminal/strata_control/engine_update.py:300-317`）。

## 出力とエラー

再試行後の成功は通常の update 結果として表示されます。再度 test start に失敗した場合は更新前の engine が維持され、失敗記録と履歴が保存されます。`TestStartFailed` は終了コード 6 で、human 出力ではエラーを stderr に、`--output json` / `jsonl` ではエラーオブジェクトを stdout に出します（`terminal/strata_control/updater.py:86-132`, `terminal/strata_control/updater.py:1557-1566`, `terminal/strata_cli/update_cmd.py:304-312`, `terminal/strata_cli/update_cmd.py:374-378`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における `--force` の宣言と既定値。
- `terminal/strata_cli/update_cmd.py:70-79`, `terminal/strata_cli/cli.py:160-161` — `strata components update` の parser 登録。
- `terminal/strata_cli/update_cmd.py:314-321`, `terminal/strata_cli/update_cmd.py:357-373` — parser 値から `Context`、check / update の各経路への受け渡し。
- `terminal/strata_control/updater.py:670-730`, `terminal/strata_control/updater.py:1484-1514` — 保留候補の判定と force による再試行分岐。
- `terminal/strata_control/updater.py:1538-1566`, `terminal/strata_control/updater.py:1582-1624` — test start の失敗記録、成功時の切り替えと履歴保存。
- `terminal/strata_control/updater.py:1812-1833` — 未検証候補の初回実起動失敗時に行う自動 rollback と記録。
- `terminal/strata_control/updater.py:2044-2074`, `terminal/strata_control/engine_update.py:300-317` — 対象候補の事前判定と稼働中モデルの gate。
