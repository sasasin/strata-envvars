# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--url URL` |
| 別名 | なし |
| 値 | Strata サーバーの root URL。`http://` または `https://` |

## 役割

モニターが接続する Strata サーバーを明示します。値はサーバーの root であり、リバースプロキシのパス prefix はこのオプションには含めません。リモート接続は HTTPS が必要で、HTTP は loopback のローカル接続に限られます（`strata_cli/monitor_commands.py:20-25`、`strata_cli/client.py:45-63`）。

## 使い方

```sh
strata monitor --url http://127.0.0.1:8095
strata monitor --url https://strata.example.net
```

対話型モニターでは stdout が端末である必要があります。端末を使わず一度だけ取得する場合は `--once` を併用できます（`strata_cli/monitor_commands.py:49-60, 189-194`）。

## 値と既定値

- `--url` 自体は任意です。省略時は、明示の `--connection`、`STRATA_CONNECTION`、起動中の `strata launch` の接続情報、`STRATA_URL`、既定 URL の順で接続先が選ばれます。起動中の launch 情報は、明示 URL/接続名がなく、かつ `STRATA_URL` と `STRATA_CONNECTION` も設定されていない場合にだけ先に調べられます（`strata_cli/monitor_commands.py:36-46, 195-199`、`strata_cli/connections.py:273-302`）。
- 直接指定 URL の既定値は `http://127.0.0.1:8095` です。`STRATA_URL` があれば既定 URL より優先されます（`strata_cli/connections.py:44, 285-290`）。
- scheme は `http` または `https`、host は必須です。URL に user info（`user:pass@host`）、root 以外の path、query、fragment は指定できません。port が不正な場合も拒否されます。scheme が HTTPS 以外なら host は `localhost`、`127.0.0.1`、`::1` のいずれかでなければなりません。host は小文字化され、明示された port は保持されます（`strata_cli/client.py:45-63`）。
- 空文字や不正な URL は parser ではなく、接続先解決時の validation で失敗します（`strata_cli/monitor_commands.py:196-198`、`strata_cli/client.py:45-63`）。

## 実行時の動作

`strata monitor` の parser は `--url` を値付き引数として登録し、monitor 実行時に `connections.resolve()` へ渡します（`strata_cli/monitor_commands.py:20-25, 49-52, 195-199`）。

明示した `--url` は `STRATA_URL` と既定 URL を上書きします。`--url` と `--connection` の同時指定はエラーです。`--url` を指定しない場合、`STRATA_CONNECTION` に名前があれば保存済み接続の URL と prefix が使われ、`STRATA_URL` より優先されます。`--url` を指定した場合、`STRATA_CONNECTION` は選択されません（`strata_cli/connections.py:273-301`）。

明示 URL を使う場合の prefix は空です。逆プロキシ配下の path prefix を使う保存接続とは異なり、この引数単独では prefix を設定しません（`strata_cli/connections.py:280-301`）。認証 token も URL には埋め込めません。既定では環境変数 `STRATA_API_KEY` の値が Bearer credential として使われ、`--credential-env` で参照する環境変数名を変えられます。launch 情報を自動選択した場合は、その key が参照環境変数に値がないときの fallback になります（`strata_cli/connections.py:287-301`、`strata_cli/monitor_commands.py:198-199`、`strata_cli/client.py:101-108`）。

取得には HTTP GET を用い、Strata が許可する読み取り用 endpoint は `/v1/telemetry`、`/v1/status`、`/metrics`、`/health` です。モニターの snapshot はまず `/v1/telemetry` を読み、404 の場合に `/metrics`、さらにその 404 時には `/v1/status` へ fallback します。HTTP redirect は追従せずエラーになります（`strata_cli/client.py:79-82, 101-132, 134-152`）。

## 適用条件と副作用

- `strata monitor` 専用の parser ではなく、`status`、`logs`、`config show` も同じ `_connection()` 定義を使います。ただし本書の対象範囲は索引に従い `strata monitor` です（`strata_cli/monitor_commands.py:20-25, 28-33, 49-52, 63-72, 96-103`、`strata_cli/cli.py:490-493`）。
- `--url` と `--connection` の併用は拒否されます。remote URL の平文 HTTP、埋め込み credential、root でない URL も拒否されます（`strata_cli/connections.py:277-280`、`strata_cli/client.py:45-63`）。
- このオプションの処理は接続先を選び、モニターはサーバーの読み取り用 telemetry/status を取得します。`--url` 自体による設定ファイルの保存やサーバー設定の変更は確認できません。対話 UI の接続画面で保存操作を行う経路は別機能です（`strata_cli/monitor_commands.py:203-229`）。
- サーバー応答 body は 2 MiB までに制限され、JSON 以外の Content-Type や不正 JSON は失敗します（`strata_cli/client.py:17, 101-132`）。

## 出力とエラー

URL validation や `--url` と `--connection` の競合はエラーコード 2 です。通常の human 出力では `strata: ...` を stderr に出します。HTTP 認証/権限エラーはコード 4、通信失敗やその他 HTTP エラーは既定コード 3、互換性のない telemetry schema はコード 5 になります（`strata_cli/monitor_commands.py:124-129, 231-240`、`strata_cli/client.py:117-132, 142-152`）。

`--output json` または `--json` は `--once` が必要です。JSON を使わない対話モードでは stdout が端末でない場合にコード 2 で終了します（`strata_cli/monitor_commands.py:189-194`）。

## 根拠

- `strata_cli/monitor_commands.py:20-25` — `--url` の parser 定義と接続関連 option の共通登録。
- `strata_cli/monitor_commands.py:36-46, 189-199, 203-229, 231-240` — 起動中 launch の検出、実行時の接続解決、monitor 起動、例外処理。
- `strata_cli/connections.py:44, 273-302` — 既定 URL、URL/保存接続/環境変数の選択と競合処理。
- `strata_cli/client.py:45-63, 79-132, 134-152` — URL validation、HTTP 要求、snapshot endpoint と fallback。
- `strata_cli/cli.py:490-493, 2153-2165` — Terminal CLI への monitor parser 登録と dispatcher。
- [`docs/cli/README.md`](../../README.md) — `strata monitor` のコマンド階層と option 文書リンク。
