# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--url URL` |
| 別名 | なし |
| 値 | Strata サーバーのルート URL。HTTP または HTTPS。 |

## 役割

`--served` と併用し、現在稼働中の Strata サーバーから提供中モデルを読み取ります。`--url` 単独では接続先の利用はできず、`--served` が必要です。ローカルのインストール済みモデル一覧を取得する場合は `--url` を使わずに実行します（parser: `strata_cli/cli.py:143-152`、分岐: `strata_cli/cli.py:564-588`）。

## 使い方

```sh
strata models list --served --url https://strata.example:8095
```

ローカル接続では HTTP も受け付けます。

```sh
strata models list --served --url http://127.0.0.1:8095
```

## 値と既定値

- parser は値を文字列として受け取り、URL検証はサーバー接続設定の解決時に行います（`strata_cli/cli.py:148`、`strata_cli/cli.py:568-573`）。
- URL は `http://` または `https://`、ホスト名、および任意の有効なポートで構成するサーバールートでなければなりません。ユーザー情報（`user:pass@`）、ルート以外のパス、クエリ、フラグメントは拒否されます。末尾の `/` は許容され、ホスト名は小文字に正規化されます（`strata_cli/client.py:45-63`）。
- HTTPS でない URL は `localhost`、`127.0.0.1`、`::1` に限られます。それ以外のホストでは HTTPS が必要です（`strata_cli/client.py:58-63`）。
- `--url` 省略時は `STRATA_URL`、それも未設定なら `http://127.0.0.1:8095` が使われます。明示した `--url` は `STRATA_URL` より優先されます（`strata_cli/connections.py:273-291`）。

## 実行時の動作

- `--url` は `--served` のときに `connections.resolve()` へ渡され、解決済み URL を使って読み取り用 `Endpoint` を作り、サーバーのスナップショットを取得します。成功時の結果は現在のサーバーインスタンスのモデル情報に限られ、インストール済みモデル全体の一覧ではありません（`strata_cli/cli.py:564-585`）。
- `--connection` との同時指定は拒否されます。明示した `--url` は `STRATA_CONNECTION` 環境変数の接続選択を使わず、`STRATA_URL` を上書きします（`strata_cli/connections.py:273-291`）。`--credential-env` と `--timeout` は同じ接続解決に渡されます（parser: `strata_cli/cli.py:149-151`、処理: `strata_cli/connections.py:292-302`）。認証環境変数の既定名は `STRATA_API_KEY`、タイムアウトは既定3秒で、明示値は `0 < 秒数 <= 30` の範囲です。
- 接続は `GET` で行われ、Bearer 資格情報がある場合は Authorization ヘッダーに付与されます。クライアントは `/v1/telemetry` を優先し、404 の場合に `/metrics` と `/v1/status`、または `/v1/status` へフォールバックします。リダイレクトは追従しません。応答は JSON で、本文上限は2 MiBです（`strata_cli/client.py:101-152`）。
- `--served` と `--installed` は相互排他です（`strata_cli/cli.py:143-146`）。`--served` を指定した状態では `--install-dir` も拒否されます（`strata_cli/cli.py:565-568`）。`--served` がない状態で `--url` を指定すると、接続オプションには `--served` が必要というエラーになります（`strata_cli/cli.py:586-588`）。

## 出力とエラー

- 成功時、通常表示はサーバーが報告したモデル ID とロード状態を表示し、モデル ID がないときはその旨を表示します。`--output json`（または共通 alias の `--json`）では `scope: served_current_instance`、サーバー URL、モデル配列などを JSON で出力します（`strata_cli/cli.py:575-585`）。
- URL形式・接続オプションの検証エラーは通常 `strata: ...` と stderr に表示し、終了コード2になります。JSON 出力時はエラーオブジェクトを stdout に出します（`strata_cli/cli.py:527-532`、`strata_cli/cli.py:2166-2173`）。
- 通信、HTTP、認証、応答形式の失敗は `ClientError` として扱われます。認証・権限エラーは終了コード4、その他の `ClientError` は既定で3です。HTTP 404 はスナップショット取得時に限って後続エンドポイントへのフォールバック条件になります（`strata_cli/client.py:38-42`、`strata_cli/client.py:117-152`、`strata_cli/cli.py:2184-2188`）。

## 調査範囲

同一 checkout の Python ソースを調査しました。`--help` は実行していません。URL の parser 定義、接続解決、HTTP クライアント、コマンドの成功・例外処理を確認しています。OS ごとのネットワークスタックや接続先サーバー実装による挙動は確認していません。

## 根拠

- parser と option scope: `strata_cli/cli.py:141-152`
- `--served` の接続・一覧処理、および未指定時の拒否: `strata_cli/cli.py:564-588`
- URL の形式検証と HTTPS 条件: `strata_cli/client.py:45-63`
- URL・環境変数・既定値・他接続 option の解決: `strata_cli/connections.py:273-302`
- 読み取り HTTP 要求と fallback: `strata_cli/client.py:101-152`
- エラー表示と終了コード: `strata_cli/cli.py:527-532`、`strata_cli/cli.py:2166-2188`
