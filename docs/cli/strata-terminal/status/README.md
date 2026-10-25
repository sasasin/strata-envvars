# `strata status`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| parser / 実行処理 | `strata_cli/monitor_commands.py`（`add_status`、`run`） |
| 通信・snapshot 正規化 | `strata_cli/client.py` |

## 役割

指定した Strata server に一度だけ接続し、読み取り専用 telemetry snapshot を取得して Overview 形式で表示するコマンドです。既定の出力は人向け表示で、`--json` または `--output json` を使うと versioned JSON object を返します。対話画面を開いたり、server を起動・停止したりするコマンドではありません。

接続先を省略した場合、CLI の接続設定を解決し、条件が合えばこの CLI の `launch` が管理する稼働中 server の情報も利用します。接続先、credential、timeout は共通接続 parser で受け付けます。個々の値や alias の説明は [`strata status` のオプション一覧](../../README.md#strata-status-status) を参照してください。

## 基本的な使い方

```sh
# ローカル server の概要を表示
strata status --url http://127.0.0.1:8080

# JSON snapshot を取得
strata status --url http://127.0.0.1:8080 --json

# 保存済み read-only connection を使う
strata status --connection work --output json

# credential を環境変数から渡し、timeout を指定
strata status --url https://inference.example --credential-env STRATA_TELEMETRY_KEY --timeout 5
```

`--url` と `--connection` は同時に指定できません。remote server は HTTPS が必要です。local server へ HTTP で接続する例外として loopback address と local SSH tunnel が許可されます。credential の値は URL や引数に埋め込まず、`--credential-env` で指定した環境変数から読み取られ、HTTP Bearer header に設定されます。

## 出力と実行時の動作

- parser の既定は `--output human` です。human 出力は取得した snapshot を固定幅 80・高さ 24 の Overview renderer に渡します。`--quiet` は human informational output を抑えます。
- `--json` は `--output json` の alias です。成功時は `schema_version: 1`、`ok: true`、`snapshot` を含む JSON object を stdout に出します。JSON mode では `--quiet` で JSON payload は抑制されません。
- client はまず `GET /v1/telemetry` を試し、HTTP 404 の場合に限って `GET /metrics` と `GET /v1/status` による旧形式 snapshot へ fallback します。`/metrics` も 404 なら `/v1/status` の status-only snapshot を使います。v1 endpoint が別 schema version を返す場合は互換性エラーです。
- URL は server root のみ受け付け、埋め込み credential、path、query、fragment を拒否します。非 loopback の HTTP は拒否します。各応答は JSON content type であることを要求し、redirect を追わず、本文を 2 MiB までに制限します。client 側で受信 telemetry を正規化・sanitize します。
- status command 自体は server を変更する HTTP endpoint を呼びません。接続不能、認証・権限エラー、不正応答などは human mode では stderr に `strata: ...`、JSON mode では `ok: false` と error object を出し、対応する非ゼロ exit code を返します。timeout の許容範囲は 0 より大きく 30 秒以下です（既定 3 秒）。

## 注意点

snapshot は取得時点の観測であり、server 内の全 subsystem を同時に確定した transaction ではありません。旧 server への fallback では telemetry の一部が unavailable/null となり得ます。取得できる field と旧 server での扱いは [Terminal telemetry field contract](../../../../../../Niko1221/Strata/docs/TERMINAL_TELEMETRY_FIELDS.md) を参照してください。

`strata status` は対話 monitor の代替となる一回の snapshot 表示です。継続的な画面更新には `strata monitor`、saved connection の登録や変更には `strata connection` を使います。利用者向けの全体説明は Strata の `docs/TERMINAL.md` と `docs/TERMINAL_QUICKSTART.md` にあります。

## 関連文書

- [CLI 索引: `strata status`](../../README.md#strata-status-status)
- [Terminal CLI の使い方と接続設定](../../../../../../Niko1221/Strata/docs/TERMINAL.md)（Strata source: `docs/TERMINAL.md:7-14,30-44,162-170,236-240`）
- [Terminal quick start](../../../../../../Niko1221/Strata/docs/TERMINAL_QUICKSTART.md)（Strata source: `docs/TERMINAL_QUICKSTART.md:7-30`）
- [Telemetry field contract](../../../../../../Niko1221/Strata/docs/TERMINAL_TELEMETRY_FIELDS.md)（Strata source: `docs/TERMINAL_TELEMETRY_FIELDS.md:1-12`）

## 根拠

- `strata_cli/cli.py:488-493` — Terminal CLI の `status` parser 登録。
- `strata_cli/monitor_commands.py:20-33` — 共通 connection parser と `status` parser、既定値・alias。
- `strata_cli/monitor_commands.py:36-46,195-213` — 起動中 launch 情報の利用、接続設定、snapshot と human/JSON 出力。
- `strata_cli/monitor_commands.py:124-129,231-244` — JSON/human error 出力と例外別 exit code。
- `strata_cli/connections.py:273-303` — 接続先・credential environment variable・timeout の解決と検証。
- `strata_cli/client.py:45-63,84-125` — server root / HTTPS 検証、timeout、Bearer header、redirect 拒否、応答サイズ制限。
- `strata_cli/client.py:134-152` — v1 telemetry 優先と 404 に限った旧形式 fallback。
- `strata_cli/client.py:361-447` — 受信 telemetry の sanitize と schema v1 snapshot 構築。
- `strata_cli/render.py:460-490` — Overview 表示内容。

調査時の Strata checkout は `git status --short --branch` で `## main...origin/main` と確認し、作業ツリーに未コミット変更はありませんでした。ビルド、実行、テストは行っていません。
