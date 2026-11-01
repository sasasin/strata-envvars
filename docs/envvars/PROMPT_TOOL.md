# `PROMPT_TOOL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PROMPT_TOOL` は、Strata のホスト/UI を Chrome で操作する同梱 E2E スクリプト `apps/host/scripts/agent-flow.mjs` が、ツール呼び出しを試す最初のチャットに入力するプロンプトを指定します。Strata の推論エンジンや通常のサーバー起動設定が読む変数ではありません。コード内でこの名前を読む箇所は同スクリプトの一箇所で、同ファイルの `send(PROMPT_TOOL)` に渡されます（`apps/host/scripts/agent-flow.mjs:16,32,72-74`）。

## 値と判定

| 環境値 | スクリプトが使う値 |
|---|---|
| 未設定 | `SCRIPT:tool notes.txt hello from the agent` |
| 空文字 | 空文字のまま。既定文には置き換えない |
| その他 | 環境変数の文字列をそのまま使う |

Node.js の `process.env.PROMPT_TOOL ?? <既定文>` による読み取りで、数値変換、trim、文字列比較、値域検証はありません。環境変数はモジュール評価時に一度 `const` へ読み込まれます。CLI 引数や別の環境変数による上書き経路はこの変数にはありません（`apps/host/scripts/agent-flow.mjs:32`）。

## 有効になる条件

`apps/host/scripts/agent-flow.mjs` を Node.js で実行した場合にだけ使われます。コメントに記載された用途は、Harness がインストール済みで API 接続を一つ保存したホストに対する実アプリのブラウザ操作です（`apps/host/scripts/agent-flow.mjs:2-10`）。スクリプトは `STRATA_URL` が空または未設定なら `STRATA_URL is required` を stderr に出して終了コード 2 で終了するため、その条件では `PROMPT_TOOL` を送信しません（同:27-28）。ブラウザ操作は Chrome を headless で起動し、チャットで `MODEL`（既定 `Cloud model`）を選択してから進みます（同:31,35-46,63-73）。

## 実行時の詳細

スクリプトは読み取った値を `textarea` に入力し、Send ボタンをクリックします。続いて、提案状態のツールカードが現れるのを最大 120 秒待ち、カードの承認操作など後続のチェックを行います（`apps/host/scripts/agent-flow.mjs:51-55,72-84`）。この変数自体がツールを実行したり承認したりするわけではなく、プロンプト文字列を UI へ渡すだけです。モデルやアプリの応答が意図どおりのツールカードになる保証はコードにありません。

待機などの処理で例外が起きると、スクリプトは `FAIL <例外メッセージ>` を標準出力に出し、失敗時のスクリーンショットを試み、最後に終了コード 1 で終了します。各チェックが失敗した場合も最終的に終了コード 1 です（`apps/host/scripts/agent-flow.mjs:41-43,149-156`）。空文字の場合も値は空のまま入力欄へ渡されますが、その後 UI が送信をどう扱うかはこの変数の読み取りコードでは規定されていません。

## 根拠

- 候補名の全参照を検索すると、実装上の読み取りは `apps/host/scripts/agent-flow.mjs:32` のみで、使用箇所は `:73`。`:16` はコメント上の説明です。
- E2E スクリプトが実アプリを Chrome で駆動する説明: `apps/host/scripts/agent-flow.mjs:2-10`; `apps/host/server/agent/README.md:116-118`。
- 既定値と読み取り時期: `apps/host/scripts/agent-flow.mjs:32`。
- UI への入力、ツールカード待ち、承認手順: `apps/host/scripts/agent-flow.mjs:51-55,72-84`。
- 必須 URL、Chrome 起動、失敗時のログと終了: `apps/host/scripts/agent-flow.mjs:27-28,35-46,149-156`。
