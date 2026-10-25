# `--once`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--once` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True` |

## 役割

対話型 TUI を起動せず、サーバーの telemetry snapshot を一度取得して表示します。端末がない環境で monitor を使う場合や、スクリプトから一回分の状態を読む場合に使えます（`strata_cli/monitor_commands.py:49-60,191-213`）。

## 使い方

```sh
strata monitor --once
strata monitor --once --json
```

`--json` または `--output json` は `--once` と併用します。監視先は `--url` または `--connection` で指定できます（例: `strata monitor --once --url http://localhost:8000`）。

## 値と既定値

`--once` は `argparse` の `store_true` で、追加値や引数を受け付けません。未指定時は対話型 monitor が選ばれます。繰り返し指定を独自に拒否する処理はなく、真偽値のまま扱われます（`strata_cli/monitor_commands.py:49-60`）。

## 実行時の動作

指定すると `Endpoint.snapshot()` を一度呼び出し、取得結果を概要ビューとして描画して終了します。TUI の `MonitorApp` / `LaunchMonitor` 起動経路には入りません（`strata_cli/monitor_commands.py:203-229`）。snapshot はまず `/v1/telemetry` を要求し、404 の場合は `/metrics`、さらに404なら `/v1/status` を使う既存サーバー互換経路へ進みます（`strata_cli/client.py:134-152`）。これは状態取得の HTTP 要求を行いますが、monitor コマンドからサーバー設定を変更する処理はありません。

`--json` と `--output json` は JSON 出力を選びますが、`--once` がなければ終了コード2で拒否されます。JSON 成功時は `schema_version: 1`、`ok: true`、`snapshot` を含む JSON を stdout に出します。人向け出力は overview の描画結果で、`--quiet` を併用すると抑制されます（`strata_cli/monitor_commands.py:53-55,168-169,191-213`）。

監視先の解決では `--url` と `--connection` の同時指定は拒否されます。明示指定がないときは、保存済み `STRATA_CONNECTION`、`STRATA_URL`、既定 URL などから解決し、起動中の `strata launch` 情報も条件付きで利用します（`strata_cli/connections.py:273-303`; `strata_cli/monitor_commands.py:36-46,195-199`）。接続設定の詳細は [`--url`](--url.md)、[`--connection`](--connection.md) を参照してください。

## 適用条件と副作用

`--once` を付けない JSON monitor は拒否されます。また、`--once` なしで stdout が TTY でない場合も拒否され、`--once` または `strata status --json` の利用を案内します（`strata_cli/monitor_commands.py:191-194`）。

`--interval` と `--requests` の値域検証は `--once` の場合にも実行されます（interval は 0.5–30 秒、requests は 1–50）。ただし one-shot 分岐ではこれらの値は snapshot 要求・描画へ渡されません。`--theme`、`--color`、`--glyphs` も TUI 起動時にだけ渡されるため、one-shot 出力には適用されません（`strata_cli/monitor_commands.py:56-60,189-190,203-229`）。

## 出力とエラー

成功時の終了コードは `0` です。JSON を要求して `--once` を省略した場合、および対話型実行に TTY がない場合は終了コード `2` です。接続・HTTP エラーは `ClientError` の終了コードで返り（既定 `3`、401/403 は `4`）、不正な telemetry schema は `5` です。JSON モードではエラー JSON を stdout、人向けでは `strata: ...` を stderr に出します（`strata_cli/monitor_commands.py:124-129,191-194,231-240`; `strata_cli/client.py:38-42,117-152`）。

## 根拠

- `strata_cli/monitor_commands.py:49-60` — monitor parser と `--once`、関連オプション。
- `strata_cli/monitor_commands.py:189-213` — 値域検査、TTY/JSON 条件、one-shot snapshot と出力。
- `strata_cli/monitor_commands.py:214-229` — `--once` 時に TUI 起動を通らないこと。
- `strata_cli/monitor_commands.py:231-244` — client error、終了コード、標準出力・標準エラーの扱い。
- `strata_cli/client.py:38-42,101-152` — HTTP 要求、snapshot fallback、client error の終了コード。
- `strata_cli/connections.py:273-303` — URL・保存接続・環境設定の解決順序。
