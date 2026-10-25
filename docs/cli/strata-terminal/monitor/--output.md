# `strata monitor --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの状態は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--output` |
| 別名 | なし（`--json` は別のフラグで、`--once` 時の JSON 出力指定） |
| 値 | `human` または `json` |

## 役割

`--once` で取得する1回分の monitor snapshot を、人向けの概要表示または機械処理向け JSON のどちらで stdout に出すか指定します。対話式 monitor は JSON 出力に対応せず、`--output json` には `--once` が必要です。

## 使い方

```sh
# 一度だけ取得し、人向けの overview を表示（既定値）
strata monitor --once

# 一度だけ取得し、snapshot を JSON で表示
strata monitor --once --output json
```

## 値と既定値

- parser は `human` と `json` のみを受け付け、未指定時は `human` です。ほかの値は argparse の選択肢エラーになります（`strata_cli/monitor_commands.py:49-55`）。
- このオプションは値を1つ取ります。繰り返し指定した場合の parser 結果は argparse の通常動作で、最後に指定した値です。
- `--json` は `--output` の alias 表記ではありません。monitor parser 上の独立した真偽値フラグで、help は `--once` と組み合わせた JSON 指定として説明しています（`strata_cli/monitor_commands.py:52-55`）。

## 実行時の動作

- `--output json` と `--json` は `machine` 出力として扱われます。JSON の場合、monitor 実行前に snapshot を取得し、`{"schema_version":1,"ok":true,"snapshot":...}` を1行の JSON として stdout に出して終了します（`strata_cli/monitor_commands.py:167-169,203-208`）。JSON のシリアライズでは非有限数を許しません（`strata_cli/monitor_commands.py:206-207`）。
- `--output human` で `--once` を指定すると、取得した snapshot を overview のテキストとして表示します。`--quiet` が同時に指定されていればこの人向け表示は抑止されます（`strata_cli/monitor_commands.py:209-213`）。
- `--output human` で `--once` を指定しない場合は、通常の対話式 monitor が起動します。値 `human` 自体は対話画面を一回表示して終了させる指定ではありません（`strata_cli/monitor_commands.py:191-194,214-229`）。
- snapshot は server の read-only telemetry endpoint から取得されます。クライアントは `/v1/telemetry` を優先し、404 の場合に `/metrics` と `/v1/status`、または `/v1/status` 単独へ fallback します（`strata_cli/client.py:134-152`）。
- 接続先の選択は `--output` では変わりません。明示した `--url`、`--connection`、既定 URL・環境設定などから endpoint を解決して snapshot を取得します（`strata_cli/monitor_commands.py:195-207`、`strata_cli/connections.py:273-300`）。

## 適用条件と副作用

- `--output json` は `--once` がないと拒否され、対話画面は開始しません。`--output human` は TTY がない環境では対話式起動を拒否されますが、`--once` なら TTY を必要としません（`strata_cli/monitor_commands.py:191-194`）。
- このオプションによる書き込みや設定変更はありません。`strata monitor` は読み取り専用 client として定義され、snapshot の取得にはサーバーへの HTTP リクエストを行います（`strata_cli/monitor_commands.py:50`、`strata_cli/client.py:101-116,134-152`）。
- 出力に含める snapshot はクライアント側の telemetry sanitizer を通ります（`strata_cli/client.py:142-152`）。

## 出力とエラー

- JSON 成功時は stdout に schema version、成功状態、snapshot を含む JSON を出し、終了コード `0` を返します（`strata_cli/monitor_commands.py:203-208`）。human の one-shot 成功時も終了コード `0` です（同 `209-213`）。
- `--output json` に `--once` がない場合はコード `2` のエラー JSON を stdout に出します。human 出力指定で TTY がない場合は `strata: ...` 形式のエラーを stderr に出し、コード `2` を返します（`strata_cli/monitor_commands.py:124-129,191-194`）。
- `--interval` が 0.5〜30 秒の範囲外、または `--requests` が 1〜50 の範囲外の場合も、monitor 実行前にエラーとなります。machine 出力ならエラー JSON、そうでなければ stderr のテキストで、終了コードは `2` です（`strata_cli/monitor_commands.py:189-190,124-129`）。
- 接続失敗や認証エラーなど `ClientError` は上位 CLI でエラー化されます。`--output json` の場合は JSON エラー形式になり、クライアントが定義する exit code が返ります（`strata_cli/client.py:117-131`、`strata_cli/cli.py:2184-2188`）。

## 根拠

- `strata_cli/monitor_commands.py:49-60` — `monitor` parser、`--output` の値・既定値、関連フラグ。
- `strata_cli/monitor_commands.py:124-129,167-213` — machine mode、出力形式、適用条件、one-shot と対話式の分岐、基本エラー形式。
- `strata_cli/client.py:101-152` — HTTP telemetry 取得、失敗条件、snapshot endpoint の fallback。
- `strata_cli/connections.py:273-300` — 接続先と credential 環境変数の解決。
- `strata_cli/cli.py:491,2165-2188` — 共通 CLI への monitor parser 登録と例外の出力経路。

この文書は指定 commit のソースを調査したものです。別 revision の配布済み CLI や各 server/backend の実際の telemetry 内容までは確認していません。
