# `RATE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/chat-growth-proxy.mjs` の実験用プロキシが、合成した chat stream の出力間隔を調整するために読む環境変数です。通常の Strata engine やサーバー設定として読む箇所は確認できませんでした。このスクリプトの先頭コメントも、デモ host を使う throwaway proxy と説明しています（同ファイル 1 行目）。

## 値と判定

モジュール初期化時に `Number(process.env.RATE ?? 400)` で数値へ変換し、`per = Math.max(1, Math.round(RATE / 50))` を求めます（`apps/host/scripts/chat-growth-proxy.mjs:4,16`）。文字列全体を `Number` で変換するため、`parseInt` のような先頭部分だけの読み取りではありません。

| `RATE` | 結果 |
|---|---|
| 未設定 | `?? 400` により 400。`per` は 8。 |
| 空文字 | `Number("")` は 0。`per` は下限の 1。 |
| 数値文字列 | `Number` で変換し、50 で割って四捨五入した値を `per` にする。ただし `per` は最低 1。例: `400` → 8。 |
| 負数または 0 | 丸めた値が 1 未満になるため `per` は 1。 |
| 数値に変換できない文字列 | `RATE` と `per` は `NaN` になり、待ち時間条件の比較が成立しないため、人工待ちを挟まない。 |
| 数値としての無限大 | `per` も無限大となり、待ち時間条件は成立せず、人工待ちを挟まない。 |

範囲外値に対するエラーや警告はありません。下限処理は `per` に対するもので、`RATE` 自体を範囲内に clamp するものではありません（同ファイル 16 行目）。

## 有効になる条件

この値を使うのは `chat-growth-proxy.mjs` が起動している場合だけです。`POST` かつ URL が `/api/chat/stream` で始まるリクエストに対して、合成の reasoning と本文を送る経路に入ると `per` が参照されます（同ファイル 9-19 行目）。他のリクエストは上流 host に転送されるため、`RATE` による待ちは入りません（同ファイル 23-25 行目）。OS/backend/build macro/モデル状態による分岐はこのスクリプト内にありません。

## 実行時の詳細

`RATE` は Node.js の `process.env` からモジュール読み込み時に一度読み、定数に保持します。起動後の環境値変更を再読込するコードはありません（同ファイル 4 行目）。CLI 引数との優先順位や別環境変数からの上書きもありません。

合成 stream の reasoning 部分ではカウンターを 9 ずつ増やし、`sent % per < 9` のとき 20 ms 待ちます。本文部分では段落を 24 文字ずつ delta として送り、カウンターを 6 ずつ増やし、`(sent / 6) % Math.max(1, Math.round(per / 2)) === 0` のとき 10 ms 待ちます（同ファイル 17-19 行目）。従って `RATE` は一秒あたりの token 数や返却する長さを直接設定せず、これらの人工待ち条件に使う間隔値を変えます。返却長は別の `REASON_TOKENS` と `REPLY_TOKENS` が決めます（同ファイル 4,17-19 行目）。

待ち処理によるログ、警告、終了コード変更はありません。上流への転送で接続エラーが発生した場合は HTTP 502 を返しますが、これは `RATE` の判定や変換による経路ではありません（同ファイル 23-24 行目）。

## 根拠

- `apps/host/scripts/chat-growth-proxy.mjs:1` — throwaway demo proxy である旨。
- `apps/host/scripts/chat-growth-proxy.mjs:4,16-19` — `RATE` の読み取り、既定値、変換、人工待ち条件。
- `apps/host/scripts/chat-growth-proxy.mjs:9-13,20-25` — 対象リクエスト、stream 応答、その他の上流転送と 502 経路。
