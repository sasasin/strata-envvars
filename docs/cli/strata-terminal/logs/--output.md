# `strata logs --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--output` |
| 別名 | なし（`--json` は独立した alias option） |
| 値 | `human`、`json`、`jsonl` |

## 役割

`strata logs` が読み取った、サーバーに保持されている redacted request activity の表示形式を選びます。ファイルへの保存先を指定するオプションではありません。値は `human`（人間向け表示）、`json`（機械可読 JSON）、`jsonl`（追跡時のイベントごとの JSON Lines）です。parser の選択肢と既定値は `strata_cli/monitor_commands.py:63-72`、各形式による出力は `strata_cli/logs.py:101-124,129-151` にあります。

## 使い方

```sh
strata logs --output json
strata logs --follow --output jsonl
```

`strata logs` の connection 関連オプション（`--url`、`--connection`、`--credential-env`、`--timeout`）と `--output` は同じコマンド parser のスコープです（`strata_cli/monitor_commands.py:20-26,63-72`）。

## 値と既定値

- 省略時は `human`。
- `argparse` の `choices` により `human`、`json`、`jsonl` 以外は parser が拒否します。値なしや不正値は通常の argparse usage error（終了コード 2）になります（`strata_cli/monitor_commands.py:70`）。
- `json` は `--follow` なしの一回取得専用です。`jsonl` は `--follow` と組み合わせる必要があります（`strata_cli/monitor_commands.py:71`、`strata_cli/monitor_commands.py:179-186`）。
- `--json` は `--output json` の alias として説明されていますが、`--follow` と同時指定、または `--output jsonl` との同時指定は拒否されます（`strata_cli/monitor_commands.py:71`、`strata_cli/monitor_commands.py:179-182`）。

## 実行時の動作

処理の入口で `output != "human"` を machine output として扱います（`strata_cli/logs.py:101-105`）。`--output json` の一回取得では、activity を `events` 配列に含む一つの JSON object（`schema_version`、`ok`、`source`、`instance_id`、`last_seq`、`retained`、`events`）を stdout に出します（`strata_cli/logs.py:110-116`）。

`--output jsonl` は `--follow` が必須です。初回 snapshot のイベントと、その後の poll で得た activity、sequence gap、serving instance 切替をそれぞれ JSON object として一行ずつ stdout に出力し、各行は flush されます（`strata_cli/logs.py:14-23,125-151`）。`human` は一回取得なら redacted の説明と activity 表示、追跡時なら進捗表示および人間向け event 表示を行います（`strata_cli/logs.py:17-23,116-123,127-131`）。

これは読み取り専用の endpoint snapshot を使います。client は activity event の末尾最大32件だけを採用し、sequence、時刻、request ID、event/outcome を検証して固定形に絞ります。そのため、このオプションで本文や tool content を出力することはありません（`strata_cli/client.py:244-268`）。

## 適用条件と副作用

- `--follow` を使うと `--interval` 秒ごとに snapshot を poll し、Ctrl+C まで継続します。interval は `0.5`〜`30` 秒で、既定は `2` 秒です（`strata_cli/monitor_commands.py:67-72,176-178`、`strata_cli/logs.py:133-137`）。
- `--output json` と `--follow` は併用できず、`--follow` と `--output jsonl` は併用必須です。違反時は option の組み合わせエラーを出して終了コード 2 になります（`strata_cli/monitor_commands.py:179-186`）。
- 非 human 形式では `quiet` が有効にならないよう設定されます。つまり `--quiet` は JSON/JSONL のデータ出力を抑止しません（`strata_cli/monitor_commands.py:167-169`）。
- `--source` の既定値は `runtime` です。現行実装は `--source harness` を終了コード 5 で拒否するため、`--output` の選択によらず runtime activity のみが利用可能です（`strata_cli/monitor_commands.py:66,187-188`）。
- ファイル生成、書き込み、サーバー状態変更はこの表示処理から行いません。通信は read-only telemetry endpoint を使います（`strata_cli/client.py:101-107`、`strata_cli/monitor_commands.py:64`）。

## 出力とエラー

- machine output のエラーは stdout に `schema_version`、`ok: false`、`error` を持つ JSON object、人間向けエラーは stderr に `strata: ...` を出します（`strata_cli/monitor_commands.py:124-129`）。`--output json` / `jsonl` ではトップレベル dispatcher も machine error 形式を選びます（`strata_cli/cli.py:2184-2188`）。
- request activity がサーバーで利用できない場合、終了コード 5 の `ClientError` になります（`strata_cli/logs.py:105-108`）。追跡開始時に serving instance ID がない場合も終了コード 5 です（`strata_cli/logs.py:125-126`）。
- 接続失敗は `ClientError` の既定終了コード 3 で扱われます。follow 中は最大3回の連続失敗まで再試行し、最初の切断と復旧を human の場合 stderr に通知します。3回目で終了コード 3 のエラーになります（`strata_cli/client.py:38-40,124-125`、`strata_cli/logs.py:133-149`）。
- `jsonl` follow 中の event record は stdout に逐次出力されます。後で接続が失敗した場合、先に出力済みの行は残り、その後エラー object が出力され得ます（`strata_cli/logs.py:129-151`、`strata_cli/cli.py:2184-2188`）。

## 根拠

- parser、値、既定値、説明: `strata_cli/monitor_commands.py:20-26,63-72`
- option の組み合わせ validation、source 適用条件、endpoint 解決と呼び出し: `strata_cli/monitor_commands.py:167-202`
- 表示形式、JSON/JSONL record、poll と retry: `strata_cli/logs.py:14-23,101-151`
- activity の bounded sanitization: `strata_cli/client.py:244-268`
- client transport と error code: `strata_cli/client.py:38-40,101-152`
- CLI 共通 error 出力: `strata_cli/cli.py:2165-2193`
