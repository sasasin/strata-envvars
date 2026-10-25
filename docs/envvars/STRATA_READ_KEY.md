# `STRATA_READ_KEY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_READ_KEY` という名前を特別扱いする実装はありません。Strata のターミナル監視クライアントは、`--credential-env` または保存済み接続に指定された環境変数名を使って、実行時にその環境変数の値を取得します。その名前として `STRATA_READ_KEY` を指定した場合に限り、この変数がサーバー接続の資格情報として使われます。環境変数名は `credential_name()` の ASCII 識別子形式を満たす必要があります。

取得した値は、空でなければ監視 API リクエストの `Authorization: Bearer ...` ヘッダーに設定されます。保存済み接続に保存されるのは変数名であり、秘密値ではありません。

## 値と判定

| 状態 | 動作 |
|---|---|
| `STRATA_READ_KEY` が未設定 | この名前を参照していれば `os.environ.get()` は `None` を返し、資格情報なしで接続します。monitor が自動検出した起動中サーバーを使う場合は、その起動情報に含まれるキーへ fallback します。 |
| 空文字 | 資格情報なしとして扱います。monitor の起動情報 fallback 条件を満たす場合は、そのキーへ fallback します。 |
| 空でない値 | 文字列全体が資格情報として使われます。Strata クライアントはその値を数値や真偽値に変換しません。 |
| 変数名が不正 | 指定された環境変数名が `[A-Za-z_][A-Za-z0-9_]{0,127}` に一致しない場合、接続設定の解決時に `ConnectionError` になります。 |

この値について、Strata クライアント側に長さ制限、文字種検査、trim、大小文字変換はありません。値がサーバーに受理されるかは接続先の認証処理によります。

## 有効になる条件

- `strata status`、`strata monitor`、`strata logs`、`strata models list --served` などの読み取り専用監視接続で、`--credential-env STRATA_READ_KEY` が渡されるか、選択された保存済み接続の `credential_env` が `STRATA_READ_KEY` であること。
- `--credential-env` は選択した接続の資格情報参照を上書きします。URL直指定など保存済み接続を使わない場合の既定名は `STRATA_API_KEY` です。新しい保存済み接続の既定名は `STRATA_TELEMETRY_KEY` です。
- `strata monitor` が明示 URL、接続名、`STRATA_CONNECTION`、`STRATA_URL` を使わず、ローカル起動情報からサーバーを自動検出した場合、環境変数が未設定または空なら検出した起動情報のキーを使います。この fallback は同じ条件の `status`、`logs`、`models list --served` にはありません。
- サーバーから返る認証結果はクライアントの資格情報選択とは別です。クライアントは指定値を Bearer ヘッダーに載せ、HTTP 401/403 を `telemetry authentication or permission failed` として報告します。

## 実行時の詳細

`connections.resolve()` は `credential_env` の参照名を選び、`credential_present` には `bool(env.get(key_ref))` を返します。この設定表示は値そのものを出しません。実際に通信する経路では、`monitor` / `status` / `logs` の共通処理や `models list --served` が `os.environ.get(resolved["credential_env"])` を呼び、その場で得た値を `Endpoint` に渡します。`Endpoint.get()` は値が truthy の場合だけ Authorization ヘッダーを追加します。

環境変数はコマンド実行中の解決・通信時に読み取られ、読み取り後の変更を監視する処理や static cache はありません。接続作成・編集では資格情報の値を読み取らず、参照名だけを保存します。

リポジトリ内で文字列 `STRATA_READ_KEY` が現れるのは接続機能のテストです。そこでは `--credential-env STRATA_READ_KEY` を指定して参照名が保存・解決されることを確認しています。本番コードには `STRATA_READ_KEY` 固有の既定値や分岐はありません。

## 根拠

- `strata_cli/connections.py:41-43,66-69` — 参照名の形式。
- `strata_cli/connections.py:221-226,273-303` — 保存時の既定値、CLI/接続/既定の優先順位、presence 判定。
- `strata_cli/monitor_commands.py:20-25,132-138,195-199` — 監視系引数と環境変数参照、自動検出キーへの fallback。
- `strata_cli/cli.py:566-570` — `models list --served` の環境変数参照。
- `strata_cli/client.py:84-107,117-123` — truthy な資格情報の Bearer ヘッダー設定と認証エラー。
- `tests/terminal/test_connections.py:35-70,186-198` — `STRATA_READ_KEY` を動的な資格情報参照名として使うテスト。
- `docs/TERMINAL.md:30-44,236` — 監視用接続が参照名を保存すること、`--credential-env` と既定名の説明。`docs/DETAILS.md` には `STRATA_READ_KEY` 固有の説明はありません。
