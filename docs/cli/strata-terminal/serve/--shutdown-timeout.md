# `--shutdown-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--shutdown-timeout` |
| 別名 | なし |
| 値 | 秒数（浮動小数点数、0〜300） |

## 役割

`strata serve` を停止するとき、受付済みの推論呼び出しが終わるまで待つ上限時間を指定します。通常の Ctrl+C や停止シグナルでは、期限内の完了を待ってから server と engine を閉じます。指定時間内に drain が完了しない場合は、期限後にこの server が所有する要求をキャンセルします（`strata_cli/cli.py:61-62`、`serve/server.py:8674-8689`）。

## 使い方

準備済み profile の設定ファイルを使って、停止時に最大 45 秒待つ例です。

```sh
strata serve --profile /path/to/run.json --shutdown-timeout 45
```

`--profile` は `--config` の別名です。`strata serve` は CLI の値を server の `--shutdown-timeout` 引数へ転送します（`strata_cli/cli.py:46-47, 794-798`）。

## 値と既定値

- 値は `float` として解析され、範囲は 0〜300 秒です。境界値 0 と 300 を含みます（`strata_cli/cli.py:61-62, 929-930`）。
- 省略時は 30 秒です。CLI parser が `default=30` を設定し、`_launch_plan` は parser が作った `cli` がある場合に値を server 引数へ追加します（`strata_cli/cli.py:61-62, 794-798`）。
- `0` は待機時間なしで期限を迎える値です。負数、300 を超える値、有限範囲外の値は拒否されます。`NaN` も範囲比較を通らず拒否されます（`strata_cli/cli.py:929-930`）。
- 数値として解析できない文字列は `argparse` の引数解析エラーになります。`strata serve` の parser は `argparse.ArgumentParser` を使用します（`strata_cli/cli.py:5, 40-41, 61`）。
- この値は serve の起動引数であり、profile や run config へ保存する処理は確認できません。CLI から server 起動引数へ渡す箇所は `strata_cli/cli.py:794-798` です。

## 実行時の動作

停止処理に入ると、server は `begin_drain()` で新しい推論呼び出しの受付を止め、現在予約されている呼び出し数を取得します。受付処理は drain 中に新たな予約を拒みます（`serve/server.py:3981-3991, 4031-4036`）。続いて `wait_for_drain()` が指定秒数を上限に予約済み呼び出しの終了を待ちます（`serve/server.py:4038-4047, 8674-8682`）。

期限時点で呼び出しが残っていれば `cancel_owned_requests()` がこの Service の active cancellation event を設定します。server はその後最大 5 秒、予約の解放を待ってから HTTP server、engine、vision、MCP hub を閉じます（`serve/server.py:4049-4055, 8682-8693`）。停止期限を超えた場合の終了コードは 8 です。期限内に終わった場合、SIGTERM 等の通常停止は 0、Ctrl+C は 130 になります（`serve/server.py:8706-8713`）。

## 適用条件と副作用

- `strata serve` は parser の既定値 30 秒を常に server の起動引数へ含めるため、この CLI から起動した server は graceful drain を有効にします（`strata_cli/cli.py:61-62, 794-798`）。一方、`python -m serve.server` の parser では同じオプションの既定値は `None` で、明示指定時だけ drain 分岐に入ります。この別入口の既定動作を `strata serve` の既定値と混同しないでください（`serve/server.py:8159-8160, 8674-8678`）。
- タイムアウトは停止時だけ使われ、通常の推論待ち時間や起動待ち時間を変えません。サーバーが停止シーケンスに入る契機は Ctrl+C および stop handler が扱うシグナルで、signal handler は slow な起動処理より前に設定されます（`serve/server.py:8219-8233, 8665-8682`）。
- `--plan` と併用した場合、値は検証され launch plan の `server_argv` に含まれますが、plan 経路は server を起動せず終了します（`strata_cli/cli.py:794-798, 929-941`）。
- 期限後のキャンセル対象は、この server が所有する active request です。無関係な GPU 作業を止める処理ではありません（`serve/server.py:4049-4055`）。

## 出力とエラー

- 範囲外の値は server 起動前に拒否されます。通常出力では stderr に `strata: --shutdown-timeout must be in 0..300 seconds` を出し、終了コード 2 を返します。`--output json` の場合は JSON error、`--output jsonl` の場合は `failed` event として出力されます（`strata_cli/cli.py:527-532, 829-835, 915-930`）。
- drain 中は server の標準出力に保留数と期限超過・キャンセル数のメッセージを出します。`--output jsonl` では stdout に `draining` event（`pending_requests`, `deadline_s`）と `stopped` event（`drained`, `cancelled_requests`, `exit_code`）を出します（`serve/server.py:8670-8687, 8706-8713`; `strata_cli/cli.py:838-863`）。
- `--quiet` の human 出力では server の標準出力を抑え、期限超過時に CLI が stderr へ `strata: shutdown drain deadline expired; owned requests were cancelled` を出します。JSONL event は quiet でも抑制されません（`strata_cli/cli.py:838-873, 900-912`）。

## 根拠

- Terminal CLI の parser、範囲検証、server 引数への転送: `strata_cli/cli.py:46-67, 782-810, 915-941`
- drain 中の新規受付停止、予約済み要求の待機、所有要求のキャンセル: `serve/server.py:3981-3991, 4031-4055, 8674-8689`
- 停止イベントと終了コード: `serve/server.py:8665-8713`; CLI の JSONL lifecycle event: `strata_cli/cli.py:838-897`
- 利用者向け説明との照合: `docs/TERMINAL.md:220-222`
