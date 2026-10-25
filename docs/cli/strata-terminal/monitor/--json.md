# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--once` で取得する1回分のモニター snapshot を、JSON の成功・失敗 envelope として出力します。対話モニターには使えず、`--once` を伴わない場合はエラーになります。

## 使い方

```sh
strata monitor --once --json
strata monitor --url https://strata.example --once --json
```

2例目はリモートサーバーを指定する場合です。リモート接続には HTTPS が必要です。接続先の指定方法や認証情報は `--url`、`--connection`、`--credential-env` の設定に従います。

## 値と既定値

値は取りません。parser 上の既定値は `False` です。`--json` 自体に `--once` は自動付与されません。`--output` の既定値は `human` ですが、実行時には `--json` フラグまたは `--output json` のいずれかで machine 出力と判定されます。そのため `--once --json` は JSON 出力になり、`--once --output json` も同じ出力形式になります。`--json` と `--output json` の併用も可能です。

`--json` または `--output json` を `--once` なしで指定すると、実行時検証で拒否されます。parser 自体には値域 validation はありません。

## 実行時の動作

machine 出力モードでは、接続先から1回 snapshot を取得し、標準出力へ次の形式で出力します。

```json
{"schema_version":1,"ok":true,"snapshot":{}}
```

`ensure_ascii=False`、`allow_nan=False` で JSON 化されます。`--quiet` は human 表示を抑制する設定で、machine 出力時には抑制フラグとして扱われません。接続設定は `--url` / `--connection`、環境変数 `STRATA_URL` / `STRATA_CONNECTION`、既定 URL の順など `connections.resolve` の規則で解決され、timeout の既定値は3秒です。`--json` は接続先や認証の選択を変更しません。

snapshot はまず `/v1/telemetry` を読み、schema version 1 を要求します。この endpoint が404の場合に限り `/metrics`、さらに404なら `/v1/status` へ fallback し、旧形式を正規化します。取得は読み取り専用の HTTP GET です。

## 適用条件と副作用

この指定は `strata monitor` の1回取得経路に適用されます。通信を行い snapshot を標準出力に書きますが、モニターの対話 TUI は起動しません。非ローカル接続先は HTTPS、またはローカル SSH tunnel が必要です。接続先はサーバールートとして解釈され、パス・query・fragment を含む URL は受理されません。

## 出力とエラー

成功時は終了コード0で JSON envelope を標準出力へ出します。接続失敗など、machine モードで捕捉される失敗も標準出力に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` の形式で出ます。`--json` なしの人間向けエラーは `strata: ...` を標準エラーへ出します。

確認できる主な失敗条件は次のとおりです。

- `--once` なし: `JSON monitor output requires --once; interactive monitor uses a terminal`、終了コード2。
- `--interval` が0.5未満または30超、または `--requests` が1〜50の範囲外: 終了コード2。これらは `--json` に直接関係する値ではありませんが、monitor の実行前検証です。
- URL/接続設定の不正: `ConnectionError` の終了コード（通常2、保存情報の不整合などは5）。
- 認証・権限エラー: HTTP 401/403 は終了コード4。
- 接続不可、HTTP エラー、応答形式不正: `ClientError`。既定コード3、互換しない telemetry schema は5。

HTTP 応答の Content-Type が JSON でない、応答が2 MiBを超える、JSON が壊れている、JSON のトップレベルが object でない場合も失敗します。HTTP redirect は追跡せず、リダイレクト先の server root を使うよう案内します。

## 根拠

- parser と型・既定値: `strata_cli/monitor_commands.py:49-60`。
- machine 判定、範囲検証、`--once` 制約、terminal 判定: `strata_cli/monitor_commands.py:167-194`。
- 接続解決・snapshot 取得・成功 JSON・human 出力: `strata_cli/monitor_commands.py:195-213`。
- 失敗 envelope と例外・終了コード: `strata_cli/monitor_commands.py:124-129`, `strata_cli/monitor_commands.py:231-244`。
- URL、credential、timeout の選択と既定値: `strata_cli/connections.py:273-303`。
- server URL の検証: `strata_cli/client.py:45-63`。
- read-only HTTP GET、認証 header、response limit、HTTP 失敗: `strata_cli/client.py:101-132`。
- telemetry endpoint と404 fallback: `strata_cli/client.py:134-152`。
- コマンド parser 登録: `strata_cli/cli.py:490-493`。
