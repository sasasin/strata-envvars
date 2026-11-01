# `STRATA_PREVIEW_HOST_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host` の `npm run preview:ui` が起動する、隔離されたプレビュー用 Strata host の待受ポートを指定します。通常のアプリ設定ではなく、UI プレビュー用スクリプトだけがこの名前を読みます。`apps/host/package.json:26` が `preview:ui` を `node scripts/preview-ui.mjs` に割り当て、`apps/host/README.md:5-10` がこのコマンドを案内しています。

## 値と判定

スクリプトは `Number(process.env.STRATA_PREVIEW_HOST_PORT ?? 8792)` で一度数値に変換します（`apps/host/scripts/preview-ui.mjs:9`）。

| 値 | 結果 |
|---|---|
| 未設定 | `??` の右辺が使われ、`8792`。 |
| 空文字 | nullish ではないため `Number('')` の結果 `0`。 |
| 数値文字列 | `Number` が文字列全体を数値変換した値を使う。部分的な数値読み取りや範囲 clamp はこのスクリプトにない。 |
| 数値に変換できない文字列 | `NaN` が得られ、検証・fallback なしに子 host の `STRATA_PORT` とヘルスチェック URL に使われる。 |
| `0` | ポート 0 として子 host に渡される。プレビュー側のヘルスチェックも `127.0.0.1:0` を参照するため、起動確認に成功しない。 |

負数、小数、65535 を超える数などに対する独自の境界検査はありません。値は子 host の `server.listen()` に届きます（`apps/host/server/index.mjs:100,2262`）。この設定は CLI 引数や別設定との優先順位を解決せず、プレビュー用スクリプトが子プロセスの `STRATA_PORT` を明示的に上書きします（`apps/host/scripts/preview-ui.mjs:13`）。

## 有効になる条件

- `apps/host` で `npm run preview:ui` を実行したときに限り読み取られます。通常の `server/index.mjs` はこの変数を参照しません。
- Node.js のスクリプトとして動作し、OS や CUDA/HIP/SYCL backend、モデル状態には依存しません。
- `dist/index.html` がなければスクリプトは `Run npm run build before starting the UI preview.` を stderr に出して終了します。ポート値自体は先に計算されますが、子 host には渡されません（`apps/host/scripts/preview-ui.mjs:9,15-16`）。
- `STRATA_BIND` は継承され、host の bind address に使われます。一方、プレビュー用スクリプトのヘルスチェック先は固定で `127.0.0.1` です。そのため `STRATA_BIND` を別アドレスにすると、host が listen してもプレビュー側が起動を確認できないことがあります（`apps/host/scripts/preview-ui.mjs:13,19`; `apps/host/server/index.mjs:101,2262`）。

## 実行時の詳細

値はプレビュースクリプトの起動時にトップレベルで一度評価され、子 host 起動時に `STRATA_PORT: String(hostPort)` として渡されます。続いて同じ数値を `http://127.0.0.1:<port>/api/health` のポーリングに使います（`apps/host/scripts/preview-ui.mjs:9,13,16-22`）。実行中に親プロセスの環境を変更しても、既に計算された `hostPort` は再評価されません。host 自体も起動時に `STRATA_PORT` を数値化して `PORT` に保持し、その値で listen します（`apps/host/server/index.mjs:100,2262`）。通常の host 既定ポートは `8791` ですが、このプレビューラッパーは `STRATA_PORT` を設定して既定 `8792` を使います。

ポート競合や listen 失敗を host が非同期の `error` として受け取った場合、`[strata] ...` を stderr に出し、終了コード 1 で終了します（`apps/host/server/index.mjs:2256-2261`; 文言生成は `apps/host/server/ports.mjs:5-10`）。子プロセスの終了はプレビュースクリプトに伝わり、子を停止して同じ終了コードで親も終了します。host が終了せずヘルスチェックにも応答しない場合は最大100回（各回150 ms）の後、`The isolated preview host did not start. Check the port and console output.` を stderr に出して終了します（`apps/host/scripts/preview-ui.mjs:12,17-22`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:1327-1330`。
- 唯一の直接読み取り、変換、子プロセスへの受け渡し、ヘルスチェック: `apps/host/scripts/preview-ui.mjs:9-25`。
- コマンド登録と利用案内: `apps/host/package.json:26`; `apps/host/README.md:5-10`。
- host のポート取得、listen、listen error の終了処理: `apps/host/server/index.mjs:100-101,2256-2266`; `apps/host/server/ports.mjs:5-10`。
