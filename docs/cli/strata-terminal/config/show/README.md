# `strata config show`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `## main...origin/main`（未コミット変更なし）でした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/connections.py` |

## 役割

監視クライアントが使う接続設定を解決し、各値の出所と、資格情報を参照する環境変数に値が設定されているかを表示します。サーバーへの接続や資格情報そのものの表示は行いません。読み取り専用の接続先を確認した後、`strata status`、`strata monitor`、`strata logs` などへ同じ設定を渡す前の確認に使えます。

このページはコマンド全体の概要です。個別オプションの詳細は [`--connection`](--connection.md)、[`--credential-env`](--credential-env.md)、[`--effective`](--effective.md)、[`--json`](--json.md)、[`--output`](--output.md)、[`--quiet`](--quiet.md)、[`--timeout`](--timeout.md)、[`--url`](--url.md) を参照してください。

## 基本的な使い方

```sh
# ローカル既定値と設定元を表示
strata config show

# 保存済みの読み取り専用接続を解決し、JSON で表示
strata config show --connection work --output json

# 接続 URL と資格情報の環境変数名をその場で指定
strata config show --url https://inference.example --credential-env STRATA_TELEMETRY_KEY
```

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 人向け出力 | `strata config show` | 解決した設定を整形 JSON で stdout に表示します。 |
| 機械向け出力 | `strata config show --output json` または `--json` | `schema_version`、`ok`、`effective` を含む JSON オブジェクトを stdout に出します。 |
| 出力抑制 | `strata config show --quiet` | 人向け stdout を抑制します。JSON 出力と併用した場合は `--quiet` は抑制を行いません。 |

`--effective` は parser にありますが、実装は指定の有無を参照せず常に解決済み設定を表示します。したがって現行実装では既定動作と同じです。

## 主な動作と設定の選択

- `--url` と `--connection` は同時に指定できません。どちらかを明示すると `STRATA_CONNECTION` より優先されます。`--connection NAME` を指定した場合は保存済み接続を読み込み、URL・proxy prefix・資格情報環境変数名をそこから選びます。
- どちらも指定せず、`STRATA_CONNECTION` が設定されていればその保存済み接続を使います。それ以外は `STRATA_URL`、未設定時の `http://127.0.0.1:8095` の順に URL を選びます。保存接続が選ばれない場合、proxy prefix は空、資格情報環境変数名は `STRATA_API_KEY` です。`--credential-env` があれば資格情報参照だけを上書きします。
- `--timeout` は秒単位の数値で、省略時は 3 秒です。明示値は 0 より大きく 30 以下でなければなりません。
- 出力には正規化した URL / prefix、資格情報環境変数名、資格情報の有無を示す boolean、timeout、選択した接続名・revision、設定元が含まれます。環境変数の秘密値は表示しません。
- このコマンドは設定ファイルを作成・変更せず、通信もしません。保存済み接続を選ぶ場合は設定ディレクトリと接続ファイルを読み取り、owner-only などの検査を行います。

## 注意点

URL は HTTP(S) の server root 形式で、埋め込み資格情報・path・query・fragment は受け付けません。remote host は HTTPS が必要で、HTTP を使えるのは localhost / loopback です。保存接続ファイルを使う場合、そのファイルは存在し、対応 schema と安全性検査を通る必要があります。設定ディレクトリは `STRATA_CONNECTION_DIR`（絶対パスが必要）、Windows の `%APPDATA%` 配下、または POSIX の `${XDG_CONFIG_HOME:-~/.config}/strata/connections` から選択されます。POSIX では接続ディレクトリと接続ファイルが owner-only であることを検査します。Windows ACL の適合性はこの revision の利用者向け資料で未確定とされています。

通常の解決エラーは人向けの場合 stderr に `strata: ...` として出力されます。JSON モードでは `ok: false` と `error` を含む JSON を stdout に出します。接続設定の値エラーは通常終了コード 2、保存接続の不在・不正・安全性エラーは 5 です。JSON 指定の不正値も argparse の型・選択肢検証で拒否されます。

## 関連文書

- [CLI 索引の `strata config show` 節](../../../README.md)
- [接続先の保存・編集と config show の利用例](../../../../TERMINAL.md)
- [接続環境変数 `STRATA_CONNECTION`](../../../../STRATA_CONNECTION.md)
- [`strata status`](../../status/README.md)、[`strata monitor`](../../monitor/README.md)、[`strata logs`](../../logs/README.md)

## 根拠

- Strata `strata_cli/cli.py:488-493,2165` — monitor 系 parser の登録と共通実行先への dispatch。
- Strata `strata_cli/monitor_commands.py:20-25,96-103` — 接続関連引数、`config show` parser、既定値と alias。
- Strata `strata_cli/monitor_commands.py:124-139,167-175,231-240` — 出力形式、設定解決、quiet、エラー表示と終了コード。
- Strata `strata_cli/connections.py:41-44,66-90,97-114,128-146` — 既定 URL、資格情報名・保存データ・owner-only 検証。
- Strata `strata_cli/connections.py:273-303` — URL / 接続 / 環境変数の優先順位、既定 timeout、出力する出所情報。
- Strata `strata_cli/client.py:45-64` — URL の形式と remote HTTPS 条件。
- Strata `docs/TERMINAL.md:30-44` — 接続設定の利用例と config show の利用者向け説明。
