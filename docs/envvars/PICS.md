# `PICS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PICS` はホスト画面の負荷測定スクリプト `apps/host/scripts/chat-growth.mjs` 専用の設定です。画像付きの会話を測るため、何ターン目までテスト画像を貼り付けるかを指定します。Strata エンジン、通常のホスト起動、サーバー API の設定としては読み取られていません。

## 値と判定

スクリプトのモジュール読み込み時に `Number(process.env.PICS ?? 3)` で数値化します（`apps/host/scripts/chat-growth.mjs:7`）。環境変数は文字列として受け取り、`Number` に渡された値を整数化・範囲検証する処理はありません。

| 環境値 | 判定と結果 |
|---|---|
| 未設定 | `?? 3` により 3。既定では最初の 3 ターンに画像を貼り付ける |
| 空文字 | `??` は空文字を既定値に置き換えず、`Number("")` は 0。画像を貼り付けない |
| 数値に変換できる文字列 | 変換後の値を `t <= PICS` の比較に使う。例: `2` なら最初の 2 ターン |
| 数値に変換できない文字列 | `Number` の結果は `NaN` となり、`t <= PICS` は常に偽。画像を貼り付けない |
| 負数または 0 | すべてのターンで条件が偽。画像を貼り付けない |
| 正の小数 | 整数のターン番号と直接比較する。例: `2.5` なら 1、2 ターンに貼り付ける |
| `Infinity` など大きい値 | 画像対象は `TURNS` のループ内に限られるため、実行される全ターンに貼り付ける |

## 有効になる条件

この変数を読むのは、開発・診断用の `apps/host/scripts/chat-growth.mjs` を実行した場合だけです。同ファイル先頭の説明では、使い捨てホスト（`STRATA_REAL_ENGINE=0`、ポート 18791）、`scripts/chat-growth-proxy.mjs`（ポート 18790）および Chrome を使う測定手順とされています（`apps/host/scripts/chat-growth.mjs:1`）。同梱テストのコメントもこのスクリプトを画面上の測定手段として参照しています（`apps/host/tests/chat-render-memo.test.mjs:1-3`）。

実際の添付回数は `TURNS` のループにも制限されます。`TURNS` は同じ行で既定値 6 として読み取られ、各ターン番号 `t` に対して `t <= PICS` のときだけ画像を作って貼り付けます（`apps/host/scripts/chat-growth.mjs:7,34-39`）。このスクリプトは `PICS` 用の CLI 引数や、別設定による上書きを実装していません。

## 実行時の詳細

各対象ターンで 900×900 ピクセルのランダムな RGB PNG を生成して base64 化し、ブラウザー上の composer に `image.png` として clipboard paste イベントを送ります。その後、テキストを入力して送信します。従って `PICS` が変えるのはこの測定スクリプトが画像を貼る初期ターン数であり、Strata 側の画像処理機能を有効化するものではありません（`apps/host/scripts/chat-growth.mjs:9-13,34-41`）。

`PICS` はモジュール評価時に定数へ読み込まれます。実行中に環境を書き換えても再読込されません。値の範囲検証、無効値の警告、`PICS` に起因する終了処理はありません。無効な数値文字列は比較が偽になるため画像を貼らず、スクリプトはそのままターン処理を続けます（`apps/host/scripts/chat-growth.mjs:7,34-41`）。

## 根拠

- `apps/host/scripts/chat-growth.mjs:1-7`: スクリプト用途、既定値、起動時の数値変換。
- `apps/host/scripts/chat-growth.mjs:34-41`: ターン番号による画像添付条件と送信。
- `apps/host/scripts/chat-growth.mjs:9-13`: 測定画像の生成。
- `apps/host/tests/chat-render-memo.test.mjs:1-3`: 同梱テスト内での測定スクリプトへの参照。
