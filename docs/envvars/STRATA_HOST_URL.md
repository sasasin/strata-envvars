# `STRATA_HOST_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Time-skip の既定のエージェント修正コマンド `apps/host/server/timeskip-revise.mjs` が、修正要求を Strata ホスト内の `/api/internal/timeskip-revise` に POST する接続先です。ホスト本体がこの環境変数を読むのではなく、レガシー Time-skip 実行の起動時に `http://127.0.0.1:${PORT}` を子プロセスへ注入し、修正スクリプトが読み取ります（`apps/host/server/index.mjs:1152-1165`, `apps/host/server/timeskip-revise.mjs:14,24-29`）。

## 値と判定

| 状態 | `timeskip-revise.mjs` の扱い |
|---|---|
| 未設定 | `base` は `undefined`。他の必須値とともに初期チェックで失敗し、stderr に `The revision step needs the Strata app to be running.`、終了コード 2。 |
| 空文字 | `base` は falsy として未設定と同じ初期チェック失敗。 |
| 空でない文字列 | 形式検証、URL parse、trim、末尾スラッシュ除去はせず、`${base}/api/internal/timeskip-revise` にそのまま連結して `fetch`。 |
| 不正な URL、接続失敗など | `fetch` の例外を catch し、stderr に `The assistant could not be reached: ${e.message}`、終了コード 1。 |

URL の形式・host・port の境界値をこのスクリプト自身が検査する処理はありません。値を `Number` 等で変換することもありません。通常のホスト起動経路では、親プロセスが `PORT` から loopback URL を作って子プロセス用環境へ渡します。そのため、親プロセスに同名変数が設定されていても、ここではその値を上書きします（`apps/host/server/index.mjs:100,1160-1165`; `apps/host/server/timeskip.mjs:454-456`）。

## 有効になる条件

- 組み込み Node 修正スクリプトが実行される必要があります。ホストは既定で `timeskip-revise.mjs` を `--revise-command` に指定しますが、`STRATA_TIMESKIP_REVISE` でコマンドを差し替えられます。差し替え先がこの環境変数を読まなければ、本変数による接続動作はありません（`apps/host/server/index.mjs:774-778,1152`）。
- レガシー Time-skip API 経路では `body.useAgent === false` の場合に修正コマンドを指定しません。組み込み修正スクリプトが起動しないので、本変数は使われません（`apps/host/server/index.mjs:1132-1137,1152-1165`）。新しい通常経路は別の fork runner を使います（`apps/host/server/index.mjs:1137-1150`）。
- OS、GPU backend、モデル状態による URL 判定の違いはありません。モデル選択の成否は本変数の parse には影響せず、接続先の内部 API が選択状態を調べます（`apps/host/server/index.mjs:1195-1206`）。

## 実行時の詳細

`timeskip-revise.mjs` はモジュール評価時に `process.env.STRATA_HOST_URL` を `const base` に読み込みます。プロセス起動後に環境を変更しても再読込しません（`apps/host/server/timeskip-revise.mjs:14-17`）。初期チェックでは `base` に加え `STRATA_INTERNAL_SECRET` と `STRATA_TIMESKIP_PROMPT` も truthy であることを要求します。いずれかが欠けるか空なら URL へのアクセス前に終了コード 2 となります（同:14-21）。

組み込み経路では、ホストが生成した `http://127.0.0.1:${PORT}` と内部 secret を Time-skip CLI の子プロセス環境へ渡します。子スクリプトは URL の `/api/internal/timeskip-revise` へ JSON POST し、secret を `x-strata-internal` ヘッダーに、作業ディレクトリ・prompt・attempt を本文に含めます（`apps/host/server/index.mjs:100,1160-1165`; `apps/host/server/timeskip.mjs:446-456`; `apps/host/server/timeskip-revise.mjs:24-29`）。この環境注入は起動時のものであり、URL の優先順位を決める CLI 引数はありません。

内部 API は secret を timing-safe に照合し、不一致なら HTTP 403 と `Not allowed.` を返します。作業ディレクトリが当該 Time-skip の候補フォルダー外なら HTTP 400、モデルを選べない場合は HTTP 503 を返します（`apps/host/server/index.mjs:1194-1206`）。スクリプトは HTTP 成功でない場合または応答 body がない場合、JSON の `error` を stderr に出して終了コード 1 にします。成功時は NDJSON の `result` を stdout に出し、`error` を受けた場合や結果なしで stream が終わった場合は stderr に失敗内容を出して終了コード 1、fetch 自体が失敗した場合も終了コード 1 です（`apps/host/server/timeskip-revise.mjs:30-57`）。

## 根拠

- 読み取り・初期判定・リクエスト URL 生成・失敗処理: `apps/host/server/timeskip-revise.mjs:14-57`。
- 通常の既定コマンドと `STRATA_TIMESKIP_REVISE` による差し替え、レガシー API の分岐、子プロセスへの URL 注入: `apps/host/server/index.mjs:774-780,1132-1165`。
- 子プロセス環境の合成と URL 注入値の優先: `apps/host/server/timeskip.mjs:446-456`。
- URL が到達する内部 API の認証、候補フォルダー確認、モデル状態確認: `apps/host/server/index.mjs:1194-1206`。
- `STRATA_HOST_URL` の他のリポジトリ参照は、スクリプトを起動して接続・失敗を確認するテストです（`apps/host/tests/timeskip-real.test.mjs:126-158`）。テストコードは実装動作の根拠ではなく、環境変数の読み取り箇所は上記の本番スクリプト一箇所です。
