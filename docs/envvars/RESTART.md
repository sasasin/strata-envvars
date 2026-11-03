# `RESTART`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`RESTART` は Strata の実行エンジンやサーバー設定ではなく、同梱の `docker/smoke-test.sh` がコンテナを一度停止した後、同じコンテナを再起動した後の serving 確認を実行するかどうかを決めます。スクリプトは成功時に `restart reuses /data` と表示しますが、実装上の判定は `/v1/models` が HTTP 200 を返すことです。Strata プログラム本体に対する `RESTART` の環境変数読み取りは見つかりませんでした。スクリプトの説明も smoke test のチェック項目に restart を挙げています（`docs/DOCKER.md:301`）。

## 値と判定

スクリプトは Bash の `${RESTART:-1}` を使い、展開した文字列を `1` と完全一致で比較します（`docker/smoke-test.sh:94`）。`:-` は未設定または空文字のとき既定値 `1` を使うため、どちらも追加チェックを有効にします。

| `RESTART` | 判定 | 動作 |
|---|---|---|
| 未設定 | 有効（既定値 `1`） | 2回目の起動チェックを実行 |
| 空文字 | 有効（`:-1` により `1`） | 2回目の起動チェックを実行 |
| `1` | 有効 | 2回目の起動チェックを実行 |
| その他すべて（例: `0`, `01`, `true`, ` 1`） | 無効 | 2回目の起動チェックをスキップ |

数値変換や前後空白の除去、大文字小文字の変換はありません。CLI 引数による上書きもありません。なお `set -u` が有効ですが、未設定値は `${RESTART:-1}` で処理されるため未定義変数エラーにはなりません（`docker/smoke-test.sh:10,94`）。

## 有効になる条件

この変数を読むのは Docker smoke test スクリプトだけです。値が有効でも、先行する smoke test が失敗して途中で `exit 1` した場合、2回目の起動チェックまでは到達しません（`docker/smoke-test.sh:33-44,94`）。Strata の server/runtime の再起動間隔に使われる `RESTART_RETRY_S` はクラス属性であり、環境変数 `RESTART` の読み取りではありません（`serve/server.py:1432,1475-1476`）。

## 実行時の詳細

スクリプトは実行中、コンテナの最初の停止・終了確認と GPU/プロセス確認を済ませた後、`RESTART` を一度評価します。値が有効なら `docker start` し、`WAIT` 秒（未設定時 2400 秒）を上限として認証付き `GET /v1/models` が HTTP 200 になるまで10秒間隔で確認します。200 になれば `PASS: restart reuses /data` と表示し、コンテナをもう一度停止します。`/data` の内容や preset の再利用そのものを別途比較する処理はありません（`docker/smoke-test.sh:82-105`）。この判定はスクリプト実行中の環境からこの位置で行われ、後続ループで再評価されません。

`docker start` の終了ステータス自体は判定せず、HTTP 応答で起動を確認します。2回目の起動確認が `WAIT` を超えると `FAIL: second start not serving` を記録して失敗フラグを立てます。その後もスクリプトは後処理と最終結果表示へ進み、最後に失敗フラグが立っていれば終了コード 1、なければ 0 で終了します。全出力は `test.log` に追記され、標準出力・標準エラーにも tee されます（`docker/smoke-test.sh:17,20-22,100-107`）。`RESTART` が無効なら2回目の起動・再利用チェックは無出力でスキップされますが、先行する smoke test とその最終結果は通常どおり実行されます。

## 根拠

- `docker/smoke-test.sh:1-17` — Bash スクリプト、必須入力、`WAIT` 既定値、ログ出力。
- `docker/smoke-test.sh:20-22,33-44` — 失敗フラグと、先行チェック失敗時の終了経路。
- `docker/smoke-test.sh:82-107` — 初回停止後の `RESTART` 判定、2回目の起動・HTTP 確認・timeout・最終終了コード。
- `docs/DOCKER.md:301` — smoke test が restart を含む実カード向けチェックであるとの説明。
- `serve/server.py:1432,1475-1476` — 類似名 `RESTART_RETRY_S` は server の属性参照であること。
