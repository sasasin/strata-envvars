# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--url URL` |
| 別名 | なし |
| 値 | HTTP または HTTPS の Strata サーバールート URL。パス、query、fragment、URL 内資格情報は不可。 |

## 役割

状態スナップショットを取得する接続先を明示します。引数なしの `strata status` は接続設定に従い、実行中の `strata launch` が検出される場合はそのアドレスを使います。別サーバーを調べる場合や、既定の接続先を明示したい場合に `--url` を指定します（`strata_cli/monitor_commands.py:20-33,195-199`）。

## 使い方

```sh
strata status --url http://127.0.0.1:8080
strata status --url https://inference.example --json
```

## 値と既定値

- `--url` は文字列引数で、省略時の parser 値は `None` です。値の指定自体は parser で必須化されていません（`strata_cli/monitor_commands.py:20-25,28-33`）。
- URL は `http://` または `https://` とホスト名を必要とし、userinfo（`user:pass@` 等）、サーバールート以外の path、query、fragment を拒否します。path は空または `/` のみです。host は小文字化され、末尾の `/` は正規化結果に含まれません（`strata_cli/client.py:45-63`）。
- 平文 HTTP は `localhost`、`127.0.0.1`、`::1` に限り受理されます。その他のホストは HTTPS が必要です。コードのエラー文は HTTPS またはローカル SSH tunnel を案内します（`strata_cli/client.py:58-63`）。
- `--url` と `--connection NAME` を同時に使うと拒否されます（`strata_cli/connections.py:273-280`）。
- URL を指定しない場合は、`--connection`、環境変数 `STRATA_CONNECTION`、環境変数 `STRATA_URL`、既定値 `http://127.0.0.1:8095` の順に接続先を解決します。明示した `--url` はこの環境設定より優先されます（`strata_cli/connections.py:273-303`）。ただし、明示 URL なしで環境変数が接続先を指定していない場合、`strata status` は実行中の `strata launch` 情報を先に調べ、その URL を解決に渡します（`strata_cli/monitor_commands.py:36-46,195-199`）。

## 実行時の動作

`--url` の値は `connections.resolve` で正規化され、HTTP client の `Endpoint` に渡されます。明示 URL の場合、保存済み接続の path prefix は使われず、prefix は空です。資格情報参照は既定で `STRATA_API_KEY` ですが、`--credential-env NAME` を併用すれば参照する環境変数を変更できます。資格情報の値は URL に加えず、client が存在する値を `Authorization: Bearer ...` header として送ります（`strata_cli/connections.py:285-303`; `strata_cli/monitor_commands.py:195-199`; `strata_cli/client.py:84-108`）。

client はまず `/v1/telemetry` を読み、未対応（HTTP 404）の場合に `/metrics` と `/v1/status`、または `/v1/status` のみを読む互換経路へ進みます。いずれも GET による読み取り専用処理です（`strata_cli/client.py:101-108,134-152`）。通常出力は Overview の人間向け表示で、`--json` または `--output json` はスナップショットを JSON で出力します（`strata_cli/monitor_commands.py:28-33,167-168,203-213`）。

## 適用条件と副作用

- `--url` は `strata status` のほか、共有 parser を使う `strata monitor`、`strata logs`、`strata config show` にも定義されています。この文書の適用スコープは索引に従い `strata status` です（`strata_cli/monitor_commands.py:20-33,49-71,96-103`）。
- URL で接続先を明示すると、`running_launch()` によるローカル launch 情報の自動検出を行いません（`strata_cli/monitor_commands.py:195-199`）。
- HTTP client は redirect を追跡せず、応答の Content-Type が JSON でない場合、本文が 2 MiB を超える場合も失敗させます（`strata_cli/client.py:17,79-82,101-123`）。
- status は一回の snapshot を読むコマンドであり、対象サーバーの設定変更や起動・停止を行う処理は確認できません（`strata_cli/monitor_commands.py:28-33,203-213`; `strata_cli/client.py:101-152`）。

## 出力とエラー

- 接続 URL の形式不正、`--url` と `--connection` の併用、または timeout の不正は接続エラーとして扱われます。`status` は `ConnectionError` を捕捉し、JSON モードでは `{"ok": false, "error": ...}` を stdout に、人間向けでは `strata: ...` を stderr に出します（終了コードは `ConnectionError` に設定された値。通常の接続設定エラーは 2）（`strata_cli/connections.py:47-50,273-303`; `strata_cli/monitor_commands.py:124-129,231-236`）。
- HTTP 401/403 は終了コード 4、それ以外の HTTP エラーは既定コード 3 で `ClientError` になります。接続不能、redirect、JSON 不正、非 object 応答なども client error です（`strata_cli/client.py:38-42,117-132`; `strata_cli/monitor_commands.py:231-232`）。
- parser が値を受け取れない、または未知の引数を渡した場合は argparse が usage とエラーを出し、終了コード 2 で終了します（`strata_cli/monitor_commands.py:247-248`; `strata_cli/cli.py:2217-2231`）。

## 根拠

- `strata_cli/monitor_commands.py:20-33` — `status` の parser 定義と共有接続オプション。
- `strata_cli/monitor_commands.py:36-46,124-129,167-213,231-248` — launch URL 自動検出、snapshot の取得・表示、失敗時の出力。
- `strata_cli/connections.py:273-303` — `--url`/`--connection` の競合、環境変数・既定値・timeout・資格情報参照の解決。
- `strata_cli/client.py:45-63,79-132,134-152` — URL validation、HTTP request と制限、snapshot の取得・互換 fallback。
- `strata_cli/cli.py:490-493,2217-2231` — status parser の登録とトップレベル CLI の引数処理。
