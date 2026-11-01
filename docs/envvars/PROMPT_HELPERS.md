# `PROMPT_HELPERS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/agent-flow-s4b.mjs` が、S4b の実アプリ操作フローでチャットに送る「helper agent を2つ起動する依頼文」を設定します。Strata のサーバーやエンジンの設定値ではなく、Playwright で既存の Strata UI を操作する同梱の検証用スクリプト専用です（`apps/host/scripts/agent-flow-s4b.mjs:1-14,82-103`）。

## 値と判定

| 環境変数の状態 | スクリプトが使う値 |
|---|---|
| 未設定 | hello.py と README.txt の作成を2つの helper に依頼する既定の英文プロンプト |
| 空文字 | 空文字のまま。既定文には置き換えない |
| その他の設定値 | 文字列を変換・検証せず、そのまま使う |

実装は Node.js の `process.env.PROMPT_HELPERS ?? <既定文>` です。nullish coalescing により未設定 (`undefined`) の場合だけ既定文を選びます。空文字や、`0`、`false` を含む任意の文字列に特別な解釈・範囲制限はありません。CLI 引数や別の環境変数による上書きはこのスクリプトにはありません（`apps/host/scripts/agent-flow-s4b.mjs:26`）。

## 有効になる条件

この値を読むのは `apps/host/scripts/agent-flow-s4b.mjs` を Node.js で直接実行した場合です。ファイル冒頭の説明にある通り、Playwright と Chrome を使って Strata のチャット UI を操作するフローです。通常の Strata サーバー起動や CLI 起動時に、この変数を読む実装は見つかりません（同スクリプト `:2-14,16-18`）。OS、GPU backend、build macro、モデル状態による `PROMPT_HELPERS` 自体の条件分岐はありません。

## 実行時の詳細

環境変数はスクリプトのモジュール初期化時に一度読み、`const` に保持されます。実行中の環境変更を再読込するコードはありません。フローはチャット画面を開き、モデルを選んだ後に `send(PROMPT_HELPERS)` を呼びます。`send` は最初の textarea に値を入力して Send ボタンをクリックします。その後、ストリーミング開始や subagent 表示を待ち、画面を撮影して確認を進めます（`apps/host/scripts/agent-flow-s4b.mjs:26,41,82-103`）。

このスクリプトは値の parse エラーや無効値の警告を出しません。プロンプト文字列自体をログに出す処理もありません。後続の UI 操作や確認で例外が発生した場合は catch 節が `FAIL <error.message>` を標準出力に出し、失敗画面の撮影を試み、最終的に終了コード 1 を返します。完了時は確認結果に応じて 0 または 1 です（`apps/host/scripts/agent-flow-s4b.mjs:32-33,153-161`）。これらはフロー全体の失敗処理であり、特定の `PROMPT_HELPERS` 値に対する個別の検証ではありません。

## 根拠

- 環境変数名とこのスクリプトが検証用であること: `apps/host/scripts/agent-flow-s4b.mjs:1-14`
- 値の読み取り、既定値、送信先: `apps/host/scripts/agent-flow-s4b.mjs:26,41,94-103`
- 起動フローと失敗・終了処理: `apps/host/scripts/agent-flow-s4b.mjs:82-103,153-161`
- 候補一覧での記載: `docs/envvars/000_envvers.md:511`
