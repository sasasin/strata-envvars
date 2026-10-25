# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

`--once` で取得する一回分の human-readable スナップショットを stdout に表示しないためのフラグです。監視リクエストやスナップショット取得そのものは抑止しません。

## 使い方

```sh
strata monitor --once --quiet
```

この例は既定の接続先から一回分のスナップショットを取得し、human 出力を表示せずに終了します。サーバーの指定方法は `--url`、`--connection`、環境設定などで別途選びます。

## 値と既定値

- `argparse` の `store_true` で宣言され、未指定時は `False`、指定時は `True` です。値や alias はありません。
- `--quiet` 自体に追加の値 validation はありません。引数解析に失敗した場合は `argparse` が usage とエラーを出し、終了コード 2 で終了します。
- monitor の実行時には `--interval` が 0.5〜30 秒、`--requests` が 1〜50 の範囲で検証されます。範囲外なら `--quiet` の有無にかかわらず終了コード 2 です。

## 実行時の動作

- `--output` の既定値は `human` です。human 形式で `--once` を指定すると、CLI はサーバーから snapshot を取得した後、`--quiet` が偽の場合に限って overview を幅 80・高さ 24 で描画して stdout に出します。`--quiet` が真なら描画・表示を飛ばし、終了コード 0 を返します。
- `--quiet` は `--once` がない対話モニターでは抑制効果を持ちません。対話経路では TUI を起動し、`quiet` は UI 起動に渡されません。非 TTY での対話起動は `--quiet` では許可されず、`--once` が必要です。
- `--json` または `--output json` は machine 出力として扱われます。`--quiet` を同時に指定しても JSON を抑止せず、snapshot JSON を stdout に出します。JSON 出力は `--once` が必須で、対話モニターで使うと接続前にエラーになります。
- `--quiet` はコマンド名 `monitor` にだけ属する parser option です。同じ名前の `status`、`logs` 等のフラグは別スコープで、抑制する内容も異なります。

## 適用条件と副作用

- human 出力を抑止するのは `--once` の成功時だけです。出力を捨てても snapshot の HTTP 読み取りは行われるため、ネットワーク接続・認証・サーバー応答などの失敗は発生し得ます。
- snapshot はまず `/v1/telemetry` を要求し、404 の場合は `/metrics`、さらに必要な場合は `/v1/status` へ fallback します。これらは read-only telemetry endpoint としてクライアントで許可された経路です。
- `--quiet` 自体によるファイル書き込み、サーバー状態変更、GPU 操作はありません。

## 出力とエラー

- `--once --quiet` の human 成功経路では snapshot を取得してから表示を省略し、終了コード 0 です。`--once --quiet --json` または `--output json` では JSON snapshot が stdout に出ます。
- `--quiet` はエラーを隠しません。human モードの失敗は `strata: ...` を stderr に出し、エラーコードを返します。JSON モードの失敗は `{"schema_version":1,"ok":false,"error":...}` を stdout に出します。
- `--quiet` を付けても `--once` なしで JSON を要求した場合や、対話モードを非 TTY で起動した場合はコード 2 で拒否されます。接続・認証・telemetry 取得に関するエラーは client の `ClientError` 経路で報告されます。

## 根拠

- `strata_cli/monitor_commands.py:49-60` — `monitor` parser の option 宣言。`--quiet` は `store_true`、help は one-shot human 出力の抑制と説明。
- `strata_cli/monitor_commands.py:167-170,189-213` — human と machine 判定、interval/requests validation、JSON/TTY 条件、snapshot 取得後の human 出力抑制。
- `strata_cli/monitor_commands.py:124-129,231-240` — エラー出力先と終了コード処理。
- `strata_cli/cli.py:488-493,2153-2165` — Terminal CLI への monitor parser 登録と実行委譲。
- `strata_cli/client.py:101-132,134-152` — read-only endpoint の制限、HTTP 読み取り、snapshot endpoint と fallback。
- 索引 [`docs/cli/README.md`](../../README.md) はこのオプションを `strata monitor` 配下に掲載しています。
