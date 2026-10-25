# `strata config`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/connections.py` |
| 配下の操作 | `show`（実効接続設定の表示） |

## 役割

`strata config show` は、Terminal CLI の read-only クライアントが使う接続先、認証情報の参照先、timeout と、それぞれの設定元を解決して表示します。設定を保存・変更するコマンドではなく、この操作自体はサーバーへ接続しません。HTTP の状態取得は `strata status` や `strata monitor` の役割です。

このページは `strata config` のコマンド概要です。実効値や個別フラグは [`strata config show` の概要](show/README.md) と [CLI オプション索引](../../README.md)を参照してください。

## 代表的な使い方

```sh
# 環境変数や既定値から解決される設定を表示
strata config show

# 保存済み接続を選んで解決
strata config show --connection work

# URL と認証値の環境変数名を一時指定し、JSON で表示
strata config show --url https://strata.example --credential-env STRATA_TELEMETRY_KEY --output json
```

`--url` と `--connection` は同時に指定できません。JSON 形式を使う場合は `--output json` またはその alias `--json` を使います。値と優先順位は [`--url`](show/--url.md)、[`--connection`](show/--connection.md)、[`--credential-env`](show/--credential-env.md)、[`--timeout`](show/--timeout.md)、[`--output`](show/--output.md) を参照してください。

## 主な動作と副作用

- parser は `config` の下に `show` を必須サブコマンドとして登録します。`show` では `--effective`（実効値表示。指定しなくても同じ）、接続先などの選択フラグ、および出力形式を受け付けます（`strata_cli/monitor_commands.py:96-103`）。
- `show` は `connections.resolve()` を呼び、環境変数・保存済み接続・CLI 指定を解決して結果を出力します。通常出力では解決結果の JSON オブジェクト、機械出力では `schema_version`、`ok`、`effective` を含む JSON を返します（`strata_cli/monitor_commands.py:132-139`）。
- 接続先は `--connection` または `--url` で明示できます（両方の同時指定はエラー）。どちらもなければ `STRATA_CONNECTION` があれば保存済み接続を選び、そうでなければ `STRATA_URL`、既定 URL の順に解決します。保存済み接続を選んだ場合はその URL・prefix・credential-env 参照が使われますが、`--credential-env` があれば認証環境変数名だけを上書きします。credential の値そのものは表示せず、指定環境変数に値があるかを `credential_present` として示します。結果には各設定の `origins` も含まれます（`strata_cli/connections.py:273-303`）。
- 指定 URL は HTTP(S) のサーバールート形式に限られ、非 loopback の接続先には HTTPS が必要です。timeout は 0 より大きく 30 秒以下でなければなりません（`strata_cli/client.py:45-76`、`strata_cli/connections.py:292-303`）。
- `strata config show` の処理は接続設定の読取りと表示までで、通信・設定保存・ファイル生成を行いません。保存済み接続を指定した場合は接続記録を読み取ります（`strata_cli/monitor_commands.py:132-139`、`strata_cli/connections.py:128-146,273-303`）。
- Terminal CLI の共通入口 `main()` は parser の実行前にユーザー所有ファイルの既定権限を採用する helper を呼びます。これは config 専用の処理ではありません（`strata_cli/cli.py:2218-2224`）。

## 注意点

- `strata config` のままでは必須の `show` がないため、argparse が usage とエラーを表示して終了します。未知の引数も CLI の共通 parser が拒否します（`strata_cli/monitor_commands.py:96-103`、`strata_cli/cli.py:2223-2231`）。
- URL と保存済み接続を同時に選ぶ、URL・prefix・環境変数名が不正、timeout が範囲外、または保存済み接続が欠落・不正の場合は失敗します。アプリケーション側の設定エラーは stderr の `strata: ...` と終了コードで返し、JSON 指定時はエラーオブジェクトを stdout に出します。保存接続の不存在・不正は通常コード 5、入力値の不正は通常コード 2 です（`strata_cli/connections.py:47-69,128-146,273-303`、`strata_cli/monitor_commands.py:124-129,231-240`）。
- リリース配布物の実行確認はこの調査では行っていません。ここに記した挙動は上記 commit のソースに基づきます。

## 関連文書

- [`strata config show`](show/README.md) — 実効接続設定と各 option の詳細
- [`strata connection`](../connection/README.md) — 保存済み接続の管理
- [`strata status`](../status/README.md) — サーバーから状態を一度取得
- [`CLI オプション索引`](../../README.md) — Terminal CLI 全体の文書一覧

## 根拠

- `strata_cli/cli.py:27,488-493,2119-2165,2218-2248` — CLI の parser 登録、実行委譲、共通入口とエラー処理。
- `strata_cli/monitor_commands.py:16-25,75-103,124-139,231-240` — 設定コマンドの parser、設定解決・出力、失敗時の出力。
- `strata_cli/connections.py:41-69,72-90,128-146,273-303` — 接続記録の位置・検証・読取り、設定ソースの優先順位と解決結果。
- `strata_cli/client.py:45-76` — URL と reverse-proxy prefix の形式検証。
