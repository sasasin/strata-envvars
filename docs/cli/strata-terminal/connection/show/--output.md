# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection show` |
| オプション | `--output` |
| 別名 | なし（`--json` は別のフラグとして同じ JSON 出力を有効にする） |
| 値 | `human` または `json` |

## 役割

保存済み接続を表示するときの JSON 形式を選びます。`--output human` は人が読みやすい整形 JSON、`--output json` は機械処理向けのコンパクトな JSON envelope を出力します。この `show` は保存記録を読むローカル操作です。

## 使い方

```sh
strata connection show myserver --output json
```

`myserver` は表示する接続名です。`--output` は `show` のサブコマンド parser に定義されています。`--json` も利用できます。

## 値と既定値

- 受理値は `human` と `json`、省略時は `human` です。別の値は `argparse` の choices 検証で拒否されます。
- `--output` を複数回指定した場合の個別処理は実装されていません。parser は通常の `store` action を使うため、最後に指定した値が残ります。
- `--json` は `store_true` の別フラグです。`--output human --json` のように併用すると JSON モードになります。
- `--output jsonl` はこのコマンドでは受理されません。

## 実行時の動作

成功時、`show` は名前を使って保存接続をロードし、値と revision を含む payload を出力します。

- 既定の `human` は `schema_version` と `ok` を除いた `{"connection": ..., "revision": ...}` を、インデント付き JSON として出力します。人向けの文章形式ではありません。
- `json` または `--json` は `{"schema_version": 1, "ok": true, "connection": ..., "revision": ...}` をコンパクトな JSON で出力します。
- `--quiet` を併用すると human 出力は抑制されます。JSON モードでは quiet 抑制が無効です。
- 接続記録を読み込んで表示するだけで、接続設定ファイルの作成・変更やサーバーへの通信は行いません。出力データに含まれるのは接続 ID、URL、prefix、credential の環境変数名と revision で、credential の値ではありません。

## 適用条件と副作用

指定名は小文字 `a-z` で始まり、続く文字は小文字 `a-z`、数字、`_`、`-` のみ、全体で1〜64文字である必要があります。記録は `STRATA_CONNECTION_DIR`（設定時は絶対パス必須）、Windows の `%APPDATA%/Strata/connections`、または Unix 系の `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）から読みます。既存ディレクトリはディレクトリ型であり、POSIX では所有者専用である必要があります。ファイルは通常ファイルかつ4 KiB以下で、POSIX では所有者専用である必要があります。

## 出力とエラー

- 成功時の終了コードは `0` です。
- 接続名の形式不正など `ConnectionError` は既定では `stderr` に `strata: ...` を出し、エラーコードを終了コードとして返します。`--output json` または `--json` のときは stdout に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を出します。
- 保存記録がない、読めない、形式・権限・サイズが不正な場合は接続エラーになります。未保存の接続や不正な記録はコード `5`、名前形式不正は既定コード `2` です。ファイル操作の `OSError` はコード `6` で報告されます。
- `--quiet` は正常時の標準出力を抑制しますが、失敗メッセージは抑制しません。

## 根拠

- `strata_cli/monitor_commands.py:83-94` — `show` parser、位置引数 `name`、`--output` の choices・既定値、`--json` と `--quiet`。
- `strata_cli/monitor_commands.py:124-129,132-164` — JSON/人向けエラー、成功 payload の構築と出力形式。
- `strata_cli/monitor_commands.py:167-175,231-240` — machine/quiet 判定、読取処理の呼び出しとエラー処理。
- `strata_cli/connections.py:41-55,72-94` — 名前規則、保存先の決定とディレクトリ検査。
- `strata_cli/connections.py:97-114,128-146` — 記録スキーマ、ファイル検査・読み込み・検証・revision 計算。
- `strata_cli/cli.py:488-493,2119-2165,2217-2238` — monitor parser の登録、実行委譲、トップレベルの JSON/quiet 処理。
