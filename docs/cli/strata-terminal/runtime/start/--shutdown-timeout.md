# `strata runtime start --shutdown-timeout`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--shutdown-timeout` |
| 別名 | なし |
| 値 | 秒数（有限の浮動小数点数、`0`〜`300`） |

## 役割

`strata runtime start` が起動するバックグラウンドサーバーの停止時に、実行中の推論リクエストを完了まで待つ上限時間を指定する。上限に達すると、そのサーバーが受け付けた未完了リクエストをキャンセルして終了処理へ進む。サーバーは端末終了後も動作し、`runtime stop` または `--die-with-pid` で指定したプロセスの終了などで停止するため、この値は起動待ち時間ではなく、後の停止処理に使われる（`terminal/strata_control/runtime.py:668-670`）。

## 使い方

```sh
# 保存済みの profile を起動し、停止時の推論 drain を最大45秒待つ
strata runtime start --profile four-gpu --shutdown-timeout 45
```

## 値と既定値

- 値は秒単位で、既定値は `30` 秒。parser は `float` として読み取る（`terminal/strata_cli/cli.py:231-240`）。
- `0`〜`300` 秒を含む範囲で指定する。`strata_control.management._seconds` は有限値かつ範囲内であることを検証するため、負数、300を超える値、`NaN`、無限大は受理されない（`terminal/strata_control/management.py:118-122, 207-213`）。
- 値を省略すると既定値 `30` が管理層に渡る。明示した値はそのまま秒数として渡され、profile の保存値を書き換える処理はこの経路にはない（`terminal/strata_cli/cli.py:1415-1426`; `terminal/strata_control/management.py:228-238`）。

## 実行時の動作

CLI は値を `management.runtime_action(..., shutdown_timeout=...)` に渡す。通常起動では管理層が検証後に `runtime.start` を呼び、owner host の起動引数へ `--shutdown-timeout` と値を転送する。owner host はその値を server 子プロセスにも渡す（`terminal/strata_cli/cli.py:1415-1426`; `terminal/strata_control/management.py:207-238`; `terminal/strata_control/runtime.py:658-679, 704-719, 1040-1053`）。

停止時、server は新しい推論リクエストの受付を閉じ、すでに受け付けたリクエストの完了を指定秒数だけ待つ。残件があればその server が所有するリクエストをキャンセルし、さらに最大5秒 drain を待ってから HTTP server、engine、vision、hub の終了処理を行う（`terminal/serve/server.py:4423-4447, 9777-9802`）。値 `0` は待ち時間なしで期限判定に進むため、残件があればキャンセル対象になる。

## 適用条件と副作用

- `--plan` を付けた場合は起動せず、計画に `shutdown_timeout` を含めて `would_start: false` を返す（`terminal/strata_control/management.py:215-227`）。
- 実起動では owner host が停止を要求する際、POSIX では server に `SIGTERM` を送り、Windows では owner pipe を閉じる。host は server の終了を指定時間 + 8秒待ち、終了しない場合はプロセスツリーを kill して終了を回収する（`terminal/strata_control/runtime.py:612-613, 1197-1218`）。
- `--shutdown-timeout` を持つ server は drain 期限超過時に終了コード `8` を返し、キャンセル件数を lifecycle の `stopped` 通知に含める（`terminal/serve/server.py:9787-9792, 9817-9822`）。
- これは `strata runtime start` の設定であり、同名の `strata serve` オプションや legacy server 入口の既定動作とはスコープが異なる。server 側 parser では同名引数の既定値が `None` で、管理 runtime 経路が明示的に値を渡す（`terminal/serve/server.py:9177-9178`; `terminal/strata_control/runtime.py:1051-1053`）。

## 出力とエラー

- 範囲外または有限でない値は管理層で `shutdown timeout must be finite seconds in 0..300` として拒否される。管理 RPC は `ProfileError` の終了コード（指定がなければ `2`）を応答へ含める（`terminal/strata_control/management.py:118-122, 594-620`）。
- server の drain 期限を超えても停止処理を続ける。未完了の所有リクエストがキャンセルされ、server 終了コードは `8` となる（`terminal/serve/server.py:9787-9792, 9817-9822`）。
- CLI の通常出力は `human`、`--output json` またはその alias `--json` では JSON 形式。対象オプション自体は出力形式を変えない（`terminal/strata_cli/cli.py:239-240, 543-547, 1401-1443`）。

## 根拠

- `terminal/strata_cli/cli.py:231-240` — `runtime start` parser、必須 profile、対象 option の型と既定値。
- `terminal/strata_cli/cli.py:227-233`; `terminal/strata_control/runtime.py:668-670` — `runtime start` がバックグラウンドサービスを起動し、端末終了後も動作すること。
- `terminal/strata_cli/cli.py:1415-1426` — CLI から runtime 管理処理へ値を渡す箇所。
- `terminal/strata_control/management.py:118-122, 207-238` — 有限値・範囲の検証、plan と実起動の分岐、runtime への転送。
- `terminal/strata_control/runtime.py:658-679, 704-719` — 起動引数を作り owner host を起動する処理。
- `terminal/strata_control/runtime.py:1040-1074, 1197-1224` — server 子プロセスへの転送と、停止時の signal / pipe、kill fallback。
- `terminal/serve/server.py:9177-9178, 9264-9265, 9777-9822` — server parser と検証、停止時の drain・cancel・終了コード。
- `terminal/serve/server.py:4423-4447` — drain が新規受付を止め、期限後に所有リクエストをキャンセルする処理。
