# `--port`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--port` |
| 別名 | なし |
| 値 | 整数 `N`、0〜65535 |

## 役割

`strata serve` が前景で起動する HTTP 推論 API の listen port を指定します。指定値は run config や保存 profile の port を上書きします。`0` を指定すると OS が空いている port を割り当てます。

## 使い方

```sh
strata serve --profile /path/to/strata-model.json --port 8096
```

`--profile`（alias `--config`）には run config のパスまたは解決可能な profile を指定します。実サーバーを起動せず有効設定を確認する場合は `--plan` を加えます。

```sh
strata serve --profile /path/to/strata-model.json --port 0 --plan
```

## 値と既定値

- 値は `argparse` の `int` で変換されます。未指定なら、保存 profile の `port`、run config の `port`、既定値 `8095` の順で採用されます。CLI の `--port` を指定した場合はそれが最優先です。port 専用の環境変数はこの解決処理にありません。
- 有効範囲は両端を含む `0..65535` です。`0` は範囲内の特別な値で、固定 port ではなく OS に割当を委ねます。
- 整数に変換できない値は parser が拒否します。範囲外の整数は `strata: --port must be in 0..65535` と stderr に出して終了コード 2 になります。profile/run config 由来の port も serving override 検証で整数・同範囲を要求します。

## 実行時の動作

- `_effective` が CLI 指定、saved profile override、run config、既定値 `8095` の優先順で有効値を決め、その値を serving override として検証します。起動計画の `server_argv` に `--port <値>` として含まれます。`--plan` はこの計画を出力して終了し、listen socket は作りません。
- 通常起動では実サーバーがその値で `ThreadingHTTPServer` を bind します。port `0` のときは bind 後に実際の port を取得し、`ready:` の URL と `--ready-file` の `bound_port` / `api_url` に反映します。
- 既定 host は loopback `127.0.0.1` です。到達範囲は `--host` および設定の host にも依存します。`--port` 自体は HTTP API の認証や host の公開範囲を変更しません。

## 適用条件と副作用

- 範囲検証は計画・起動の前に行われます。起動経路では、モデル読み込みに入る前に指定 host/port で listen 可能かを一度 bind/unbind して確認します。その後の実 listen は別の bind なので、確認後に他プロセスが port を取得した場合も起動に失敗し得ます。
- 実起動では TCP listen socket を開き、前景 server の終了まで API を受け付けます。`--plan` では socket を開きません。

## 出力とエラー

- 有効値は `--plan` の結果の `effective.port` と `server_argv` で確認できます。
- bind の事前確認に失敗すると server parser の usage と `listen_problem` の診断が表示され、通常は終了コード 2 です。port 使用中の場合は別 port 指定を案内します。OS のエラーが address unavailable や permission error の場合は原因に応じて host/port または OS 側の制約を案内します。
- `--port 0` では指定した `0` ではなく、OS が割り当てた実 port が ready URL と ready record に出ます。

## 根拠

- `strata_cli/cli.py:46-53` — `serve` parser、必須 profile、`--port` の整数変換。
- `strata_cli/cli.py:745-779` — CLI / saved profile / run config / default (`8095`) の優先順と serving 値の検証。
- `strata_cli/cli.py:782-826` — 有効 port を server argv と計画に反映。
- `strata_cli/cli.py:915-942` — `0..65535` の CLI 範囲検証、plan と実起動の分岐。
- `strata_control/profiles.py:98-105` — profile/run config port の整数・範囲検証。
- `serve/server.py:144-160` — bind 失敗理由の診断。
- `serve/server.py:8143-8156`, `8288-8308` — server 側の既定値、host の決定、listen 前の bind 確認。
- `serve/server.py:7718-7724`, `8615-8623`, `8645-8654` — 実 listen、割当 port の取得、ready 出力・record。
- `docs/cli/README.md` — `strata-terminal` の `strata serve` 配下に本 option を掲載。

調査は上記 commit の checkout のソースに基づきます。別 OS 上での bind 失敗文言の実例や各 OS の port 割当動作は実行確認していません。
