# `strata logs`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/logs.py`、`strata_cli/client.py` |

## 役割

Strata serving server の read-only telemetry から、直近に保持されたリクエスト遷移を表示します。通常は最後の snapshot を一度取得して終了し、`--follow` を付けると新しい遷移を polling し続けます。ここで表示するのは redacted request activity であり、engine のファイルログ全体を読むコマンドではありません。

## 基本的な使い方

```sh
# ローカルで起動中の Strata server の直近の遷移を表示
strata logs

# 明示した server から JSON snapshot を取得
strata logs --url http://127.0.0.1:8080 --output json

# 保存済み connection を使い、遷移を JSON Lines で追跡
strata logs --connection work --follow --output jsonl
```

`--url`、`--connection`、`--credential-env`、`--timeout` の接続設定は、`strata status` / `strata monitor` と共通です。両方の接続先指定を同時には使えません。接続方法の詳細は [`strata connection`](../connection/README.md) と [`strata monitor`](../monitor/README.md) を参照してください。

## 実行モードと出力

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| one-shot の人向け表示 | `strata logs` | snapshot を一度取得し、保持イベントを時刻・sequence・request ID・event・任意の outcome として表示します。 |
| one-shot の機械可読表示 | `strata logs --output json` または `--json` | `schema_version`、`source`、instance ID、最終 sequence、保持件数、events を含む JSON を一行で出力します。 |
| 継続表示 | `strata logs --follow` | 最初の snapshot のイベントを出した後、既定 2 秒間隔で polling し、新しい遷移を出力します。人向け出力は Ctrl+C で detach できます。 |
| 継続 JSON Lines | `strata logs --follow --output jsonl` | activity、retention gap、instance change をそれぞれ JSON Lines として出力します。 |

one-shot の保持イベントは最大 32 件です。follow 中に取得間隔のあいだで保持範囲から外れた sequence は gap として示され、serving instance が変わると sequence の再開始を通知します。`--json` は one-shot 専用で、follow と `jsonl` の併用は拒否されます。follow には `human` または `jsonl` を指定してください。

## 主な動作と副作用

- 接続先は明示した `--url` / `--connection`、環境変数 `STRATA_URL` / `STRATA_CONNECTION`、既定接続の順で解決されます。明示 URL と saved connection の同時指定はエラーです。接続 credential は指定された環境変数から読み、HTTP Bearer header に設定されます。
- server の `/v1/telemetry` を優先し、未提供（HTTP 404）の場合は `/metrics` と `/v1/status` の既存経路に fallback します。受信データは client 側で固定形・最大 32 件に sanitize されます。
- 接続先への read-only HTTP request と、`--follow` 時の周期的な再取得を行います。コマンドはローカルへのログ保存や server の状態変更を行いません。
- `--source` の既定値 `runtime` は利用できます。parser は `harness` も受理しますが、現行処理は shared local harness activity を未提供として終了コード 5 で拒否し、`--source runtime` の使用を案内します。

## 注意点

- remote server には HTTPS が必要です。HTTP は localhost（`localhost`、`127.0.0.1`、`::1`）または local SSH tunnel の接続に限られます。
- server が activity を提供しない場合、または serving instance ID がない場合（follow 時）は失敗します。継続中の接続失敗は最大 3 回目でエラーになり、2 回までは retry し、復旧時には stderr に通知します。
- `--interval` は 0.5〜30 秒で、範囲外は終了コード 2 です。`--timeout` は接続 request の timeout で、既定 3 秒、上限 30 秒です。
- JSON 出力、通信失敗、認証失敗などのエラー応答は `--output json` / `jsonl` または `--json` では JSON error object、それ以外では stderr の `strata:` メッセージになります。Ctrl+C は follow 時は正常 detach（0）、それ以外の割り込みは 130 です。

## 関連するオプション文書

このコマンドの全オプションは [`docs/cli/README.md`](../../README.md) の `strata-terminal` 節に一覧します。接続先・credential・timeout は [`--url`](--url.md)、[`--connection`](--connection.md)、[`--credential-env`](--credential-env.md)、[`--timeout`](--timeout.md)、出力動作は [`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)、追跡動作は [`--follow`](--follow.md)、[`--interval`](--interval.md)、取得元は [`--source`](--source.md) を参照してください。コマンド固有のヘルプは [`--help`](--help.md)（短縮形 `-h`）です。

## 根拠

- Strata `strata_cli/cli.py:488-493` — Terminal CLI parser への logs parser 登録。
- Strata `strata_cli/monitor_commands.py:20-26,63-72` — 共通接続 options と `logs` の parser、既定値・候補値。
- Strata `strata_cli/monitor_commands.py:167-202,231-244` — interval/output/source validation、接続解決、ログ処理の呼び出し、失敗処理。
- Strata `strata_cli/logs.py:25-57,101-151` — snapshot 一回取得、保持イベント表示、follow polling、欠落・instance change・接続再試行。
- Strata `strata_cli/client.py:45-63,84-152,244-268` — server URL 制約、read-only endpoint と fallback、timeout、activity sanitize。
- Strata `strata_cli/connections.py:273-303` — URL・saved connection・環境変数の優先順位と credential 参照。
- Strata `docs/TERMINAL_QUICKSTART.md:23-30` — remote 接続と credential 環境変数の利用者向け説明。
