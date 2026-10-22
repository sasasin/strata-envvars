# `STRATA_URL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。調査対象リポジトリの作業ツリーは clean。外部ライブラリとテスト専用コードは対象外。

## 役割

Strata Terminal CLI が monitor/status 系コマンドで接続するサーバーの URL を指定します。対象は `strata status`、`strata monitor`、`strata logs`、`strata config show`、および `strata models list --served` の接続解決です。エンジンやサーバーの bind address を設定する変数ではありません。

`strata config show` は解決した URL とその由来を表示しますが、接続はしません。status/monitor/logs と `models list --served` は解決した接続先に問い合わせます。根拠: `strata_cli/monitor_commands.py:132-138,195-203`、`strata_cli/cli.py:562-580`。

## 値と判定

変数は文字列 URL として読み、数値や真偽値への変換はありません。値の構文検証と正規化は `strata_cli.client.server_url()` が行います。

| 状態・値 | 扱い |
|---|---|
| 未設定 | 他の接続指定がない場合、`http://127.0.0.1:8095` を使う。 |
| 空文字 | 未設定扱いにはならず、そのまま URL 検証に渡されてエラーになる。 |
| `http` URL | `localhost`、`127.0.0.1`、`::1` のみ許可。 |
| `https` URL | ローカル・リモートいずれのホストでも許可。 |
| それ以外 | scheme と hostname がない、userinfo（`@`）を含む、root 以外の path、query、fragment、無効な port などは拒否。 |

入力は前後空白を trim しません。受け付けた URL は hostname を小文字化し、空または `/` の path を取り除いた server root に正規化します。明示した port は維持します。remote の平文 HTTP は拒否され、`server_url()` は `remote monitoring requires HTTPS or a local SSH tunnel` を返します。根拠: `strata_cli/client.py:45-63`。

## 有効になる条件

接続先は次の優先順位で選ばれます。

1. CLI の `--url` または `--connection`。両方を指定すると `choose --url or --connection, not both` でエラー。
2. CLI の明示指定がなければ、設定済みで空でない `STRATA_CONNECTION` が指す保存済み connection。これが選ばれると `STRATA_URL` は使いません。
3. それ以外では `STRATA_URL`。
4. `STRATA_URL` も未設定なら `http://127.0.0.1:8095`。

従って `--url` はこの環境変数を上書きします。空の `STRATA_CONNECTION` は connection 選択としては false になり、URL の解決へ進みます。CLI の URL と connection の排他、および保存済み connection の選択は `strata_cli/connections.py:273-291` にあります。ドキュメントの優先順位も `docs/TERMINAL.md:44` に記載されており、実装と一致します。

## 実行時の詳細

`connections.resolve()` が呼ばれた時に `os.environ` から値を読みます。値を static cache するコードはなく、同一プロセスで呼び出し前に環境辞書が変更されれば次の呼び出しで再取得されます。通常の CLI は一回のコマンド実行で解決し、実行中にシェル側の環境を変更してもそのプロセスの `os.environ` には反映されません。根拠: `strata_cli/connections.py:273-298`。

`strata monitor` は `--url`、`--connection`、`STRATA_CONNECTION`、`STRATA_URL` のいずれも truthy でない場合に限り、起動済み `strata launch` の URL と key を探します。`STRATA_URL` に空文字を設定した場合、この自動探索を止めませんが、その後の URL 解決では空文字が採用されて URL 検証エラーになります。見つかった launch URL は `connections.resolve(url=...)` に明示引数として渡されるため、通常の環境 URL より優先されます。根拠: `strata_cli/monitor_commands.py:36-46,195-199`。

`strata status` / `monitor` / `logs` では、解決 URL を `Endpoint` に渡して telemetry 等の read-only API を呼びます。`models list --served` も同じ resolver を使い、現行 server instance の telemetry を読みます。無効な URL はコマンド側の ValueError 処理で human 出力なら stderr の `strata: <エラー文>`、JSON 出力ならエラー JSON になり、終了コード 2 です。根拠: `strata_cli/client.py:84-110`、`strata_cli/monitor_commands.py:231-236`、`strata_cli/cli.py:2149-2157`。

Docker の `docker/strata-wrapper.sh` は Terminal を起動する前に `STRATA_URL` が未設定または空なら `http://127.0.0.1:${PORT:-8080}` を設定して export します。非空のユーザー指定値は維持します。これは wrapper 固有の既定値で、CLI の一般既定値 `http://127.0.0.1:8095` とは異なります。根拠: `docker/strata-wrapper.sh:1-10`。Docker の変数表では `STRATA_URL` は公開設定として記載されていません（`docs/DOCKER.md:115-135`）。

`apps/host/scripts/` にも同名参照がありますが、Playwright の画面確認や実アプリ操作を行う開発・検証スクリプトです（例: `flow.mjs`、`agent-http.mjs`）。調査手順のテスト専用コード除外に従い、Terminal の利用者向け挙動の根拠には含めていません。`tests/` と `bench/results/` 内の記録・スクリプトも同様に実装根拠から除外しました。

## 根拠

- `strata_cli/connections.py:273-301` — `STRATA_URL` の読み取り、接続指定の優先順位、未設定時の既定値、解決結果の origin。
- `strata_cli/client.py:45-63` — URL の受理条件、拒否条件、正規化。
- `strata_cli/monitor_commands.py:36-46,132-138,195-203,231-236` — monitor の launch 自動探索、status/monitor/logs/config の接続解決とエラー処理。
- `strata_cli/cli.py:562-580,2149-2157` — `models list --served` の利用箇所と CLI エラー処理。
- `docker/strata-wrapper.sh:1-10` — Docker Terminal wrapper の空値を含む既定値設定。
- `strata_cli/client.py:84-110` — `Endpoint` が解決 URL を read-only API request に使う箇所。
- `docs/TERMINAL.md:44` — 接続優先順位の説明（ソースと一致）。
