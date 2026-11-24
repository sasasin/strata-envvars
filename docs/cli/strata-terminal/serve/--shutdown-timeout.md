# `strata serve --shutdown-timeout`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--shutdown-timeout` |
| 別名 | なし |
| 値 | 秒数（浮動小数点数、0〜300） |

## 役割

`strata serve` が停止要求を受けたとき、受付中の推論リクエストを完了させるために待つ上限時間を指定します。上限までに終わらない場合は、この Service が受け付けたリクエストをキャンセルしてから engine などを閉じます。対象になる停止要求には Ctrl+C のほか、server が停止ハンドラーを設定する通常の終了要求が含まれます（`terminal/serve/server.py:9244-9258`）。

## 使い方

```sh
# 停止時に推論リクエストを最大 45 秒待つ
strata serve --profile ./profile.json --shutdown-timeout 45
```

## 値と既定値

Terminal CLI は `float` として値を読み取り、既定値は `30` 秒です。0〜300 の範囲外は `--shutdown-timeout must be in 0..300 seconds` で拒否されます（`terminal/strata_cli/cli.py:82-83,954-969`）。数値に変換できない引数も parser の型変換で受理されません。

この CLI は解析した値を `--shutdown-timeout <値>` として server の起動引数に必ず加えます（`terminal/strata_cli/cli.py:833-836`）。一方、`terminal/serve/server.py` の内部 parser の既定値は `None` です（`terminal/serve/server.py:9177-9178`）。したがって、`strata serve` を通す場合の既定 30 秒と、内部 server をこのオプションなしで直接起動する場合の挙動は異なります。profile や run config からこの値を読む処理はなく、`strata serve` の CLI 値が server に渡されます（`terminal/strata_cli/cli.py:821-840`）。

## 実行時の動作

停止時に値が指定されていると、server はまず推論受付を閉じ、その時点の処理中リクエスト数を取得します。その後、指定秒数まで完了を待ちます。期限内に完了すれば通常の終了処理へ進みます（`terminal/serve/server.py:4423-4439,9777-9788`）。

期限までに残った場合は、この Service が所有する実行中リクエストにキャンセルを通知し、さらに最大 5 秒 drain を待ってから HTTP server、engine、vision、hub の終了処理に進みます。タイムアウト時には「drain deadline expired」のメッセージを出し、最終終了コードは `8` になります。キャンセル対象はこの Service が受け付けたリクエストであり、無関係な GPU 作業を一括停止する処理ではありません（`terminal/serve/server.py:4441-4447,9787-9805,9817-9822`）。

`--plan` を併用した場合は有効な server 引数を含む起動計画を表示して終了し、server を起動しないため、停止時の drain は発生しません（`terminal/strata_cli/cli.py:821-865,979-980`）。

## 適用条件と副作用

- 停止時に処理中リクエストがなければ待ち時間は発生しません。値が `0` の場合も受付を閉じてから待機判定を行いますが、待機上限は直ちに到達します（`terminal/serve/server.py:4430-4439,9779-9792`）。
- drain 中は新しい推論リクエストを受け付けず、該当 API は `503` と `server_draining` を返します（`terminal/serve/server.py:7775-7785`）。
- 期限超過では進行中の推論リクエストがキャンセルされます。続く engine 等の close 処理は別途実行されます（`terminal/serve/server.py:9787-9805`）。
- `--output jsonl` では `draining` と `stopped` の lifecycle event に、待機期限、残数、キャンセル数、終了コードが含まれます（`terminal/strata_cli/cli.py:882-887,978-982`）。quiet モードでは通常の人向け出力を抑えますが、期限超過時は stderr に通知します（`terminal/strata_cli/cli.py:939-950`）。

## 出力とエラー

範囲外の値は通常出力ではエラー経路で終了コード `2` となり、JSONL 出力では `failed` event とエラー内容が出力されます（`terminal/strata_cli/cli.py:868-874,954-969`）。停止時に期限超過すると server は stdout にキャンセル通知を出し、終了コード `8` を返します。quiet モードでは stdout が抑止され、CLI が stderr に `shutdown drain deadline expired; owned requests were cancelled` と出力します（`terminal/serve/server.py:9787-9792,9817-9822`; `terminal/strata_cli/cli.py:942-950`）。

## 根拠

- `terminal/strata_cli/cli.py:82-83` — `strata serve` parser の型、既定値、説明。
- `terminal/strata_cli/cli.py:821-840` — CLI 値を server argv に転送する箇所。
- `terminal/strata_cli/cli.py:954-980` — 範囲検証と plan 時の分岐。
- `terminal/serve/server.py:9177-9178,9264-9265` — 内部 server parser の既定値と独自の範囲検証。
- `terminal/serve/server.py:4423-4447,9777-9822` — 受付停止、drain、キャンセル、close、終了コード。
- `terminal/serve/server.py:7775-7785` — drain 中の新規推論要求への応答。
- `terminal/strata_cli/cli.py:868-874,939-950` — CLI エラー出力と quiet 時の期限超過通知。
