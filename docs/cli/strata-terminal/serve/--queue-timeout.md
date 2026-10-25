# `strata serve --queue-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--queue-timeout` |
| 別名 | なし |
| 値 | 秒数（有限の数値、0.1〜600、両端を含む） |

## 役割

推論要求が engine の最初の turn を得るまで待てる上限時間を設定します。待機要求に期限を付けるには、待機要求数を制限する `--max-queue` も必要です。期限を省略すると無効（期限なし）です。

## 使い方

```sh
strata serve --profile ./run-config.json --max-queue 32 --queue-timeout 15
```

`--profile` は `strata serve` で必須です。例では pending call を最大32件に制限し、それらが最初の engine turn を待つ時間を15秒にしています。プロファイルに値を保存して使う方法は `strata profile set <profile> max_queue=32 queue_timeout=15` です。

## 値と既定値

- Terminal CLI parser は `float` として読み取ります。範囲外、`nan`、`inf` は受理されません。明示値がなければ `None`（期限なし）です。
- 値を省略した場合、保存プロファイルの `queue_timeout`、次に run config の `queue_timeout` があればそれを使います。明示した CLI 値は両方より優先します。値は起動時に有効設定へ解決され、launch plan の `effective` と `origin` に反映されます。
- CLI の parser は通常の `argparse` の値格納を使うため、同じ指定を複数回書いた場合は最後に解析された値が残ります。特別な複数値処理はありません。
- 値の指定漏れや数値として解析できない値は CLI parser のエラーです。有限性と範囲は CLI 側と server 側で検査されます。

## 実行時の動作

1. `strata serve` は CLI 値、保存プロファイル、run config の順に設定を解決します（上位の値を優先）。run config 由来の値は設定ファイルのまま server に渡し、それ以外の有効値は server argv に `--queue-timeout <秒数>` として渡します。
2. server は CLI 値があればそれを、なければ run config の `queue_timeout` を選び、有限数かつ `0.1 <= 値 <= 600` であることを確認します。`bool` は数値の派生型ですが明示的に不許可です。
3. `queue_timeout` が有効なのに `max_queue` が未設定なら、server は `--queue-timeout requires --max-queue / max_queue to bound pending calls` で起動を拒否します。Terminal CLI の有効設定検査でも同じ組み合わせを拒否します。`--max-queue 0` は有効な値ですが、待機枠を設けず overload を受け付けない設定です。
4. 要求が inference 実行へ入ると単調時計による deadline を設定します。シリアル時は FIFO の turn を待つ間、並列 engine 時は制御線や slot を待つ間に期限を確認します。要求を engine に送信して最初の turn が始まると deadline を消去するため、生成全体や最初の token の待ち時間を制限する timeout ではありません。
5. timeout の回数は server の `queue_timeouts` カウンタに加算されます。telemetry の `work.queue_timeout_s` と `work.queue_timeouts` に設定値・累積回数が載り、monitor 表示にも使われます。

`max_queue` は同時 admission 上限にも関与します。上限は engine の有効 slot 数に `max_queue` を加えた数で、これを超える要求は待ち続けず `admission_full` として HTTP 429 になります。`--queue-timeout` はこの admission 上限とは別に、受け入れ済み要求が turn を待てる時間を制限します。

## 適用条件と副作用

- 有効になるのは `strata serve` が起動する server の推論要求です。期限が来ると、その要求は engine に送信されず、待機状態から終了します。engine に送信済みの処理をキャンセルしたり、server 全体を停止したりする指定ではありません。
- timeout は OpenAI chat completions、OpenAI responses、Anthropic messages 等の推論経路で処理されます。通常の非 stream 要求では HTTP 429 と `queue_wait_timeout` が返り、`Retry-After: 1` が付きます。stream 要求では HTTP headers の送信後に API 形式の error event が送られ、stream が終了します。
- 保存プロファイルや run config に設定する場合も同じ有限範囲と `max_queue` 必須条件が適用されます。profile assignment の数値変換・検証は調査対象ソースの `strata_control/profiles.py` にあります（行番号は根拠を参照）。
- CLI の起動時エラーは human 出力では stderr に `strata: ...` と表示され、通常 exit code 2 です。JSON モードではエラー object、JSONL モードでは `failed` event を stdout に出します。server parser の `ap.error` も usage とエラーを stderr に出し、argparse の標準エラー終了になります。

## 根拠

- `strata_cli/cli.py:46-56` — `serve` parser、`--queue-timeout` の `float` 値指定。
- `strata_cli/cli.py:745-779` — CLI / saved profile / run config の優先順位と `max_queue` 必須条件。
- `strata_cli/cli.py:782-805` — run config 由来でない有効値を server argv へ転送。
- `strata_cli/cli.py:829-835, 915-939` — 値の範囲検証と CLI エラー出力経路。
- `serve/server.py:8165-8168, 8259-8268` — server parser、config fallback、有限値・範囲・`max_queue` の検証。
- `serve/server.py:3962-3965, 3981-3996` — admission limit（engine slots + `max_queue`）と超過時カウンタ。
- `serve/server.py:5171-5174, 5201-5218` — request deadline の設定とシリアル FIFO 待機中の期限処理。
- `serve/server.py:1690-1717, 1809-1817, 1876-1880, 1935-1945` — control / slot 待機中の確認、および engine turn 送信時に期限を解除する処理。
- `serve/server.py:5570-5590, 8444-8446` — timeout 回数の加算と Service への設定。
- `serve/server.py:6487-6501, 6857-6862, 7192-7199, 7264-7266, 7300-7304, 7425-7429` — telemetry と非 stream / stream の timeout 応答。
- `strata_control/profiles.py:66-95, 98-117` — 保存プロファイルの `queue_timeout` 値変換と検証。

調査範囲は上記 commit の Terminal CLI と `serve/server.py` のソースです。同一 revision の `--help` や Release 配布物との照合は行っていません。実際の GPU/backend ごとの待ち時間差や server 外部の HTTP client の再試行動作は確認していません。
