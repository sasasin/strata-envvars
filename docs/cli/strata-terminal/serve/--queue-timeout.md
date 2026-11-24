# `--queue-timeout`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--queue-timeout` |
| 別名 | なし |
| 値 | 秒数（浮動小数点数、有限値 `0.1..600`） |

## 役割

API 推論リクエストが最初のエンジン処理ターンを待つ時間に上限を設定する。キュー待ちが期限を超えると、そのリクエストを `queue_wait_timeout` として失敗させる。待ち時間の上限を設ける設定であり、エンジンが最初のプロンプトを受け取った後の生成時間は制限しない。

## 使い方

```sh
strata serve --profile ./run-config.json --max-queue 16 --queue-timeout 12.5
```

`--queue-timeout` を使う場合は `--max-queue` も指定するか、選択した run config / 保存済み profile に `max_queue` を設定する。上の例では、キュー制限を有効にしたサーバーで待ち期限を 12.5 秒にする。

## 値と既定値

- Terminal CLI とサーバーの parser は値を `float` に変換する。受理範囲は有限値 `0.1..600` 秒（両端を含む）。`nan`、無限大、範囲外は受理されない。
- 未指定時の値は `None` で、待ち期限は無効。設定ファイルの `queue_timeout` があればそれを使う。
- `strata serve` では明示した CLI 値が保存済み profile の override より優先し、次に run config、最後に既定値が使われる。設定値が出所の場合も同じ範囲検証を行う。
- `queue_timeout` が有効なのに `max_queue` が未設定なら起動前に拒否される。`max_queue=0` は設定上有効な値だが、過負荷時の追加待機を許さない。

## 実行時の動作

`strata` の Terminal CLI は有効値を `--queue-timeout <秒>` としてサーバー起動引数へ転送する。CLI 指定値は profile / run config の値より優先され、CLI から渡さない場合は設定値が使われる（`terminal/strata_cli/cli.py:783-809`, `terminal/strata_cli/cli.py:833-840`）。サーバーは CLI 値を設定ファイルの `queue_timeout` より優先し、検証後に `Service.queue_timeout_s` に格納する（`terminal/serve/server.py:9289-9298`, `terminal/serve/server.py:9498-9499`）。

サーバーはリクエストが API key ごとの同時実行上限で待つ場合に期限を設け、エンジン処理へ進む `_run` 側でも期限を設定する。したがって、API key 制限待ちとエンジン待ちは別々の待ちとして期限が適用され、両方を通るリクエストは合計で設定値の約 2 倍まで待つ場合がある。エンジン側の期限は FIFO の単一ターン待ち、または batch engine が未ロードのときのロード待ちに渡される。エンジンが最初のプロンプトを受け入れた後は、この期限によって生成を中断しない（`terminal/serve/server.py:5854-5862`, `terminal/serve/server.py:5997-6001`, `terminal/serve/server.py:6023-6044`, `terminal/serve/server.py:6063-6067`）。

`--max-queue` は別途、実効エンジンスロット数に追加する HTTP admission 上限を定める。`--queue-timeout` 自体は待機枠数を決めず、`max_queue` なしでは利用できない。admission 上限到達時は待たせず `admission_full` を返し、待機中の期限切れは `queue_wait_timeout` になる（`terminal/serve/server.py:4354-4357`, `terminal/serve/server.py:7775-7791`）。

## 適用条件と副作用

- この設定は `strata serve` が起動するサーバーインスタンスに適用され、保存済み profile や run config 自体を書き換えない。
- 待機中にクライアントが切断した場合は、期限切れ応答ではなく切断として扱われる。待機リクエストは `queued` 状態から除去され、期限切れ時は `queue_timeouts` カウンターが増える（`terminal/serve/server.py:6030-6046`, `terminal/serve/server.py:6516-6536`）。
- `/v1/telemetry` の `work.queue_timeout_s` に設定値が現れ、`work.queue_timeouts` に累計期限切れ数が記録される（`terminal/serve/server.py:7464-7472`）。

## 出力とエラー

- CLI は非有限値または範囲外の値を `--queue-timeout must be finite seconds in 0.1..600` で拒否し、`max_queue` がない場合は `--queue-timeout requires --max-queue / max_queue to bound pending calls` で拒否する（`terminal/strata_cli/cli.py:954-967`, `terminal/serve/server.py:9293-9298`）。
- 非ストリーミング推論の期限切れは HTTP 429、エラーコード `queue_wait_timeout`、`Retry-After: 1` となる（`terminal/serve/server.py:7885-7890`, `terminal/serve/server.py:8374-8376`）。
- ストリーミングでは HTTP ヘッダー送信後に期限切れとなるため、HTTP ステータスを 429 に変更せず、OpenAI Chat Completions、Anthropic Messages、Responses のそれぞれの形式でエラーイベントを送る（`terminal/serve/server.py:8274-8278`, `terminal/serve/server.py:8417-8418`, `terminal/serve/server.py:8576-8580`）。

## 根拠

- Parser と型: `terminal/strata_cli/cli.py:67-77`（`strata serve` の引数。`--profile` / `--config` も同じ command scope）、`terminal/serve/server.py:9183-9186`（サーバー parser）。
- Terminal CLI の優先順位・転送・検証: `terminal/strata_cli/cli.py:783-809`, `terminal/strata_cli/cli.py:833-840`, `terminal/strata_cli/cli.py:954-967`。
- サーバー側の設定優先順位・範囲・必須条件・格納: `terminal/serve/server.py:9289-9299`, `terminal/serve/server.py:9498-9499`。
- 待機期限の設定・適用とキュー整理: `terminal/serve/server.py:5854-5865`, `terminal/serve/server.py:5997-6001`, `terminal/serve/server.py:6023-6046`, `terminal/serve/server.py:6516-6536`。
- admission 制限と API エラー経路: `terminal/serve/server.py:4354-4357`, `terminal/serve/server.py:7775-7791`, `terminal/serve/server.py:7885-7890`, `terminal/serve/server.py:8274-8278`, `terminal/serve/server.py:8374-8376`, `terminal/serve/server.py:8576-8580`。
- テレメトリ項目: `terminal/serve/server.py:7464-7472`。
