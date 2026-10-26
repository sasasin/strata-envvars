# `DS4_ASYNC_T`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 用 CUDA 実装で、通常の window 処理と speculative drafter の window 処理を非同期の expert-routing 経路にする最大 token 数を指定します。既定値は 8 です。ここでいう非同期経路は、GPU が routing 結果を mailbox に公開して shared expert と VRAM 上の expert を実行している間に、service thread が CPU 側 expert を処理し、expert の合算前に GPU が応答を待つ方式です。閾値を超えた window は別の同期 host-routing 経路を使います。

## 値と判定

値は `std::atoi` で整数に変換されます。文字列全体の妥当性検査はありません。

| 値 | 結果 |
|---|---|
| 未設定 | `async_max_t = 8` |
| `8` などの整数 | 変換した整数以下の window が閾値判定を通る |
| `0`、空文字、整数に変換できない文字列 | `atoi` の結果は 0。通常経路の正の window は閾値判定を通らない |
| 負の整数 | 正の window は閾値判定を通らない |
| 先頭に空白や符号があり、数字の後ろに文字が続く値 | `atoi` が先頭の空白と符号の後の数字部分を変換する。例: `"  +3x"` は 3 |

`async_max_t` との比較は `T <= async_max_t` です。値は clamp されません。整数型で表現できない範囲の文字列については `atoi` の範囲外変換の結果に依存するため、設定値として扱えるとは断定できません。

同じ実装には別変数 `DS4_SYNC` があります。これは値ではなく設定有無（`getenv(...) != nullptr`）だけを見ます。そのため空文字や `DS4_SYNC=0` でも通常経路の非同期化を止めます。

## 有効になる条件

- 対象は `src/dsv41/ds4_model.cu` の DeepSeek V4.1 CUDA model 実装です。値の読み取りと使用はこのファイルだけにあります。
- 通常の window 経路では `DS4_SYNC` が未設定で、window の `T` が `DS4_ASYNC_T` の変換値以下のとき `WinPlan::async` が true になります。
- speculative drafter の window も同じ `!DS4_SYNC && T <= async_max_t` 判定を使います。
- parallel/chunk の2経路では `WinPlan::async = true` を直接設定します。この経路では `DS4_ASYNC_T` と `DS4_SYNC` の上記判定は使われません。

## 実行時の詳細

`DS4_ASYNC_T` は `Model::Impl` のメンバー初期化時に読み取られ、モデル実装インスタンスの値として保持されます。通常の window ごとに `plan_window()` が `T` と閾値を比較し、speculative drafter でも `draft_()` 内で同様に判定します。

`WinPlan::async` が true の MoE 経路では、GPU が routing と expert plan を公開し、shared expert および VRAM expert の処理を進める間に CPU lane の応答を準備します。lead device は応答 sequence を待ってから expert の結果を合算します。false の経路では GPU から routing の index、weight、入力を host にコピーして event を同期した後、CPU lane と VRAM lane の処理・合算を進めます。したがって、この環境変数は非同期 mailbox 経路を選ぶ window サイズの上限であり、CPU expert lane 自体を有効・無効にするスイッチではありません。

この変数自体についての設定説明や測定値は `docs/DETAILS.md` に見つかりませんでした。値による性能差や token の同一性は、この調査では測定・検証していません。

## 根拠

- `src/dsv41/ds4_model.cu:800-810,983-987`: `Model::Impl` と `DS4_SYNC` / `DS4_ASYNC_T` の初期値・読み取り。
- `src/dsv41/ds4_model.cu:6750-6756`: speculative drafter の非同期判定と mailbox sequence の準備。
- `src/dsv41/ds4_model.cu:8458-8486`: 通常 window の判定と async の場合の sequence 発行。
- `src/dsv41/ds4_model.cu:7530-7534,7691-7695`: parallel/chunk 経路では async を直接有効化。
- `src/dsv41/ds4_model.cu:2788-2792,6449-6470`: decode service thread の起動と mailbox request ごとの CPU lane 処理。
- `src/dsv41/ds4_model.cu:9051-9073,9095-9098`: async MoE 経路の routing 公開、shared expert 実行、応答待ち。
- `src/dsv41/ds4_model.cu:9147-9167,9245-9259`: 同期 host-routing 経路での host copy / event wait / CPU expert 処理。
