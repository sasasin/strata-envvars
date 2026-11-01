# `TURNS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱診断スクリプト `apps/host/scripts/chat-growth.mjs` が、チャット画面で送信・計測するターン数を指定します。エンジン、サーバー、通常の CLI の設定ではありません。このスクリプトは使い捨てホスト、プロキシ、Chrome を用いる測定用であるとソース冒頭に記されています（`apps/host/scripts/chat-growth.mjs:1-2`）。

## 値と判定

スクリプト起動時に `Number(process.env.TURNS ?? 6)` で一度変換します（`apps/host/scripts/chat-growth.mjs:7`）。未設定なら既定値 `6` です。空文字は nullish fallback の対象ではないため `Number("")` により `0` になります。

| `TURNS` の状態・値 | 結果 |
|---|---|
| 未設定 | 既定の `6` 回 |
| 空文字、または数値として `0` 以下 | ループは `0` 回 |
| 正の整数 `n` | `n` 回 |
| 正の小数 | 条件 `t <= TURNS` を満たす整数 `t` まで実行（例: `2.5` は `2` 回） |
| 数値に変換できない文字列 | `NaN` となり、初回の `1 <= TURNS` が偽なので `0` 回 |
| `Infinity` として変換される値 | 上限チェックがないため、実用上終わらないループになる |

文字列は JavaScript の `Number()` の規則で変換されます。負数の拒否、整数化、上限 clamp、無効値の fallback は実装されていません（`apps/host/scripts/chat-growth.mjs:7,34`）。

## 有効になる条件

`TURNS` を読むのは `apps/host/scripts/chat-growth.mjs` の実行時だけです。ソースには CLI 引数による上書きや、サーバー・エンジンへの転送はありません。`BASE`（同じ行で既定 URL を設定）や `PICS`、`MON` も別々に環境から読み取ります。

各ターンでは送信前に `t <= PICS` を判定し、該当するターンだけ画像を作成して貼り付けます。`PICS` は既定 `3` で別途 `Number()` 変換されます。したがって `TURNS` が `PICS` より小さければ実際の画像貼り付けはターン数までです。ループ後には `MON !== '0'` の場合に Monitor 画面を開こうとします（`apps/host/scripts/chat-growth.mjs:7,34-39,55`）。

## 実行時の詳細

値はスクリプトのモジュール初期化時に定数 `TURNS` として読み取られ、その後のループで再評価されません。各反復で `turn t write a long answer` を入力して Send を押し、最大 240 秒まで 2 秒間隔で応答中かを確認します。各ターンの経過秒数、peak heap、main-thread busy 時間を標準出力に出し、続いて `metrics('after turn ' + t)` の計測値も出します。初期値 `6` であればターン 1 から 6 までの処理です（`apps/host/scripts/chat-growth.mjs:21-29,34-53`）。

`TURNS` が `0`、負数、または `NaN` の場合、ターン別の送信・計測ログは出ませんが、ループ前の初期画面遷移と `start` 計測は行われます。無効値を知らせる専用警告・エラー・終了コードの処理はありません。正の無限大等で長時間ループとなる値にも検査はありません。個々の応答が 240 秒を超えた場合は、そのターンの待機を抜けて計測ログを出し、次の反復へ進みます（`apps/host/scripts/chat-growth.mjs:21-29,34-55`）。

## 根拠

- 読み取り、既定値、関連変数: `apps/host/scripts/chat-growth.mjs:6-7`
- 画像条件とターン反復: `apps/host/scripts/chat-growth.mjs:34-39`
- 送信、応答待ち、ターン計測: `apps/host/scripts/chat-growth.mjs:40-53`
- 任意の Monitor 計測: `apps/host/scripts/chat-growth.mjs:55`
