# `STRATA_SHARE_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数動作は対象外。

## 役割

Strata host の「ローカル共有」HTTP listener が使うポートの優先値を指定します。host 本体の `STRATA_PORT` とは別の listener で、共有 listener は `0.0.0.0` に bind します。起動時にポートを選びますが、共有 listener が実際に listen を始めるのは共有を有効にした時です。

## 値と判定

`apps/host/server/index.mjs` は、変数が未設定 (`undefined`) のとき `PORT + 1` を使い、それ以外は JavaScript の `Number()` で数値化して `findFreePort()` に渡します。空文字は `Number('') === 0` なので未設定時の既定値にはなりません。文字列全体の整数検査や明示的な範囲検査はありません。

| 入力 | 優先ポート値 | `findFreePort()` の結果 |
|---|---:|---|
| 未設定 | host の `PORT + 1`（`STRATA_PORT` 未設定時は 8792） | 優先値から上へ最大20個試し、見つからなければ一時ポートを要求する |
| 空文字、`0` | 0 | `listen(0, ...)` で OS が割り当てたポートを返す |
| 有効な数値文字列 | `Number()` の数値 | 値から上へ最大20個試し、使えなければ一時ポートを要求する |
| 数値に変換できない文字列 (`NaN`)、負数、小数 | `Number()` の結果 | 候補が `skip` されず `listen()` に渡された場合、同期例外で `tryListen()` の Promise が reject し、`findFreePort()` からも reject する。候補探索や port 0 fallback には進まない |
| 65535 を超える値 (`Infinity` を含む) | `Number()` の結果 | 各候補が範囲判定で飛ばされ、port 0 の probe に進む |

`Number()` のため、前後の空白を含む数値や JavaScript が数値に変換できる形式も変換対象です。`findFreePort()` は優先値から `preferred` 〜 `preferred + 19` を順に試し、`STRATA_PORT` と同じ値は除外します。候補 port が 65535 を超えるとその候補を飛ばします。通常の bind error は `tryListen()` が `null` にして次候補へ進めます。候補を使えない場合は port `0` で試し、それも失敗した場合は優先値を返します。ただし `NaN`、負数、小数のように `listen()` が同期例外を出す値では、候補が `skip` に一致しなければ `tryListen()` の Promise が reject し、`findFreePort()` の探索自体が中断します。`STRATA_PORT` も `NaN` である場合は `skip: [PORT]` に一致した候補が飛ばされ、port `0` fallback へ進むことがあります。共有ポート探索は top-level `await` であり、この reject 時は後続の host `server.listen()` に到達しません。

## 有効になる条件

- GPU backend、モデルのロード状態、build macro、OS 固有の分岐は、この値の読み取り・ポート選択には条件として使われていません。
- `STRATA_PORT` は共有ポート候補から除外されます。`STRATA_PORT` 自体は `STRATA_SHARE_PORT` 未設定時の既定値計算にも使われます。CLI 引数による共有ポート指定はこの読み取り箇所にありません。
- 起動時の空きポート確認は共有機能を有効にする前に行われます。ただし probe は port を開いて閉じるため、選択後に別プロセスが先に使う競合はあり得ます。共有 listener が bind されるのは `/api/serving/share` への POST で `enabled === true` のときだけです。

## 実行時の詳細

host server のモジュール初期化時に `process.env.STRATA_SHARE_PORT` を一度読み、`Number()` に変換し、`0.0.0.0` 上で空きポートを探索します。実行中に環境変数を変更しても、この選択は再評価されません。選んだ番号は `createLocalShare()` に渡され、共有 listener の `listen(port, host)` に使われます。停止後に再度共有を開始する場合も同じ選択済みポートを使います。

共有開始時の bind が失敗すると listener を閉じて内部参照をクリアし、`listenProblem()` が作るエラーを投げます。API route はこれを HTTP 400 の応答にします。共有 listener の通常経路では、競合ポートは探索中にスキップされるため次の候補へ進みます。候補探索後の競合など bind 時点の `EADDRINUSE` は `Port <port> is already in use...`、`EACCES` はポート利用拒否の説明を含むエラーになります。Strata はこれらを `/api/serving/share` のエラー応答に載せます。

## 根拠

- `apps/host/server/index.mjs:100-101,2262` — host port (`STRATA_PORT`) の値と既定値、および host server の listen 開始位置。
- `apps/host/server/index.mjs:944-948` — 共有 listener 用ポートの探索、`STRATA_PORT` の除外、選んだ値の受け渡し、および tunnel port からの除外。
- `apps/host/server/ports.mjs:13-18,22-30` — port probe、20候補の探索、skip 判定、port 0 fallback。
- `apps/host/server/local-share.mjs:8-14,34-44` — listener の既定 bind host、開始・停止時の bind 処理。
- `apps/host/server/index.mjs:1593-1595` — 共有開始・停止 API と bind error の HTTP 400 応答。
- `apps/host/server/ports.mjs:4-10` — bind error のメッセージ組み立て。
