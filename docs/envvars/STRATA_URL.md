# `STRATA_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

端末クライアントが status / monitor / logs / served model list / config show で使う Strata サーバーのルート URL を指定します。また、Docker 内の `strata` ラッパーと `apps/host/scripts` の開発・画面確認スクリプトが、それぞれ子プロセスへ渡す URL または HTTP 接続先として使います。Strata のモデル生成・推論エンジン自体が読む変数ではありません。

## 値と判定

端末クライアントの `connections.resolve()` は、`--url` が指定されていない場合に `env.get("STRATA_URL", DEFAULT_URL)` を使います。値は `Endpoint` に渡され、`server_url()` が検証・正規化します（`strata_cli/connections.py:273-301`, `strata_cli/client.py:45-64,84-99`）。

| 入力 | 端末クライアントでの扱い |
|---|---|
| 未設定 | 他の接続指定がなければ既定 `http://127.0.0.1:8095`。|
| 空文字 | 辞書にキーがあれば空文字を採用し、既定値には戻らない。URL 検証で拒否される。|
| URL | `http` または `https`、hostname 必須、userinfo (`@`) 禁止。path は空または `/` のみ、query / fragment 禁止。hostname は小文字化され、`/` は除去される。|
| remote HTTP | `localhost`, `127.0.0.1`, `::1` 以外のホストでは拒否。remote は HTTPS が必要（エラー文は `remote monitoring requires HTTPS or a local SSH tunnel`）。|
| 不正 port | `urllib.parse` が port を解釈できない場合は `invalid server port` で拒否。|

環境変数値に独自の文字列 parse、大小文字変換、clamp はありません。`STRATA_URL` を指定した場合も接続先が起動中である保証はなく、実際の HTTP 通信時に接続エラーになり得ます。

Docker ラッパーでは shell の `${STRATA_URL:-...}` を使うため、未設定または空文字なら `http://127.0.0.1:${PORT:-8080}` を設定・export して `strata` を起動します。非空の値はそのまま維持されます（`docker/strata-wrapper.sh:5-10`）。

## 有効になる条件

- **端末クライアント**: 接続先選択が行われる `strata status`, `monitor`, `logs`, `config show` と `strata models list --served` で参照されます。ローカルのインストール済みモデル一覧には接続指定を使わず、`--url` 等の接続オプションを付けると `--served` が必要として CLI が拒否します（`strata_cli/monitor_commands.py:132-139,167-199`, `strata_cli/cli.py:564-588`）。
- **接続先の優先順位**: `--url` と `--connection` の同時指定はエラー。saved `--connection` は `STRATA_CONNECTION` より優先され、`--url` は環境変数で指定された接続より優先されます。どちらもなければ、非空の `STRATA_CONNECTION` が saved connection を選択し、それもなければ `STRATA_URL`、最後に既定 URL を使います。saved connection を選んだときはその保存 URL を使い `STRATA_URL` は使いません（`strata_cli/connections.py:273-291`; CLI の option 定義は `strata_cli/monitor_commands.py:20-26`, served models は `strata_cli/cli.py:569-570`）。
- **monitor / status / logs の起動中 launch 検出**: `--url` / `--connection` がなく、`STRATA_URL` と `STRATA_CONNECTION` の両方が falsy の場合だけ、source CLI は launch 情報を調べ、稼働中 launch の URL があればそれを明示 URL として解決します。空文字の `STRATA_URL` はこの検出条件を止めませんが、launch URL が得られない場合は通常の URL 検証で失敗します。thin monitor bundle では launch code がなく既定 URL へ進みます（`strata_cli/monitor_commands.py:36-46,193-199`）。
- **Docker**: `docker/strata-wrapper.sh` を経由した CLI だけに既定 URL 補完が適用されます。直接起動した CLI にはこの shell fallback はありません。
- **`apps/host/scripts`**: Node 起動時に一度だけ `process.env.STRATA_URL` を読みます。未設定時に `http://localhost:5199` を使う UI / 表示スクリプトは `flow.mjs`, `measure.mjs`, `motion.mjs`, `motionbudget.mjs`, `luminance.mjs`, `contrast.mjs`。未設定または空文字でエラーを stderr に出して exit 2 するスクリプトは `agent-http.mjs`, `agent3-http.mjs`, `agent2-flow.mjs`, `agent2-tools-flow.mjs`, `agent-flow.mjs`, `agent-flow-s4b.mjs`, `mode-flow-s4b.mjs`, `task-flow-s4b.mjs`, `tools-shots.mjs`。`skills-shot.mjs` は fallback や必須値チェックをせず、値をそのまま page URL に埋め込みます（各 read 箇所は後掲）。これらはサーバーの通常起動経路ではなく、画面検証・開発用スクリプトです。

## 実行時の詳細

端末クライアントでは、URL の選択は各コマンド処理時に環境辞書から行われます。`connections.resolve()` 自体は結果を cache しません。環境変数がプロセス起動後に変更された場合、以降に同関数を呼ぶコマンド処理では変更後の `os.environ` が見えます。`config show` は選択 URL と出所（`environment` / `default` 等）を返します。URL が `STRATA_URL` 由来の場合、`--url` がない限り出所はキーの存在で `environment` と判定されます（`strata_cli/connections.py:276-301`）。

解決した URL は status / monitor / logs では `Endpoint` の root になります。served model list でも同様です。`Endpoint` は telemetry 契約内のパスへ HTTP GET を発行し、credential があれば Bearer Authorization を付けます（`strata_cli/monitor_commands.py:196-203`, `strata_cli/cli.py:569-574`, `strata_cli/client.py:84-110`）。URL parse / 検証の `ValueError` は端末表示なら `strata: <message>` を stderr に出して code 2、JSON 系出力なら error JSON を出します。HTTP 側の `ClientError` はその例外の exit code で返します（`strata_cli/monitor_commands.py:231-240`）。

saved connection が選ばれた際の credential 名や `--credential-env` は動的な環境変数名として読みます。名前の形式は ASCII の `[A-Za-z_][A-Za-z0-9_]{0,127}` です。したがって設定によっては `STRATA_URL` 自体を credential 名に指定でき、その場合は `config show` が値の有無だけを確認し、通信コマンドが同じ値を Bearer credential として使います。これは URL 選択とは別の参照経路です（`strata_cli/connections.py:41-42,66-69,292-301`; `strata_cli/monitor_commands.py:198`; `strata_cli/cli.py:571-573`）。

Docker wrapper は子 `strata` に URL を export して `exec` します。Node helper scripts は module 初期化時に値を `BASE` へ読み込み、後続の `page.goto()` または `fetch()` で利用します。fallback `??` は未設定にだけ反応し、空文字には反応しません。必須チェックの `if (!BASE)` は未設定と空文字の双方を拒否します（例: `apps/host/scripts/flow.mjs:16,47`, `apps/host/scripts/agent3-http.mjs:13-22`）。Strata 側にはこれらの環境値を別プロセスへ継承・書き換える他の処理は見つかりませんでした。

## 根拠

- 接続解決、既定値、優先順位、credential の動的参照: `strata_cli/connections.py:273-303`。
- URL 検証と HTTP 接続先への適用: `strata_cli/client.py:45-64,84-110`。
- monitor / status / logs の起動中 launch 判定、Endpoint 作成、失敗出力: `strata_cli/monitor_commands.py:36-46,193-240`。
- served model list の接続先使用: `strata_cli/cli.py:564-588`。
- Docker wrapper の空値 fallback と export: `docker/strata-wrapper.sh:5-10`。
- UI / 計測スクリプトの未設定 fallback / 使用例: `apps/host/scripts/flow.mjs:16-19,47`, `measure.mjs:24`, `motion.mjs:26`, `motionbudget.mjs:24`, `luminance.mjs:29`, `contrast.mjs:23`。
- 必須 URL のチェックと HTTP 使用例: `apps/host/scripts/agent-http.mjs:13-14`, `agent3-http.mjs:13-22,34-37`, `agent2-flow.mjs:19-20`, `agent2-tools-flow.mjs:18-19`, `agent-flow.mjs:27-28`, `agent-flow-s4b.mjs:20-21`, `mode-flow-s4b.mjs:8`, `task-flow-s4b.mjs:8`, `tools-shots.mjs:11-12`。`skills-shot.mjs` の無検査 read は `apps/host/scripts/skills-shot.mjs:5,10-12`。
- `docs/TERMINAL.md:44` も CLI の接続優先順位を説明しており、上記実装と一致します。候補一覧は `docs/envvars/000_envvers.md` にありますが、そこに記載された名前だけから挙動は導いていません。
