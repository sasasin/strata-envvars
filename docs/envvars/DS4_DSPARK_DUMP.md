# `DS4_DSPARK_DUMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 の DSpark drafter が使う入力と中間値・出力をバイナリファイルへ書き出す診断用フックです。Strata 同梱の `tools/dsv41/dspark_ref.py` が、DeepSeek の checkpoint から計算した参照値と照合するためのデータを記録します（`src/dsv41/ds4_model.cu:914-920`; `tools/dsv41/dspark_ref.py:3-16`）。通常の生成結果を指定形式で保存する機能ではありません。

## 値と判定

| 入力 | 動作 |
|---|---|
| 未設定 | dump を行わない（`dump_d == nullptr`） |
| 設定あり（空文字を含む） | 値をファイルパスとして `fopen(path, "wb")` し、成功した場合に dump を行う |

値の真偽や数値変換はせず、`getenv()` が null かどうかだけで分岐します。ファイルは `wb` で開くため、同じパスの既存内容は切り詰められます。open に失敗すると `dump_d` が null になり、コード上は診断出力を無効のまま処理を続けます。エラーを報告する分岐はこの箇所にはありません（`src/dsv41/ds4_model.cu:919`）。

## 有効になる条件

DSpark drafter の CUDA 実装で、`dump_d` が null でない場合に限り有効です。DSpark の seed は `g.n_mtp == 0` または入力行数 `n <= 0` なら何もせず戻り、通常の drafter forward 側も DSpark blocks が実行されなければ該当 dump は起きません（`src/dsv41/ds4_model.cu:6659-6664,6758-6771`）。ソースに環境値の形式検証や別 backend 用の読み取りは見つかりませんでした。

## 実行時の詳細

seed 時には全 device stream を同期してから、4 個の int64 header `{'S', p0, n, nt * D}` と taps の float 配列を書き、flush します（`src/dsv41/ds4_model.cu:6668-6677`）。各 drafter block の forward では、ring の BF16 行を host へコピーし、block を実行した後の stream を float で host にコピーします。生成・confidence 計算後には `{'D', p0, y, T}` header、draft token（int32）、confidence（float）、hidden rows（float）、各 block の ring（BF16）と stream（float）を順に書いて flush します（`src/dsv41/ds4_model.cu:6758-6771,6851-6873`）。

helper は `fopen` 成功後に `fwrite` と `fflush` の戻り値を検査しません。ファイルを閉じるコードもこの参照範囲では見つからず、ファイル寿命は `Dspark` オブジェクトが保持する `dump_d` の寿命に依存します。I/O エラー時の回復や明示的な close は確認できません。

## 根拠

- `src/dsv41/ds4_model.cu:911-920` — 関連する DSpark 調査用環境変数と `dump_d` の初期化。
- `src/dsv41/ds4_model.cu:6659-6677` — seed 入力と taps dump。
- `src/dsv41/ds4_model.cu:6758-6771,6851-6873` — block ring/stream と drafts/confidence/hidden dump。
- `tools/dsv41/dspark_ref.py:3-16` — dump の intended consumer と参照計算の目的。
