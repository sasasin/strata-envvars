# `strata tune auto --boot-timeout`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--boot-timeout` |
| 別名 | なし |
| 値 | 秒数。`float` として解析される |

## 役割

自動チューニングで候補設定を測定する worker が起動し、health check に応答するまで待つ上限時間を指定する。既定値は15分で、チューニング中に起動する各 worker に適用される。

## 使い方

```sh
strata tune auto qwen/IQ3_S --boot-timeout 1200
```

この例では worker ごとの起動待ちを最大20分にする。`target` はインストール済みモデル、保存 profile、または run configuration を指定できる。

## 値と既定値

parser は `type=float`、既定値 `900.0` で値を解析する。明示的な正数範囲の検証はない。数値でない値は argparse の型変換で拒否される。複数回指定した場合の処理は parser の通常の単一値引数に委ねられる。

## 実行時の動作

`strata tune auto` はこの値を `WorkerSession` の `boot_timeout_s` に渡す。セッションは各測定用に設定ファイルと worker プロセスを用意し、起動後に loopback の `/health` を確認する。指定時間内に HTTP 200 の応答がなければ、その測定を `TIMEOUT` として扱う。従って、この値は全チューニング処理や個々の推論リクエストの時間制限ではなく、worker の起動待ち時間である。

`--plan` を指定した場合は計画を表示して終了し、測定 worker を起動しないため、この待ち時間は使われない。なお、同じ `--boot-timeout` は `strata presets recheck` にも別 scope で存在する。また `strata tune run` の同名オプションは `--mode api` の候補 worker に使われ、既定値は600秒である。これらは本オプション文書の対象外。

## 適用条件と副作用

値は、`--plan` ではなく実測を行う `strata tune auto` の worker 起動時に適用される。起動待ち中は worker プロセスを実行し、loopback の health endpoint をポーリングする。タイムアウトまたは起動失敗時、セッションは起動中の worker を終了し、終了待ちが60秒で完了しなければ kill を試みる。負数や0も parser 上は受理されるが、期限が直ちに過ぎるため通常の起動待ちにはならない。

## 出力とエラー

起動期限を過ぎても worker が ready にならない場合、セッションは `TIMEOUT` と理由 `the engine was not ready within … s` を付けた起動失敗を返す。自動チューナーはこれを測定結果に記録し、最初の基準設定の測定が失敗した場合は「現在の設定を測定できなかった」という失敗結果にする。人間向け進捗は stderr、最終結果は stdout に出力され、`--output json` では最終結果を JSON で出す。基準測定の失敗時、コマンドは終了コード6を返す。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `auto` parser と `--boot-timeout` の float 型・既定値。
- `terminal/strata_cli/tune_commands.py:349-353` — 計画モードは worker 起動前に戻る。
- `terminal/strata_cli/tune_commands.py:371-376` — 値を `WorkerSession` に渡す箇所。
- `terminal/strata_control/tune_session.py:484-497` — session が起動待ち秒数を保持する箇所。
- `terminal/strata_control/tune_session.py:545-594` — worker 起動、health check、期限判定と `TIMEOUT` の生成。
- `terminal/strata_control/tune_session.py:595-610` — 起動失敗時のログ保持と worker の終了処理。
- `terminal/strata_control/autotune.py:338-354` — `StartFailed` を測定結果に記録する処理。
- `terminal/strata_control/autotune.py:415-427` — 基準測定の失敗を失敗結果にする処理。
- `terminal/strata_cli/tune_commands.py:358-369, 388-425` — 人間向け進捗の stderr 出力、最終出力と終了コード。
- `terminal/strata_cli/cli.py:489-515, 1722-1724` — `tune auto` が `tune` のサブコマンドとして登録・実行される箇所。
- `terminal/strata_cli/cli.py:471-474` — 別 scope の `strata tune run` にある同名オプション（既定値600秒、API request timeout とは別）。
