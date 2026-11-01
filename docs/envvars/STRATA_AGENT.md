# `STRATA_AGENT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の Node ホストがチャット要求を agent 実行系へ渡すかを制御します。`apps/host/server/index.mjs` の `/api/chat/stream` と `/api/plan/start-goal` の共通処理が値を参照します。`off` の場合はその要求を `runAgentTurn` に渡さず、通常の `runTurn` 経路へ進めます。これは agent 経路の切り替えであり、サーバー全体の停止やモデル要求の無効化ではありません。

## 値と判定

値は `process.env.STRATA_AGENT === 'off'` で文字列全体を比較します。大文字小文字を区別し、trim や真偽値・数値への変換はありません。

| 値 | agent 経路の扱い |
|---|---|
| 未設定 | `off` ではない。ほかの条件が満たされれば agent 経路を試す |
| 空文字 | `off` ではない。ほかの条件が満たされれば agent 経路を試す |
| 完全一致の `off` | agent 経路を使わず、通常のチャット処理へ進む |
| `OFF`、`0`、`false`、` off`、`off ` など | `off` ではない。ほかの条件が満たされれば agent 経路を試す |

既定値を文字列として設定するコードはなく、未設定時はこの完全一致判定により agent が禁止されません。値はリクエスト処理のたびに参照され、static 変数などへの cache はありません。コード上、プロセス起動後に `process.env` の値を変更した場合も次の要求では再判定されます。

## 有効になる条件

`STRATA_AGENT` が `off` 以外でも、agent を使うには、要求に空でない `sessionId` があり、要求の `agent` と `tools` のどちらも boolean `false` ではなく、`remoteModel` が指定されているか `native.hasLive()` が真である必要があります。条件を満たす要求では `agent.status()` も確認し、状態が `unavailable` でなければ `runAgentTurn` を実行します。状態が `unavailable` なら agent を実行せず、通常の `runTurn` に続きます。

ここでの `false` 判定は厳密な boolean 比較です。たとえば `agent: "false"` や `tools: 0` はこの判定では opt-out になりません。`STRATA_AGENT=off` は `agent` / `tools` の値より先に判定され、agent 経路を無効にします。OS、GPU backend、build macro による分岐はこの実装箇所にはありません。

## 実行時の詳細

`off` のときは agent 呼び出し条件に入らず、後続の `runTurn` に要求を渡します。`runTurn` は指定された API model があれば remote 経路へ、native model が稼働していれば native 経路へ、そうでなければ runtime model 経路へ振り分けます。したがって、この環境変数が直接変更するのはチャット要求の agent 分岐であり、通常のモデル応答経路は残ります。

agent を使わない理由の notice は、`sessionId` があり、要求側で `agent: false` / `tools: false` を指定しておらず、かつ環境変数が `off` 以外の場合に `agent-skipped` として NDJSON ストリームへ書かれます。そのため `STRATA_AGENT=off` 自体についてはこの notice は出ません。agent が利用不能の場合は別に `agent-unavailable` notice を出してから通常の `runTurn` へ進みます。この環境変数を理由とする stderr / stdout ログ、終了処理、エラー応答は実装されていません。通常の `runTurn` でモデル解決等に失敗した場合は、その経路の `error` frame が返ります。

## 根拠

- `apps/host/server/index.mjs:1980-1982` — `/api/chat/stream` と `/api/plan/start-goal` の共通要求処理。
- `apps/host/server/index.mjs:2001-2008` — agent 実行を見送る条件と `STRATA_AGENT` の完全一致判定。
- `apps/host/server/index.mjs:2009-2021` — agent の利用可能性確認、agent 実行、`agent-unavailable` / `agent-skipped` notice。
- `apps/host/server/index.mjs:2023-2038` — agent を使わない場合の `runTurn` 呼び出し。
- `apps/host/server/index.mjs:649-665` — 通常の `runTurn` の remote / native / runtime model 選択とモデル解決失敗の frame。

`000_envvers.md` にある同名候補のほか、本番コードで確認した読み取り箇所は上記の 2 箇所です。テストではホスト起動時に `STRATA_AGENT: 'off'` を設定していますが、テスト内の値は実装挙動の根拠には用いていません。調査対象ソース内の設計資料に、この環境変数の追加説明は見つかりませんでした。
