# `PROMPT_A`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PROMPT_A` は `apps/host/scripts/agent-flow.mjs` のブラウザー経由の agent flow 確認で使う入力文面です。`TWO_CHATS=1` のとき、最初のチャットを実行中にしてから二つ目のチャットへ送る文面を指定します。Strata engine や server の実行設定として読むコードは見つかりませんでした。

## 値と判定

| 状態 | 送信される文面 |
|---|---|
| 未設定（`process.env.PROMPT_A` が `undefined`） | `SCRIPT:slow 150` |
| 設定あり（空文字を含む） | 環境変数の文字列をそのまま使う |

`??` による未設定判定であり、空文字を既定値に置き換えません。文字列の parse、trim、妥当性検査、長さ制限はこのスクリプトにはありません。CLI 引数や別の環境変数による上書きもありません。

## 有効になる条件

この読み取りは `TWO_CHATS` が文字列 `1` と完全一致した場合だけ実行される任意の二チャット確認経路にあります。未設定、空文字、`true`、`01` などではこの節の経路全体が実行されず、`PROMPT_A` は参照されません。スクリプトの説明でも二チャット動作は optional とされています。

## 実行時の詳細

スクリプトは `TWO_CHATS` 条件に入った後、選択済みモデルの新しいチャットで `PROMPT_A ?? 'SCRIPT:slow 150'` を `send()` に渡します。`send()` はページの最初の `textarea` に文字列を入力して Send ボタンを押すだけで、環境変数自体を engine プロセスへ転送する処理はありません。既定の `SCRIPT:slow 150` はスクリプト上の prompt の既定値であり、Strata の engine 側での解釈や実行結果はこの環境変数の読取コードからは保証できません。

読み取りは二チャット経路に入ったときの直接参照で、値をモジュール初期化時に cache する変数はありません。送信後はページが streaming 状態になるのを待ちます。その待機や後続の操作で例外が起きると catch 節が `FAIL <error.message>` を出し、失敗スクリーンショットを試み、最後に終了コード 1 を返します。全 checkpoint 成功時の終了コードは 0 です。

## 根拠

- `apps/host/scripts/agent-flow.mjs:1-21` — 実アプリを Chrome で操作する flow script と任意の二チャット確認の説明。
- `apps/host/scripts/agent-flow.mjs:51-55` — `send()` が textarea に文面を入力して Send を押す処理。
- `apps/host/scripts/agent-flow.mjs:124-147` — `TWO_CHATS === '1'` の条件、`PROMPT_A` の nullish fallback、二チャット確認の流れ。
- `apps/host/scripts/agent-flow.mjs:149-156` — 例外時の失敗ログ・終了コードと通常終了コード。
- `apps/host/server/agent/README.md:114-118` — `agent-flow.mjs` を実アプリ操作・スクリーンショット用スクリプトとして記載。
