# `PROMPT_LONG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/agent-flow.mjs` がブラウザー経由でアプリに送る「長い返答をさせる prompt」の文面を差し替えます。Strata の通常の CLI、推論エンジン、サーバー設定を変える環境変数ではなく、実アプリのエージェント操作を確認する手動スクリプト専用です。スクリプトの説明には、Harness が導入され API 接続が保存済みのホストに対して実行する旨があります（`apps/host/scripts/agent-flow.mjs:1-20`）。

## 値と判定

| 状態 | 使用する文面 |
|---|---|
| `PROMPT_LONG` 未設定 | `SCRIPT:slow 400` |
| 設定あり（空文字を含む） | 環境変数の文字列をそのまま使う |

Node.js の `process.env.PROMPT_LONG ?? 'SCRIPT:slow 400'` による選択で、文字列の parse、trim、大小文字変換、値域検査はありません。`??` は未設定（`undefined`）の場合にだけ既定値を選ぶため、空文字は既定値へ置換されません。スクリプトは起動時に `const` として一度読み取り、実行中に環境を変更しても再読込しません（`apps/host/scripts/agent-flow.mjs:33`）。

## 有効になる条件

スクリプトを `node scripts/agent-flow.mjs` で実行したときに参照されます。通常の Strata 実行ファイルからこの名前を読む箇所は確認できません。OS や CUDA/HIP backend による値判定はありません。

処理には `STRATA_URL` が必要で、未設定または空文字なら `STRATA_URL is required` を stderr に出して終了コード 2 で終了します（同:27-28）。スクリプト説明上は Harness を導入したホストと保存済み API 接続を使い、UI のモデル選択では既定 `Cloud model`（または `MODEL`）を選びます（同:6-8,15,31,65-70）。その後に初めて `PROMPT_LONG` が使われます。

## 実行時の詳細

値はブラウザーのチャット入力欄へ入力され、Send ボタンを押して送信されます（同:51-55,86-89）。スクリプトは送信後、ストリーミング開始を待ち、ページ本文が送信前より400文字を超えて増えるまで最大300秒待機します。その後 Stop ボタンを押し、ストリーミング終了を最大60秒待ち、`/api/agent/status` の `activeTurns === 0` などを確認します（同:86-101）。したがって値はプロンプト文面を変えますが、応答の長さやストリーミングを保証する形式検査はありません。条件に達しない場合などの例外は `FAIL <error.message>` として標準出力に出し、失敗スクリーンショットを試みます。最後に失敗があれば終了コード1になります（同:148-155）。

## 根拠

- 候補一覧には `PROMPT_LONG` が載っています（`docs/envvars/000_envvers.md:512`）。
- Strata リポジトリの `rg -n --hidden --glob '!.git/**' 'PROMPT_LONG' .` では、実参照は `apps/host/scripts/agent-flow.mjs:17,33,88` のみでした。17行目は説明、33行目は環境値の読取りと既定値、88行目は送信です。
- UI 操作、待機、停止、エラー処理の根拠は上記 `apps/host/scripts/agent-flow.mjs` の各行です。別の環境変数や CLI 引数による `PROMPT_LONG` 自体の上書き・転送は見つかりませんでした。
