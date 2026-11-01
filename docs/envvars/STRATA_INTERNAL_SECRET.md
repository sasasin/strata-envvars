# `STRATA_INTERNAL_SECRET`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

この名前は一般利用者が設定する Strata の機能オプションではなく、ホストが従来型 Time-skip の revision helper に渡す一時的な内部認証値です。ホストは起動時に `randomBytes(24).toString('hex')` で値を生成し、Time-skip 子プロセスの環境へ `STRATA_HOST_URL` と一緒に渡します。helper は値を `x-strata-internal` HTTP ヘッダーに載せ、ホストは受信値を自プロセス内の値と比較して内部 endpoint を認証します（`apps/host/server/index.mjs:779-780,1160-1165,1194-1198`、`apps/host/server/timeskip-revise.mjs:14-28`）。

## 値と判定

Strata は値を真偽値や数値へ変換しません。helper は `process.env.STRATA_INTERNAL_SECRET` を起動時に一度読み、JavaScript の truthiness だけで他の必須値とまとめて検査します。未設定または空文字なら revision helper は stderr に `The revision step needs the Strata app to be running.` を出し、終了コード 2 で終了します。空白だけを含む値など、空文字でない値はこの検査を通ります（`apps/host/server/timeskip-revise.mjs:14-21`）。

空でない値は変換せずリクエストヘッダーへ渡されます。ホスト側は受信ヘッダーを文字列から Buffer にし、起動時に生成した値とのバイト長が異なる場合、または `timingSafeEqual` が不一致の場合に HTTP 403 と `Not allowed.` を返します。一致した場合だけ endpoint の処理へ進みます（`apps/host/server/index.mjs:779-780,1194-1203`）。したがって、利用者が任意の値を設定して認証を通す仕組みではありません。正常値はホストが生成・注入した 48 桁の小文字16進表現です。

| helper の値 | helper の判定 | その後の扱い |
|---|---|---|
| 未設定 | falsy | ローカルでメッセージを出し終了コード 2 |
| 空文字 | falsy | 同上 |
| 空でない誤値 | truthy | ヘッダーに載せて送信し、通常はホストから HTTP 403。helper は応答本文の `Not allowed.` を stderr に出し終了コード 1 |
| ホストが注入した値 | truthy | 認証比較を通過し、残りの endpoint 条件を満たせば revision turn を実行 |

この変数に関する CLI 引数や別環境変数との優先順位はありません。helper 起動時に値を読み取るため、その後の環境変更は反映されません。ホストの秘密値も `index.mjs` のモジュール評価時に一度生成され、同じホストプロセスの間使われます（`apps/host/server/index.mjs:779-780`）。

## 有効になる条件

- ホストが従来型 `/api/timeskip/start` 経路（`body.legacy !== true` ではない経路）で revision job を始めること。この経路は `TIMESKIP_REVISE` を revision command として選び、`startDetached` に内部 URL と秘密値を渡します（`apps/host/server/index.mjs:1132-1152,1160-1165`）。
- revision command が設定されていること。`body.useAgent === false` の場合は `reviseCommand` が `null` になり、Time-skip コマンドに `--revise-command` を加えないため、標準の Node helper は呼ばれません（`apps/host/server/index.mjs:1152`、`apps/host/server/timeskip.mjs:446-455`）。`STRATA_TIMESKIP_REVISE` が設定されていると標準 helper 以外の command が選ばれる場合もあります（`apps/host/server/index.mjs:777-778`）。
- 標準 helper では `STRATA_HOST_URL`、`STRATA_INTERNAL_SECRET`、`STRATA_TIMESKIP_PROMPT` のすべてが空でないこと。prompt はこの変数とは別に helper の事前検査対象です（`apps/host/server/timeskip-revise.mjs:14-21`）。
- リクエストが `/api/internal/timeskip-revise` に届き、ヘッダー値がホスト内の秘密値と一致すること。認証後も `cwd` が Time-skip 状態ディレクトリ配下であること、利用可能なモデル選択があることが必要です。条件を満たさなければそれぞれ HTTP 400 (`That folder is not part of a Time-skip run.`) または HTTP 503 (`Load a model first, then try Time-skip again.`) になります（`apps/host/server/index.mjs:1195-1207`）。

ソースに OS/backend/build macro による条件分岐はありません。この値が渡されるのは同じホストが起動した Time-skip 子プロセスの環境です。`startDetached` は親の `process.env` を基に環境を複製し、`extraEnv` を重ねてから `STRATA_TIMESKIP_DIR` を指定します（`apps/host/server/timeskip.mjs:446-455`）。

## 実行時の詳細

ホストは各プロセス起動時に 24 バイトの乱数を 48 文字の16進文字列へ変換します。従来型 Time-skip の開始時、`extraEnv` の同名キーとしてこの値を子プロセス環境へ渡します。子プロセスから実行される Node helper は起動時に URL・秘密値・prompt を定数へ読み込み、POST の `x-strata-internal` ヘッダーに秘密値を設定します。値を永続化する処理や、CLI から上書きする処理はありません（`apps/host/server/index.mjs:779-780,1152,1160-1165`、`apps/host/server/timeskip.mjs:446-455`、`apps/host/server/timeskip-revise.mjs:14-28`）。

helper は HTTP エラー応答で JSON の `error` を stderr に出して終了コード 1 にします。ネットワーク例外では `The assistant could not be reached: ...`、error frame ではその message、result を受け取らず stream が終わった場合は `The assistant stopped before it finished.` を stderr に出し、それぞれ終了コード 1 です。正常な result は stdout に出して終了します（`apps/host/server/timeskip-revise.mjs:30-57`）。サーバー側は認証後、NDJSON stream を開始して assistant turn を実行します（`apps/host/server/index.mjs:1207-1232`）。

## 根拠

- 全参照を `rg -n --hidden --glob '!.git/**' 'STRATA_INTERNAL_SECRET'` で確認した。実装上の環境読み取りは `apps/host/server/timeskip-revise.mjs:15` の一箇所で、ホスト側の `apps/host/server/index.mjs:1164` は子プロセス環境への設定、`index.mjs:780` は内部値の生成である。その他の参照は `apps/host/tests/timeskip-real.test.mjs:145,154-157` のテスト用子プロセス環境・期待値であり、本番挙動の根拠にはしていない。
- helper の不足値・誤値・通信失敗の出力と終了コードを検証するテスト記述は `apps/host/tests/timeskip-real.test.mjs:149-158` にある。調査ではテストを実行していない。
- `docs/DETAILS.md` にこの内部変数の追加説明は見つからなかった。以上の説明は対象 commit の実装に基づく。
