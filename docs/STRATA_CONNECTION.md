# `STRATA_CONNECTION`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの動作は対象外。

## 役割

`strata` の読み取り専用クライアント系 CLI で、保存済み接続レコードを名前で選ぶための環境変数です。`status`、`monitor`、`logs`、`config show`、サーバー上のモデル一覧などが共有する `connections.resolve()` が参照します。保存レコードは URL、proxy prefix、認証値そのものではなく認証用環境変数名を持ちます。

## 値と判定

文字列の文法や大文字小文字を環境変数値自体に対して事前検査する処理はありません。Python の `env.get("STRATA_CONNECTION")` の結果を truthy 判定し、真ならその文字列を保存済み接続名として `load()` に渡します。接続名は `^[a-z][a-z0-9_-]{0,63}$` に一致する必要があります。値の前後空白除去や大文字小文字変換はありません。

| 状態 | 接続解決での扱い |
|---|---|
| unset | 接続名を選ばず、`--url` がなければ `STRATA_URL`、さらに未設定なら `http://127.0.0.1:8095` を使う |
| 空文字 | truthy 判定が偽なので unset と同じく接続名を選ばない |
| 非空文字列 | 保存接続名として使う。名前が不正、またはレコードが不正・存在しない場合は接続解決エラー |
| `--url` が指定済み | 環境変数は接続選択式で参照されず、URL による直接接続を使う |
| 明示 `--connection` | その引数が環境変数より優先される。CLI では `--url` と同時指定できない |

CLI 引数 `--connection` が非空なら環境変数より優先します。`--url` と `--connection` を両方渡すと `choose --url or --connection, not both` のエラーになります。`STRATA_CONNECTION` が選ばれた場合は保存値の URL/prefix/credential-env を使います。未選択時の直接 URL 接続では `STRATA_API_KEY` が認証環境変数名の既定値です。

## 有効になる条件

この変数は Strata Python CLI の接続解決経路でのみ使われます。任意のエンジンプロセスが読む変数ではありません。`strata monitor` では `--url` また `--connection` を引数で指定しない場合に限り `running_launch()` を呼び、起動中 launch の接続先情報を探索します。ただし `running_launch()` 自身は `os.environ.get("STRATA_CONNECTION")` が truthy なら launch 情報の探索を省略します。その後の接続解決では環境変数が保存接続を選びます。空文字はこの探索抑止条件にもなりません。

CLI の接続選択に使われる場合、保存接続の読み込みは `STRATA_CONNECTION_DIR` または OS ごとの既定ディレクトリに依存します。通常は `${XDG_CONFIG_HOME:-~/.config}/strata/connections`、Windows は `%APPDATA%/Strata/connections`（APPDATA がない場合はホーム下）です。選択名に対応するレコードが使えない場合、`STRATA_URL` への暗黙 fallback は行われず、解決エラーとなります。

## 実行時の詳細

`connections.resolve()` は呼び出し時に `os.environ` を参照します。モジュール import 時のキャッシュではありません。選択した接続レコードをロード・検証した後、正規化 URL/prefix、credential-env 名、認証環境変数の設定有無などを返します。認証値そのものを接続レコードに格納する動作ではありません。解決結果を使う呼び出し元が `Endpoint` を作り、接続先へ要求を送ります。

`config show` は接続先設定の由来と認証変数が存在するかを表示する用途で、値を表示しないと `docs/TERMINAL.md` は説明しています。`STRATA_CONNECTION` の値が不正または参照先が不正な場合は、共通 CLI の `ConnectionError` 経路でエラー応答になります。環境変数を子プロセスへ転送・上書きする実装は、この接続解決箇所では確認できません。

## 根拠

- `strata_cli/connections.py:41-55`: 接続名の許容形式。
- `strata_cli/connections.py:72-95`: 接続レコードディレクトリの選択と名前からのファイルパス構築。
- `strata_cli/connections.py:97-114`: レコードの schema、ID、URL、prefix、credential-env の検証。
- `strata_cli/connections.py:273-303`: `STRATA_CONNECTION` / `--connection` / `--url` の選択、既定 URL と credential-env、返却値。
- `strata_cli/monitor_commands.py:36-47,195-199`: 起動中 launch 情報探索の条件と、monitor での解決結果からの Endpoint 構築。
- `strata_cli/cli.py:566-570`: サーバー上のモデル一覧で共通解決関数を利用する例。
- `docs/TERMINAL.md:44`: CLI の優先順位と接続ディレクトリに関する製品説明。上記の挙動説明はソース実装を根拠とする。
