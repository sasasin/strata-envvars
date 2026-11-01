# `PROMPT_WEB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PROMPT_WEB` は、Strata のアプリ設定ではなく、同梱の Playwright フロー用スクリプト `apps/host/scripts/agent-flow-s4b.mjs` が Web 操作確認時にチャットへ送るプロンプトを差し替えます。アプリ本体やサーバーがこの環境変数を読む箇所は見つかりませんでした。候補一覧には掲載されていますが、用途はこのスクリプト内に限られます。

## 値と判定

| 環境値 | スクリプト内の値 |
|---|---|
| 未設定 | 既定の英語プロンプト `Use the web_fetch tool to open https://example.com and tell me the page title in one sentence.` |
| 空文字 | 空文字のまま。既定値に置き換わらない |
| その他の設定値 | 文字列をそのままプロンプトとして使う |

読み取りは `process.env.PROMPT_WEB ?? <既定値>` です。真偽値・数値への変換、文字列の検証、trim、空文字判定、範囲制限はありません。Node.js が環境値を文字列として提供し、`??` は `null` / `undefined` のときだけ既定値を選ぶため、空文字を含む設定値は保持されます。

## 有効になる条件

この変数が使われるのは、`apps/host/scripts/agent-flow-s4b.mjs` を Node.js で実行し、フローが Web 操作確認の段階まで進む場合です。スクリプト冒頭で `STRATA_URL` が falsy なら `STRATA_URL is required` を stderr に出して終了コード 2 で終わるため、そこでは `PROMPT_WEB` は送信されません。モデル選択と先行する helper / edit の操作が進んだ後、Web 段階でチャットへ送信します。

## 実行時の詳細

値はモジュール初期化時に一度 `const` へ読み込まれます。実行中にプロセス環境を変更しても、この定数は再評価されません。Web 段階では `send(PROMPT_WEB)` が最初の textarea に値を入力し、`Send` ボタンをクリックします。その後、フローは承認待ちカードがなくなるまで待ち、画面に `web_fetch` を含む表示があるかを確認します。`PROMPT_WEB` 自体をアプリの環境変数として転送・設定する処理はありません。

スクリプトの例外は catch 節で `FAIL <例外メッセージ>` として記録され、最終的に失敗終了します。Web 操作段階の確認で `web_fetch` 表示が見つからない場合も `FAIL` を出力し、最終終了コードは 1 になります。プロンプト文面がどのツール呼び出しや応答を生むかはアプリ／モデル側の結果であり、この環境変数の実装だけからは保証されません。

## 根拠

- `apps/host/scripts/agent-flow-s4b.mjs:2-14` — Playwright による S4b 実アプリフローであること、および説明コメント中の環境変数一覧。
- `apps/host/scripts/agent-flow-s4b.mjs:20-30` — `STRATA_URL` 必須判定と `PROMPT_WEB` の nullish fallback を含むモジュール初期化時の読み取り。
- `apps/host/scripts/agent-flow-s4b.mjs:41` — `send` が textarea への入力と `Send` ボタンクリックを行う。
- `apps/host/scripts/agent-flow-s4b.mjs:119-132` — Web 段階での送信、承認待ち処理、`web_fetch` 表示確認。
- `apps/host/scripts/agent-flow-s4b.mjs:153-161` — 例外ログ、ブラウザー後始末、失敗フラグに応じた終了コード。
