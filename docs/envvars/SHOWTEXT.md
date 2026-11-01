# `SHOWTEXT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱スクリプト `apps/host/scripts/agent-http.mjs` が HTTP チャットストリームを処理した後、回答本文（`delta` frame のテキスト）をスクリプトの標準出力に表示するための診断用スイッチです。Strata エンジンが読む設定ではなく、値を HTTP リクエストへ渡す処理もありません。リポジトリ内の完全一致参照はこのスクリプトの 1 箇所です。

## 値と判定

| `SHOWTEXT` の状態 | `quiet` | 追加の本文表示 |
|---|---:|---|
| 未設定 | false | なし |
| 空文字 | false | なし（JavaScript の falsy 値） |
| 空でない文字列（`0`、`false` を含む） | false | あり（truthy 値） |
| 任意 | true | なし |

文字列の parse、大小文字比較、数値変換はありません。`stream()` の既定は `quiet = false` です。呼び出し側が `{ quiet: true }` を渡すと、`SHOWTEXT` が設定されていても表示されません。通常の `stream`、`goal`、`plan` 等の呼び出しは quiet を指定せず、`long`、`effort`、`sampling` の呼び出しは quiet を true にしています。

根拠: `apps/host/scripts/agent-http.mjs:35, 75, 83-86, 97-103, 150-160, 184-201, 216`。

## 有効になる条件

この変数が影響するのは同梱の Node.js HTTP 操作用スクリプト内で `stream()` が完了する経路だけです。スクリプト起動時に `STRATA_URL` が必要で、未設定なら 14 行目のエラーを標準エラーへ出して終了コード 2 で終わるため、ストリーム処理には到達しません。`SHOWTEXT` 自体に CLI オプションや別の環境変数による上書きはありません。`quiet` オプションは本文表示を抑止します。

## 実行時の詳細

`stream()` は frame を配列に蓄え、ストリームの読み取りループが終了した後に `process.env.SHOWTEXT && !quiet` を評価します。環境変数は起動時に cache されず、各 `stream()` 呼び出しの完了時に参照されます。条件が成立すると、`type === 'delta'` の frame の `text` を到着順に連結し、`---- answer text ----` と `---- end ----` の間に `console.log` で出力します。`reasoning` frame は本文に含めず、delta がない場合も囲みの行だけを出力します。HTTP エラー時は 37 行目で例外になり、この本文表示箇所へは進みません。

この処理はスクリプトのローカル表示だけを変えます。HTTP サーバーやモデルの生成内容・実行状態に対する制御はコード上ありません。

## 根拠

- 全参照検索: `apps/host/scripts/agent-http.mjs:75`。
- `STRATA_URL` の起動条件と終了: `apps/host/scripts/agent-http.mjs:13-14`。
- HTTP frame の取得・保存・delta の計数と本文出力: `apps/host/scripts/agent-http.mjs:35-76`。
- `quiet` を指定しない呼び出しと quiet を有効にする呼び出し例: `apps/host/scripts/agent-http.mjs:83-86, 184-201, 216`。
