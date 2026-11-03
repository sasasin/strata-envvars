# `E2E_RAW_CAP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/agent-lost-e2e.mjs` の `raw` シナリオがモデルサーバーへ送る chat completions リクエストの `max_tokens` を指定します。Strata エンジン本体や通常の CLI / サーバー起動設定を制御する変数ではなく、この E2E スクリプト専用です。シナリオ引数に `raw` を含めたときにだけ参照されます。引数を省略すると全シナリオが選択されるため、その場合も `raw` が実行されます（`apps/host/scripts/agent-lost-e2e.mjs:40-41,141-146`）。

## 値と判定

値は共通 helper `env(name, fallback)` で読み、未設定のときだけ文字列 `'700'` を既定値として使います。空文字は nullish ではないため既定値には戻らず、`Number(...)` で数値に変換されます（`apps/host/scripts/agent-lost-e2e.mjs:29-30,143`）。

| 環境値 | スクリプトが作る `max_tokens` 値 |
|---|---|
| 未設定 | `700` |
| `''` または空白のみ | `0`（`Number` の変換結果） |
| 数値として変換できる文字列 | JavaScript `Number` の数値。小数、指数表記、`0x` なども数値に変換される形式ならその値 |
| 数値に変換できない文字列 | `NaN`。JSON 化時には `null` になる |
| `Infinity` / `-Infinity` | 無限大。JSON 化時には `null` になる |

整数・正数の検証、clamp、無効値時の fallback はありません。負数や小数もスクリプト内ではそのまま数値としてリクエスト本文に入ります。`JSON.stringify` が非有限数を `null` にするところまではスクリプト上で確認できますが、`null`・負数・小数などを受け取ったモデルサーバーがどう扱うかは Strata のこのコードからは判断できません（`apps/host/scripts/agent-lost-e2e.mjs:143,147`）。

## 有効になる条件

- Node.js で `apps/host/scripts/agent-lost-e2e.mjs` を実行し、`raw` シナリオが選択されること。
- スクリプト冒頭の `STRATA_HARNESS_DIR` 必須確認を通過すること（未設定なら `STRATA_HARNESS_DIR is not set` を stderr に出し、終了コード 2）。
- サーバー起動または `E2E_BASE_URL` で指定した既存サーバーへの接続が成功すること。エンジンの ready 待ちに失敗した場合は `the engine did not become ready` を stderr に出し、終了コード 4 で終了するため、この変数を使う raw リクエストには到達しません（`apps/host/scripts/agent-lost-e2e.mjs:44,58-84,86-94`）。

シナリオ名をコマンドライン引数で選びますが、`E2E_RAW_CAP` を上書きする CLI 引数や別の環境変数との優先順位はありません。リクエスト先が既存サーバーか、このスクリプトが起動したサーバーかで `max_tokens` の組み立て方は変わりません（`apps/host/scripts/agent-lost-e2e.mjs:34,40-41,141-147`）。

## 実行時の詳細

環境変数はモジュール読込時に定数へキャッシュされず、`raw` ブロックに入った時点で helper が `process.env` を参照します。その値を `Number` に変換し、ストリーミング有効・temperature `0.6` などとともに JSON 本文へ設定して、`POST /v1/chat/completions` を送ります。スクリプトがサーバーを起動する場合、子プロセス環境は `{ ...process.env, ... }` で作るため、この値も継承されます。一方、既存サーバー接続ではそのサーバーの環境を変更しません。確認できた `E2E_RAW_CAP` の読み取りは raw リクエスト本文の組み立てだけです（`apps/host/scripts/agent-lost-e2e.mjs:29-30,77-79,141-149`）。

応答本文の SSE 行を解析し、tool call の断片数や `finish_reason` を集計します。期待する `finish_reason === 'length'`、tool 名 `write`、断片数 5 超を満たすと raw シナリオは PASS になり、そうでなければ FAIL として表示されます。全シナリオの結果に失敗があれば最後に終了コード 1 になります。応答ステータス自体の検査はなく、SSE の JSON 解析が失敗した場合は例外経路になります（`apps/host/scripts/agent-lost-e2e.mjs:147-158,207-209`）。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:29-30` — 名前を動的に受け取る helper と nullish fallback。
- `apps/host/scripts/agent-lost-e2e.mjs:40-41,141-146` — シナリオ選択と raw リクエストの `max_tokens` 設定。
- `apps/host/scripts/agent-lost-e2e.mjs:44,58-94` — Harness 必須条件、サーバー選択・起動、ready 失敗経路。
- `apps/host/scripts/agent-lost-e2e.mjs:147-158,207-209` — リクエスト、応答観測、PASS/FAIL と終了コード。

`docs/envvars/000_envvers.md` に候補名がありますが、実コードの参照は上記 1 箇所だけでした。Strata 本体の環境設定としてではなく、同梱 E2E スクリプトの raw リクエスト用設定として記録しています。
