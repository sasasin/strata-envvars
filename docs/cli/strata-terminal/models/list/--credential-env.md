# `--credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--credential-env` |
| 別名 | なし |
| 値 | HTTP サーバー認証情報を格納した環境変数の名前（ASCII 識別子、1〜128文字） |

## 役割

`--served` で現在配信中のモデル情報を問い合わせるとき、Bearer 認証に使う環境変数名を指定します。オプション値そのものが秘密情報ではなく、CLI はその名前で実行環境から資格情報を読み取ります。ローカルのインストール済みモデル一覧では接続情報を使わないため、このオプションは `--served` と併用する必要があります（`strata_cli/cli.py:143-152,564-588`）。

## 使い方

```sh
STRATA_READ_KEY='（サーバーの読み取り用キー）' strata models list --served --credential-env STRATA_READ_KEY
```

コマンドは問い合わせ先に読み取り専用のテレメトリー API を使用します。実際のキーをシェル履歴などに残さない方法で環境変数を設定してください。

## 値と既定値

- 値を1つ取ります。parser では既定値を指定していないため、未指定時は `None` です（`strata_cli/cli.py:147-152`）。
- `--served` の処理では、保存済み接続が選択されていればそこに保存された環境変数名、保存済み接続がなければ `STRATA_API_KEY` が既定の参照名です。明示した `--credential-env NAME` はその参照名を上書きします（`strata_cli/connections.py:273-294`）。
- 名前は `[A-Za-z_][A-Za-z0-9_]{0,127}` に一致する必要があります。空文字列、非 ASCII 識別子、128文字を超える名前などは `credential reference must be an ASCII environment variable name` で拒否されます（`strata_cli/connections.py:41-42,66-69,299-302`）。
- 環境変数が未設定または空文字列なら、認証ヘッダーは付加されません。非空の値があれば、それを Bearer token として送ります（`strata_cli/cli.py:569-573`; `strata_cli/client.py:101-107`）。同じオプションを複数回指定した場合の個別検証はありません。通常の `argparse` の値受け取りにより最後の指定値が使われます（parser 定義: `strata_cli/cli.py:150`）。

## 実行時の動作

- `--credential-env` は `--served` と排他的な `--installed` / `--served` 選択グループの外に登録されます。`--served` がないローカル一覧経路で、値が空でない `--credential-env` を指定すると、接続オプションは `--served` が必要だとして終了コード 2 で拒否されます（`strata_cli/cli.py:143-152,564-588`）。値が空文字列の場合はこのチェックを通りますが、`--served` 分岐に入らないため参照名としても使われません。
- `--served` を指定すると、CLI は接続設定を解決して `credential_env` という名前の環境変数を読み、その値を `Endpoint` に渡します。認証情報の文字列自体は標準出力に表示せず、サーバーへの HTTP リクエストの `Authorization: Bearer …` ヘッダーに使います（`strata_cli/cli.py:565-573`; `strata_cli/connections.py:277-302`; `strata_cli/client.py:101-107`）。
- `--connection NAME` がある場合はその保存済み接続の credential 環境変数名を使い、明示した `--credential-env` があれば上書きします。`--connection` と `--url` の同時指定は拒否されます。`--connection` も `--url` もない場合、`STRATA_CONNECTION` があれば保存済み接続を選びます。ただし `--url` が明示されると `STRATA_CONNECTION` による自動選択は行われません（`strata_cli/connections.py:273-294`）。
- 資格情報名を指定しない場合の接続先は `--url`、`STRATA_URL`、既定 URL `http://127.0.0.1:8095` の順で決まり、URL 直指定時の認証参照既定値は `STRATA_API_KEY` です（`strata_cli/connections.py:285-302`）。接続解決の詳細は [`strata config show --credential-env`](../../config/show/--credential-env.md) も参照してください。
- このオプション単独では接続や通信を起こしません。`--served` の実行では `Endpoint.snapshot()` がテレメトリーを取得し、現行エンドポイントが HTTP 404 の場合は `/metrics` と `/v1/status` にフォールバックします。出力は現在のサーバー instance のモデル情報で、ローカルにインストールされたモデル全体の一覧ではありません（`strata_cli/cli.py:571-585`; `strata_cli/client.py:134-152`）。

## 適用条件と副作用

- 有効な用途は `strata models list --served` です。`--install-dir` はローカル installed models 専用で、`--served` と同時に使うと終了コード 2 のエラーになります（`strata_cli/cli.py:565-568`）。
- 実行時にサーバーへ読み取り用 HTTP リクエストを送ります。リモート接続先は HTTPS が必要で、HTTP は localhost、loopback、またはローカル SSH tunnel 用ホストに限られます（`strata_cli/client.py:45-63`）。
- 参照する環境変数の値はファイルに保存されません。このオプションによる接続情報の永続化もありません（`strata_cli/cli.py:569-573`; `strata_cli/connections.py:292-302`）。

## 出力とエラー

- 成功時は人間向け出力または `--output json` / `--json` の JSON を標準出力に出します。モデル ID がなければ人間向けには `No model ID reported by this server` と表示され、JSON では `models: []`、`model_count: 0` になります（`strata_cli/cli.py:575-585`; JSON / human 共通出力: `strata_cli/cli.py:535-542`; `--json` 登録: `strata_cli/cli.py:508-515`）。
- 環境変数名や接続 URL の不正、保存済み接続の読み込み失敗は `ValueError` 系として処理され、通常は終了コード 2 です。`Endpoint` の通信失敗は `ClientError` として変換され、認証拒否は終了コード 4、テレメトリー形式の非互換は 5、未指定のネットワーク／HTTP エラーは原則 3 で報告されます。人間向けエラーは標準エラー、JSON モードでは `{schema_version, ok:false, error}` を標準出力へ出します（`strata_cli/client.py:38-42,109-152`; `strata_cli/cli.py:527-532,2166-2188`）。

## 根拠

- `strata_cli/cli.py:141-152` — `models list` parser、`--served` / `--installed` の排他設定と `--credential-env` 宣言。
- `strata_cli/cli.py:564-596` — `--served` 時の接続解決・環境変数取得・問い合わせと、ローカル一覧経路で接続オプションを拒否する条件。
- `strata_cli/connections.py:41-42,66-69,273-302` — 環境変数名の形式、接続からの既定値・明示値の優先順位、タイムアウトと接続先の解決。
- `strata_cli/client.py:45-63,84-125,134-152` — URL 条件、Bearer ヘッダー、通信失敗、テレメトリー取得と fallback。
- `strata_cli/cli.py:527-542,2166-2188` — 成功・失敗出力と終了コードの処理。
