# `DS4_PICK_MIN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンの prompt 入力で、長さがこの閾値以上なら chunked pass（全 layer を chunk 単位で処理する経路）、未満なら 16-token windows の経路を選びます。既定の閾値は 96 token です。閾値はモデルごとに最初に読み込んだ値を保持します。

## 値と判定

| 環境変数の状態 | 閾値 |
|---|---:|
| 未設定 | 96 |
| 空文字 | 96 |
| 先頭から `atoi` が 1 以上の整数として読む文字列 | その整数 |
| `atoi` が 0 以下を返す文字列 | 1 |

読み取りは `prompt_flow_min()` で行い、空でない値は `std::atoi()` に渡した後、1 未満を 1 に clamp します。したがって `0`, `-4`, `abc`, `0tail` は 1、`12tail` は 12、`+24` は 24 になります。先頭の空白と符号は `atoi` の変換規則に従い、整数部分の後ろにある文字列は判定に使われません。明示的な上限 clamp はありません。

## 有効になる条件

- DeepSeek-V4.1 の `Model` が chunked prompt 経路を持つ場合に使われます。`feed()` は `chunk > 0` かつ `n >= chunk_min` の場合にのみ path selection を行い、それ以外は windows を使います。
- `logits_rows > kWin` の場合、`feed()` は閾値判定を短絡し chunked pass を選びます。
- `DS4_PICK=adaptive` が完全一致で設定されている場合、`pick_path()` は適応選択に入ります。この経路の通常の閾値比較では `DS4_PICK_MIN` を使いません。適応選択が利用可能な予測情報を持たない場合（`pm.on` が false）や `n >= kPickMax` の場合は chunked pass を選びます。
- `feed_mark()` も `n >= 2`、`chunk > 0`、`n >= chunk_min` の場合に `pick_path()` を通しますが、`feed()` の `logits_rows > kWin` による短絡条件はありません。

## 実行時の詳細

モデル load の終盤で `chunk > 0` なら `pick_flow_min()` が呼ばれ、stderr に `ds4: prompt path: the chunked pass from %d tokens, windows of 16 below` を出します。ここで `pick_min_` が正の値なら保持済みの値を返し、まだ値がなければ環境変数を読みます。`pick_path()` の固定選択では `n >= pick_flow_min()` が真なら chunked pass、偽なら windows です。環境変数をモデル load 後に変更しても、すでに読み込まれた閾値には反映されません。

`DS4_PICK=adaptive` は別の選択モードです。実装はこの名前と文字列全体を `strcmp` で比較し、同モードでは実測・予測情報と expert の RAM residency を使って path を選ぶため、`DS4_PICK_MIN` は固定閾値として path を決定しません。`DS4_PICK_MIN` の説明や測定結果は `docs/DETAILS.md` では確認できませんでした。ソースコメントは既定値 96 の背景として複数環境での測定を記していますが、ここではその数値を独自に検証した測定結果として扱いません。

## 根拠

- `src/dsv41/ds4_pick_rule.hpp:18-27` — 既定値 96、unset/empty の既定処理、`atoi` と最小値 clamp、閾値比較。
- `src/dsv41/ds4_model.cu:7982-7997` — モデル内キャッシュ、環境変数の読み取り、起動ログ、`DS4_PICK=adaptive` の判定と閾値を使わない分岐。
- `src/dsv41/ds4_model.cu:2823-2825` — load 終盤の閾値初期化。
- `src/dsv41/ds4_model.cu:9356-9382` — `feed()` と `feed_mark()` の path 選択条件。
- `src/dsv41/ds4_model.cu:6-15,809` — この実装を含む DeepSeek-V4.1 エンジンのソースと実行ファイルの構成。
- `docs/DETAILS.md` — `DS4_PICK_MIN` の直接の記載は確認できませんでした。
