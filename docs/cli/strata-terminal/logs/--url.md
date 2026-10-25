# `strata logs --url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--url URL` |
| 別名 | なし |
| 値 | Strata サーバーの root URL。パス・query・fragment・埋め込み認証情報は不可 |

## 役割

読み取り専用の request activity を取得するサーバーを明示します。`--source runtime`（既定）で使われ、保存済み接続や環境設定による接続先選択を URL で上書きします。ログ機能はサーバーが保持する直近の redacted activity を表示し、永続ログを読むものではありません（`strata_cli/monitor_commands.py:63-72`、`strata_cli/logs.py:101-124`）。

## 使い方

```sh
strata logs --url http://127.0.0.1:8080
strata logs --url https://strata.example.com
```

後者のような loopback 以外の接続先では HTTPS が必要です。`--source harness` を指定すると URL の解決前に未対応エラーで終了するため、この option は runtime activity 用です（`strata_cli/client.py:45-63`、`strata_cli/monitor_commands.py:176-199`）。

## 値と既定値

- `--url` は `strata logs` 共通接続引数の一つで、値は `argparse` の文字列として受け取ります。parser 自体に既定 URL は設定されていません（`strata_cli/monitor_commands.py:20-26,63-66`）。
- 指定 URL は `http` または `https`、hostname 必須、埋め込み userinfo 不可です。path は空または `/` のみで、query と fragment は指定できません。非 loopback host は HTTPS に限られます。loopback として扱う hostname は `localhost`、`127.0.0.1`、`::1` です。port の書式も URL parser で検査されます（`strata_cli/client.py:45-63`）。
- `--url` 未指定時の一般的な既定 root は `http://127.0.0.1:8095` で、`STRATA_URL` があればそれが優先されます。ただし source CLI で `STRATA_URL` と `STRATA_CONNECTION` がなく、launch 情報から実行中サーバーを検出できる場合は、その URL と launch key を使います（`strata_cli/connections.py:41-45,273-302`、`strata_cli/monitor_commands.py:36-46,195-199`）。

## 実行時の動作

1. `strata logs` の parser は `--url`、`--connection`、`--credential-env`、`--timeout` を同じ接続引数群として登録します（`strata_cli/monitor_commands.py:20-26,63-72`）。
2. 通常の runtime 経路では `connections.resolve()` が URL を正規化します。明示 `--url` は `STRATA_URL` より優先し、環境変数 `STRATA_CONNECTION` による保存済み接続の選択を抑止します。明示 `--connection` も同時に指定すると「choose `--url` or `--connection`, not both」で失敗します。保存済み connection と環境変数の他の仕様は [`--connection`](--connection.md) を参照してください（`strata_cli/connections.py:273-302`）。
3. 解決した URL と credential を `Endpoint` に渡します。credential の値は URL に含めず、選択された credential environment variable から読み、存在すれば Bearer Authorization header として送ります。`Endpoint.snapshot()` は `/v1/telemetry` を先に要求し、404 のときに限り `/metrics`、続けて `/v1/status` へ fallback します（`strata_cli/monitor_commands.py:195-202`、`strata_cli/client.py:84-100,101-152`）。
4. 一回表示ではサーバーの保持 activity を出力します。`--follow` では初回 snapshot 後、`--interval` 秒ごと（既定 2 秒）に polling し、新しい transition と sequence gap を出します。URL の指定自体はファイルやサーバー設定を変更しません（`strata_cli/logs.py:101-151`）。

## 適用条件と副作用

- `--url` は `strata logs` の接続先にのみ作用します。同じ接続引数群は status、monitor、config にも使われますが、それらの option 文書とは scope が異なります（`strata_cli/monitor_commands.py:20-26,28-34,49-60,63-72,96-103`）。
- URL は read-only telemetry endpoint に対するネットワーク request の宛先になります。client は `GET` のみを許可し、許可 path は `/v1/telemetry`、`/v1/status`、`/metrics`、`/health` です。`logs` の snapshot 経路では前述の telemetry fallback path を使用します（`strata_cli/client.py:101-110,134-152`）。
- リダイレクトは追従せず、認証値も URL に埋め込めません。reverse proxy の path prefix が必要な場合は保存済み connection の `prefix` が別途使われます。`--url` 単独で path を指定することはできません（`strata_cli/client.py:45-63,79-83`、`strata_cli/connections.py:273-302`）。
- `--source harness` は runtime URL を解決する前に exit code 5 で拒否されます。現行ソースでは shared local harness activity は利用不可であり、`--source runtime` を使うよう案内します（`strata_cli/monitor_commands.py:176-188`）。

## 出力とエラー

- URL の形式不正、remote HTTP URL、`--url` と `--connection` の併用などは CLI error となり、通常は stderr に `strata: ...` を出して exit code 2 です（`strata_cli/client.py:45-63`、`strata_cli/connections.py:273-280`、`strata_cli/monitor_commands.py:124-129,231-240`）。
- サーバー接続失敗は既定 exit code 3、401/403 は認証・権限エラーとして 4、activity 非対応や不正な telemetry は 5 です。JSON/JSONL 出力モードではエラーを stdout の `{schema_version, ok: false, error: ...}` JSON にします。HTTP redirect は追従せず、最終 server root を使うようエラーになります（`strata_cli/client.py:38-42,117-131`、`strata_cli/monitor_commands.py:124-129,231-240`）。
- 成功時の human 出力は最新 32 件を redacted 表示し、activity がない場合は「No request transitions retained」と表示します。JSON 出力は `events` を含む snapshot envelope です。`--json` は one-shot 用で、`--follow` とは併用できません（`strata_cli/logs.py:110-124`、`strata_cli/monitor_commands.py:177-188`）。

## 根拠

- parser と command routing: `strata_cli/monitor_commands.py:20-26,63-72,167-202`、`strata_cli/cli.py:490-493,2119-2165`
- URL validation、endpoint request、fallback: `strata_cli/client.py:45-63,79-152`
- URL・環境・connection の優先順位と既定値: `strata_cli/connections.py:273-302`
- activity 表示と follow polling: `strata_cli/logs.py:101-151`
- 文書配置と scope: `docs/cli/README.md:1019-1033`

調査時点の checkout は `main` branch で `git status --short --branch` に未コミット変更表示はありませんでした。ビルド済み CLI の help や Release artifact は使用せず、同一 checkout の parser と実装を根拠にしています。
