# `strata monitor`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/client.py`、`strata_cli/monitor.py` |
| 起動経路 | `strata_cli/cli.py` がサブコマンドを登録し、`monitor_commands.run()` に委譲 |

## 役割

稼働中の Strata サーバーから読み取り専用のテレメトリーを取得し、ターミナル上で表示します。通常は自動更新する対話型 monitor を開き、`--once` を付けると一度だけ取得して人間向けまたは JSON で出力します。サーバーの起動・停止はこのコマンドでは行いません。

## 使い方

```sh
# ローカルの Strata サーバーを対話画面で監視
strata monitor --url http://127.0.0.1:8095

# 保存済みの接続先を使う
strata monitor --connection work

# スクリプト向けに一度だけ JSON を取得
strata monitor --connection work --once --json

# poll 間隔と最近の request 表示数を指定
strata monitor --url http://127.0.0.1:8095 --interval 2 --requests 20
```

`--url` や `--connection` を省略した場合、環境変数で選択された接続先、またはローカルの既定接続先が使われます。`strata launch` が起動したサーバーを認識できる環境では、その稼働情報も接続先の既定値に使われます。接続設定の保存・表示は [`strata connection`](../connection/README.md)、接続の有効値の確認は [`strata config show`](../config/README.md) を参照してください。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 対話型 monitor | `strata monitor --url http://127.0.0.1:8095` | 端末で定期的にテレメトリーを取得し、Overview、Serving、Requests、Engine、Hardware、Logs を表示します。Terminal CLI の通常構成では、Connect ビューも加わります。 |
| 一回表示 | `strata monitor --url http://127.0.0.1:8095 --once` | 一つの snapshot を取得し、Overview を表示して終了します。TUI は起動しません。 |
| 一回 JSON | `strata monitor --url http://127.0.0.1:8095 --once --json` | versioned JSON envelope を stdout に出して終了します。JSON 出力には `--once` が必要です。 |

## 主な動作と副作用

- parser は `--url`、保存済み接続名 `--connection`、credential を格納した環境変数名 `--credential-env`、request timeout `--timeout` を接続設定として受け付けます。表示設定は `--theme`、`--color`、`--glyphs`、更新間隔 `--interval`、最近の request 数 `--requests` です。出力関連は `--once`、`--output human|json`、`--json`、`--quiet` です。値の既定値と制約は `monitor_commands.py` の parser 定義に従います。
- 接続先は明示的な URL または接続名を優先し、接続設定・環境変数から解決されます。接続 credential の値はコマンド引数や URL に埋めず、指定された環境変数から読み込みます。直接 URL を指定しない場合、通常の Terminal CLI は `strata launch` の稼働情報から URL と key を補うことがあります。
- HTTP クライアントは `/v1/telemetry` を優先し、404 の場合に `/metrics` と `/v1/status`、または status のみへ fallback します。HTTP 応答は JSON として検証され、redirect は追わず、本文は 2 MiB に制限されます。リモート接続では HTTPS が必要です。HTTP は localhost / loopback、またはローカル SSH tunnel 用に許可されます。
- 対話モードは開始直後から poll し、既定間隔は 1 秒です。取得失敗時には直前の snapshot を stale 表示し、認証・互換性エラー以外は間隔を制限した再試行をします。`Space` は表示を freeze しますが、収集は続きます。`r` で再取得、`q` で monitor を離れます。
- 通常の monitor は読み取り専用で、`q` は detach してサーバーを稼働させたままにします。`strata launch` の monitor は同じ基礎画面に Connect ビューを加え、終了時にサーバーを維持するか停止するか尋ねます。この差は [`strata launch`](../launch/README.md) の概要にも記載しています。
- `--once --quiet` は人間向け出力を抑止します。JSON モードでは machine-readable な結果を抑止しません。

## 注意点

- `--once` を付けない対話モードは stdout が TTY でない環境では終了コード 2 で拒否されます。JSON monitor 出力も `--once` なしでは拒否されます。非対話環境では `--once --json` を使ってください。
- `--interval` は 0.5〜30 秒、`--requests` は 1〜50 の範囲に制限され、範囲外ではエラーになります。`--timeout` は接続時に 0 より大きく 30 秒以下である必要があります。
- `--url` は server root を指定します。URL 内のユーザー情報、path、query、fragment は受け付けず、非 loopback の HTTP も拒否されます。reverse proxy の prefix が必要なら保存済み connection の prefix を設定します。
- 認証失敗、到達不能、redirect、JSON 形式違反、互換性のない schema はエラーになります。対話モードでは認証・schema エラー後の自動再試行は止まり、その他の接続エラーは再試行されます。一回表示では取得できなければエラー終了します。
- 通常構成の monitor は Textual の UI 依存を使います。portable monitor bundle のように launch UI が含まれない構成では Connect ビューを持たない monitor となり、UI 依存が不足すると「monitor component missing」エラー（終了コード 5）になります。portable bundle の配布・構成差は本 checkout のソースと packaging 定義を確認した範囲に限り、個別 Release artifact の実物はこの調査では検証していません。

## 関連文書

- [CLI 文書索引](../../README.md) — `strata-terminal` のコマンドとオプション文書一覧
- [`strata launch` コマンド概要](../launch/README.md) — 起動、monitor、稼働中サーバーの管理
- [Terminal CLI 利用ガイド](../../../TERMINAL.md) — 接続、認証、キー操作、エラー時の挙動
- [Telemetry フィールド一覧](../../../TERMINAL_TELEMETRY_FIELDS.md) — snapshot の項目・単位・欠損値の扱い

## 根拠

- `strata_cli/cli.py:40-45,490-493,2165` — `strata` の subcommand parser と monitor の登録・dispatch。
- `strata_cli/monitor_commands.py:20-25,49-60` — 接続 option、monitor option、値の既定値。
- `strata_cli/monitor_commands.py:36-46,167-230` — launch server の検出、値の検証、接続解決、one-shot / JSON / TUI の分岐。
- `strata_cli/monitor_commands.py:231-244` — client・connection・値・OS error と割り込みの出力・終了コード。
- `strata_cli/client.py:45-76,84-125,134-152` — URL / prefix / timeout の validation、HTTPS 条件、HTTP 応答制限、snapshot endpoint と fallback。
- `strata_cli/monitor.py:89-109,152-165,258-320,335-343` — TUI のキー操作、起動時 polling、失敗時の状態・再試行、freeze と detach。
- `strata_cli/nav.py:1-23`、`strata_cli/launch/monitor_ext.py:1-9,39-45,57-76` — 通常 monitor の6ビューと `strata launch` 由来の Connect ビュー・終了時確認の差。
- `strata_cli/launch/app.py:415-435` — `strata launch` が monitor を開き、終了後に維持・停止の結果を扱う箇所。
- `docs/TERMINAL.md:30-44,236-244` — 接続先と credential の扱い、読み取り専用アクセス、画面操作・再試行の利用者向け説明。
