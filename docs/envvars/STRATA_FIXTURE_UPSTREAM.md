# `STRATA_FIXTURE_UPSTREAM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの開始時点の作業ツリーは `## main...origin/main` で、未コミット変更は表示されませんでした。

## 役割

`apps/host/tests/ui-fixture-host.mjs` を手動起動したとき、fixture API proxy の転送先 URL を指定します。これは Strata app host の設定ではなく、同ファイルのコメントも「manual CUA review」用で app host では使わないと説明しています。Strata の検証文書もこの proxy を test helper と位置づけています（`apps/host/tests/ui-fixture-host.mjs:1-3`、`apps/host/docs/persona-review-2026-10-05/implementation-verification.md:54-56`）。

候補一覧 `docs/envvars/000_envvers.md:798-800` には掲載されています。実際に環境から値を読む箇所は `apps/host/tests/ui-fixture-host.mjs:8` の 1 箇所で、通常の app host や他の Strata 実装からの参照はありません。

## 値と判定

コードは値を parse、検証、trim せず、`process.env.STRATA_FIXTURE_UPSTREAM ?? 'http://127.0.0.1:8794'` で既定値を選びます。

| 環境値 | `upstreamUrl` の値 | 結果 |
|---|---|---|
| 未設定 | `http://127.0.0.1:8794` | loopback の既定先を使う |
| 空文字 | 空文字 | 既定値に置き換えず、空文字のまま使う |
| その他の文字列 | 指定文字列そのまま | URL の妥当性や scheme をここでは確認しない |

受け取った文字列は各転送先 URL に連結されます（通常の要求では `upstreamUrl + req.url`、`failed-load` シナリオの POST `/load` では `upstreamUrl + '/api/models'`）。末尾 slash の補正や URL join は行われません。そのため、パスの連結結果も入力文字列と要求パスの単純な連結です（`apps/host/tests/ui-fixture-host.mjs:35-41`）。

## 有効になる条件

- この値を使うのは `node tests/ui-fixture-host.mjs` による fixture utility の起動時です。通常の app host はこのファイルを使いません（`apps/host/tests/ui-fixture-host.mjs:1-3`、`apps/host/docs/persona-review-2026-10-05/implementation-verification.md:56`）。
- 同 utility は別変数 `STRATA_FIXTURE_FILE` が truthy でなければ `Provide a disposable fixture JSON path.` で例外終了します。これは upstream の値によらない起動条件です（`apps/host/tests/ui-fixture-host.mjs:7-10`）。
- OS、GPU backend、build macro、CLI オプションによる `STRATA_FIXTURE_UPSTREAM` の分岐はありません。

## 実行時の詳細

`upstreamUrl` は module evaluation 時に一度読み込まれ、トップレベル定数に保持されます。起動後にプロセス環境を書き換えても再読込しません。受信要求ごとに upstream へ `fetch` し、通常経路では要求 URL と連結した宛先を使います。`failed-load` シナリオの POST `/load` は upstream の `/api/models` を取得します（`apps/host/tests/ui-fixture-host.mjs:7-9,35-41`）。

転送先へ `fetch` できないなど、要求処理内で例外が発生した場合は catch 節が応答 header 未送信時に HTTP 500 を設定し、例外文字列を body として返します。upstream 応答を受けた通常経路では、ステータスと content type を downstream に渡し、JSON は fixture 変換を適用して返します。起動成功時は `Disposable CUA fixture host: http://127.0.0.1:<port>` を console に出します。`STRATA_FIXTURE_UPSTREAM` 固有の警告やログはありません（`apps/host/tests/ui-fixture-host.mjs:58-63`）。

## 根拠

- 環境値の読み取りと既定値: `apps/host/tests/ui-fixture-host.mjs:7-10`
- 転送先としての利用、例外応答、起動ログ: `apps/host/tests/ui-fixture-host.mjs:29-41,58-63`
- fixture utility が app host の依存ではない旨: `apps/host/docs/persona-review-2026-10-05/implementation-verification.md:54-56`
