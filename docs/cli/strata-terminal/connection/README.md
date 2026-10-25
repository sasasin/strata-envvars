# `strata connection`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/connections.py` |
| 子コマンド | `create`、`show`、`list`、`set` |

## 役割

`strata connection` は、monitor が参照するサーバー endpoint を名前付きでローカルに保存・表示・編集する親コマンドです。各子コマンドの指定が必要で、親コマンド単独では操作しません。これは monitor 専用の接続記録であり、モデルの serving profile とは別です。

接続記録にはサーバー URL、reverse proxy の path prefix、credential を読む環境変数の**名前**を保持します。credential の値そのものは保存しません。記録の作成・参照・編集はローカルファイル操作で、これらの管理コマンド自身は server に問い合わせません。

## 主な使い方

```sh
# endpoint を新規保存する
strata connection create work --url https://inference.example --prefix /strata --credential-env STRATA_TELEMETRY_KEY

# 保存した記録を一覧・表示する
strata connection list --output json
strata connection show work

# 変更内容を確認してから保存する
strata connection set work prefix=/new-strata --plan
strata connection set work prefix=/new-strata --if-revision REVISION
```

`set` で指定できる assignment は `url=ROOT`、`prefix=/PATH`、`credential_env=ENV_NAME` です。`--if-revision` には `show`、`list`、または `set --plan` が表示する revision を指定できます。接続記録を monitor などで実際に使う方法は `strata status`、`strata monitor`、`strata logs` の各コマンドを参照してください。

## 子コマンドと主な動作

| 子コマンド | 動作 |
| --- | --- |
| `create NAME --url URL` | 名前付き記録を新規作成します。`--prefix` の既定値は空、`--credential-env` の既定値は `STRATA_TELEMETRY_KEY` です。同名記録がある場合は上書きせず失敗します。 |
| `show NAME` | 保存記録と revision を表示します。credential の値は記録されておらず、表示もしません。 |
| `list` | 保存記録を名前順に表示します。読み込み不備の記録はリスト内に個別の `error` として示されます。 |
| `set NAME KEY=VALUE` | URL、prefix、credential 環境変数名のいずれか一つを編集します。`--plan` は保存せず変更案を表示し、通常実行は revision を照合してから保存します。 |

全子コマンドは `--output human|json`（既定 `human`）、`--json`（`--output json` の別名）、`--quiet` を受け取ります。JSON 出力では成功結果に `schema_version: 1` と `ok: true` が付きます。人間向け出力ではこの2項目を除いた payload が表示されます。`--quiet` は人間向け stdout を抑制し、JSON 出力には適用されません。

## 保存先と副作用

既定の保存先は POSIX では `${XDG_CONFIG_HOME:-~/.config}/strata/connections`、Windows では `%APPDATA%/Strata/connections` です。`STRATA_CONNECTION_DIR` を指定すると保存先を切り替えられ、その値は絶対パスでなければなりません。作成時は owner-private なディレクトリを作り、記録ファイルを mode `0600` で新規作成します。POSIX では既存ディレクトリと記録ファイルも owner-only であることを検証します。

記録名は小文字 ASCII の `a-z` で始まり、その後は `a-z`、数字、`_`、`-` を使える最大64文字です。credential 参照は ASCII の環境変数名形式で検証されます。記録は schema version 1、最大4 KiBです。URL と prefix は client helper で正規化・検証され、保存時には許可された形と一致することが確認されます。ソース文書は、remote URL に HTTPS が必要で prefix は単純な path segment に限ると説明しています（`docs/TERMINAL.md:44`）。

`set --plan` は候補と現在の revision を読み取り、保存しません。通常の `set` は同じ記録のロック下で revision を再確認し、変化があれば競合として失敗します。変更があれば一時ファイルを書いて置換し、内容が同じ場合は書き換えません。`--if-revision` が現在の revision と異なる場合も保存前に拒否されます。

## 出力と失敗

不正な引数形式は argparse が拒否します。アプリケーション側の接続記録エラーは人間向けでは `stderr` に `strata: ...` として出力され、エラーに設定された終了コードを返します。JSON モードでは `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON を出力します。主な失敗条件は不正な名前・URL・prefix・環境変数名、同名記録の作成、読み込み不能または非正規の記録、権限条件違反、revision 競合です。

この調査では対象 checkout の parser と実装、checkout 内の Terminal 文書を確認しました。別途インストール済み CLI や Release artifact の help 出力は実行していないため、それらの配布状態・platform ごとの実挙動までは確認していません。Windows の ACL 条件についても、この文書からは評価しません。

## 関連文書

- [CLI 索引](../../README.md) — `strata-terminal` のコマンドとオプション文書。
- [`strata connection create`](create/README.md)
- [`strata connection show`](show/README.md)
- [`strata connection list`](list/README.md)
- [`strata connection set`](set/README.md)

## 根拠

- `strata_cli/cli.py:488-494,2153-2165` — Terminal CLI へのコマンド登録と monitor command 実行への dispatch。
- `strata_cli/monitor_commands.py:75-103` — `connection` と4つの子 parser、子コマンド共通出力 options。
- `strata_cli/monitor_commands.py:132-164,167-175,231-240` — 子コマンドのローカル処理、出力形式、エラー経路。
- `strata_cli/connections.py:41-90,97-120,128-164` — 名前・環境変数参照・保存先・記録の検証、読込、一覧。
- `strata_cli/connections.py:167-187,190-218,221-270` — 一時ファイル置換、ロック、新規作成、revision 検査と更新。
- `docs/TERMINAL.md:30-44`、`docs/TERMINAL_QUICKSTART.md:23-30` — 接続記録の用途、呼び出し例、保存先とcredential参照に関する checkout 内の利用者向け説明。
- `docs/cli/README.md:1033-1073`（strata-envvars）— `strata connection` と子コマンド概要の索引リンク。
