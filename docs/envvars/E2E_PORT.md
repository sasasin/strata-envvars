# `E2E_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/context-e2e.mjs` が起動する E2E 用 `serve/server.py` のポートを指定します。スクリプトが生成する一時 server config の `port`、子プロセスに渡す `--port`、起動後の health check URL に同じ値を使います。この変数は Strata 本体の通常起動設定ではなく、実エンジンを使う context E2E 補助スクリプトの設定です。

## 値と判定

| `E2E_PORT` | `PORT` の値 | スクリプトでの扱い |
|---|---:|---|
| 未設定 | `18590` | 既定ポートとして config、子サーバー引数、health check URL に使う |
| 空文字 | `0` | `Number('')` の結果を使う。既定値には戻らない |
| 数値として解釈できる文字列 | その数値 | そのまま使う。整数・ポート範囲への制限はない |
| `Infinity` / `-Infinity` | 正/負の無限大 | config JSON では `null` になり、引数と URL には `Infinity` / `-Infinity` を使う |
| 数値でない文字列 | `NaN` | 検査・fallback・エラー処理をせず下流へ渡す |

既定値は `env(name, fallback)` helper の nullish 判定（`process.env[name] ?? fallback`）で選び、その後 JavaScript の `Number(...)` で文字列全体を変換します。したがって `0`、負数、小数、空白文字列などもスクリプト側では拒否・clamp されません。`Number` が受理する数値表記（指数・基数表記を含む）は数値になり、末尾に余分な文字がある文字列など、変換できない値は `NaN` です。生成した JSON では `NaN` と無限大は `null` になり、子プロセスの `--port` 引数と health check URL にはそれぞれ `NaN` または `Infinity` / `-Infinity` が文字列として使われます。これらの値を受け取ったサーバー側の解釈はこのスクリプトの実装範囲外です。

## 有効になる条件

- `E2E_BASE_URL` が空または未設定なら、スクリプトは `serve/server.py` を起動し、`E2E_PORT` の値を config と `--port` に渡します。また `http://127.0.0.1:${PORT}` を health check と API の base URL にします。
- `E2E_BASE_URL` が空でない場合は、その URL を接続先にし、ローカルサーバーを起動しません。この経路では `E2E_PORT` は config JSON に記録されますが、接続先 URL には使われません。
- `E2E_PORT` に対応する CLI 引数や、別のポート用環境変数との優先順位分岐はありません。`PORT` はスクリプトのモジュール評価時に一度定数化され、実行中に環境を変更しても再読込されません。

## 実行時の詳細

スクリプト起動時に `PORT` を計算し、一時ディレクトリ内の `server.json` を作成します（`E2E_BASE_URL` の有無にかかわらず config ファイル自体は作成します）。ローカルサーバーを起動する経路では、そのファイルを `--config` で渡し、同時に `--port String(PORT)` も渡します。サーバーが起動した後は、最大120回、2秒間隔で `http://127.0.0.1:${PORT}/health` を確認します。`E2E_BASE_URL` 経路では health check の base はその URL です。

このスクリプトは値の形式やポート範囲を検証しません。起動できない・health check が成功しない場合には、スクリプト自身が `the engine did not become ready:` と子サーバー出力の末尾を stderr に出し、終了コード `4` で終了します。引数として無効なポート値を渡したときに子サーバーがどう応答するか、または実際に指定ポートで bind できるかは、このコードだけからは断定できません。

## 根拠

- `apps/host/scripts/context-e2e.mjs:25-37` — `env()` の nullish fallback、`E2E_PORT` の既定値 `18590` と `Number` 変換、`E2E_BASE_URL` の読み取り。
- `apps/host/scripts/context-e2e.mjs:47-61` — E2E 前提条件と、`PORT` を含む一時 server config の作成。
- `apps/host/scripts/context-e2e.mjs:78-95` — `E2E_BASE_URL` がない場合の子サーバー起動、`--port` への転送、health check、未 ready 時のログと終了コード。
- `apps/host/scripts/context-e2e.mjs:87-97` — 既存 URL または localhost の選択と、後続 API 接続先。
