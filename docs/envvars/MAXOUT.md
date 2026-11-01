# `MAXOUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`MAXOUT` は Strata のエンジンが直接読む環境変数ではありません。Strata ホストを HTTP 経由で操作する補助スクリプト `apps/host/scripts/agent-http.mjs` が、`connect` コマンドでカスタム API 接続を登録するときに読みます。値はモデルの `maxOutput` として `/api/model-providers` に送られ、保存された API モデルの出力予算に使われます。スクリプトのヘッダーは `agent3-http.mjs` を実行例として記載していますが、調査対象の実ファイル名は `agent-http.mjs` です（`apps/host/scripts/agent-http.mjs:1-14,79-82`）。

## 値と判定

スクリプトは値の有無を JavaScript の truthy 判定で調べ、truthy なら `Number(process.env.MAXOUT)` を `maxOutput` に入れます。文字列全体の数値パースや整数限定はしていません。

| `MAXOUT` | スクリプトが送る値 | ホストの保存値・出力予算 |
|---|---|---|
| 未設定 | `maxOutput` をリクエストから省略 | `null` に正規化。出力予算は既定計算 |
| 空文字 | `maxOutput` を省略（空文字は falsy） | `null` に正規化。出力予算は既定計算 |
| `0` または数値変換結果が 0（例: 空白だけの文字列） | 数値 `0` | `0` を保存するが、出力予算関数は `maxOutput > 0` の場合だけ使うため既定計算 |
| 正の有限数 | `Number()` が返す数値 | 非負有限数として保存。出力予算に採用され、整数に切り下げた後、少なくとも 1024、かつコンテキスト窓内の上限以下に制限 |
| 負数 | 負の数値 | ホストが `null` に正規化し、出力予算は既定計算 |
| 数値に変換できない文字列、`Infinity` など | `NaN` / 非有限数は JSON 化で `null` | ホストが `null` として扱い、出力予算は既定計算 |

JavaScript の `Number()` のため、たとえば `1e4` や `0x10` は数値として変換されます。`MAXOUT=0` は falsy ではなく数値 0 として送られます。正の値でも、保存 API は有限かつ 0 以上かだけを検証し、モデル固有上限との照合はしません（`apps/host/scripts/agent-http.mjs:81`, `apps/host/server/model-providers.mjs:51,86-98`）。

## 有効になる条件

- `apps/host/scripts/agent-http.mjs` を `connect <baseUrl> <modelId>` で起動した場合だけ `MAXOUT` の分岐を通ります。他のスクリプトコマンドでは参照されません（`apps/host/scripts/agent-http.mjs:79-86`）。
- スクリプト全体の前提として `STRATA_URL` が必要です。未設定なら `MAXOUT` を使う `connect` 分岐に入る前に stderr に `STRATA_URL is required` を出して終了コード 2 で終了します（`apps/host/scripts/agent-http.mjs:13-15`）。
- `baseUrl` と `modelId` は CLI 位置引数で、`MAXOUT` に対応する CLI 引数や別環境変数による上書きはありません（同 `:79-81`）。
- ホスト API は `maxOutput` を非負の有限 JavaScript number のみ保持し、それ以外を `null` にします。接続保存に成功すると `model-providers.json` に永続化されます（`apps/host/server/index.mjs:1065-1067`, `apps/host/server/model-providers.mjs:51,64-68,88-98`）。

## 実行時の詳細

`MAXOUT` は Node.js スクリプト実行中に `connect` 分岐で参照され、キャッシュや後続プロセスへの環境変数転送はありません。値そのものではなく変換後の `maxOutput` が JSON リクエストでホストへ渡ります。設定 API が受け取ったモデル行は `maxOutput` を含む形に正規化され、接続データとして保存されます。

保存済み接続からエージェント用プロファイルを作る際、モデルの `maxOutput` が正の有限数なら `outputBudget()` が `floor(maxOutput)` を計算し、1024 を下回らず、コンテキスト窓からプロンプト用領域を引いた上限を超えないようにします。未設定、0、無効値なら既定値 32768 を同じ窓上限で制限します（`apps/host/server/agent/profile.mjs:172-184,250-287`）。この予算はエージェント用モデルプロファイルの `maxTokens` です。通常の API チャットストリームを作る `model-providers.mjs` の payload には、この値を `max_tokens` として直接設定する処理はありません（同 `:146-168`）。

保存 API が失敗したとき、スクリプトは `/api/model-providers -> <status> <error>` の形式で例外を作ります。接続保存の成功時は stdout に `saved` を出します（`apps/host/scripts/agent-http.mjs:18-23,79-82`; API 側 `apps/host/server/index.mjs:1065-1067`）。

## 根拠

- `apps/host/scripts/agent-http.mjs:1-15,18-23,79-86` — 対象スクリプト、`STRATA_URL` の必須確認、HTTP エラー処理、`MAXOUT` の読み取りと JSON 送信、`connect` コマンド条件。
- `apps/host/server/index.mjs:1065-1067` — 接続保存 API の処理とエラー応答。
- `apps/host/server/model-providers.mjs:51,64-68,86-100` — `maxOutput` の型・範囲検証、保存処理。
- `apps/host/server/agent/profile.mjs:172-184,250-287` — エージェント用出力予算の既定値、clamp、および `maxTokens` への反映。
- 調査対象 commit の `docs/` と `apps/host/docs/` では `MAXOUT` または `maxOutput` の追加説明を確認できませんでした。
