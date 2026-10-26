# `DS4_YOCO`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek-V4.1 の chunked prompt 処理で、十分長い prompt の先頭側について、特定の圧縮 KV 層より後の層計算を省略します。各層が必要とする過去状態を作るため、最初の対象層では KV/index key の計算だけを行い、その層より後は prompt の末尾側の必要行だけを処理します。これは `forward_chunks()` の prompt 処理に限られ、通常の1 token decode を切り替える変数ではありません。

ソースコメントはこの設定の通常名を `MAYA_DS4_PROMPT_SKIP`、Strata 名を `STRATA_DS4_PROMPT_SKIP` と記し、`DS4_YOCO` をテスト用名として説明しています。実装は `DS4_YOCO` を先に読み、未設定の場合に限って `STRATA_DS4_PROMPT_SKIP` を読みます。

## 値と判定

値は `std::atoi` で整数に変換します。文字列全体の妥当性検査はありません。先頭の空白と符号を受け付け、数字列の後ろに文字があっても数字部分を変換します。先頭から整数として読めない値（空文字を含む）は `0` となり、省略を無効にします。

| `DS4_YOCO` | `STRATA_DS4_PROMPT_SKIP` | 判定 |
|---|---|---|
| 未設定 | 未設定 | 既定値 `1`。省略モード |
| 未設定 | 設定 | alias の値を `atoi` で変換 |
| 設定 | 任意 | `DS4_YOCO` の値を `atoi` で変換。alias は読まない |
| 変換結果 `0` | 任意 | 省略しない |
| 変換結果 `2` | 任意 | 省略し、末尾の保持行数を `g.win` にする |
| 変換結果が `0` と `2` 以外 | 任意 | 省略し、既定の保持行数を使う |

明示的な空文字や `abc` は `atoi` の結果が0なので無効です。`2tail` は2として扱われます。`-1` など負の非ゼロ値は省略を有効にし、値2専用の保持行数指定には該当しません。

## 有効になる条件

値が非ゼロでも、`yoco_layer()` が対象層を見つけ、prompt の長さが十分でなければ処理は省略されません。

- chunk サイズが正で、モデルに2層以上あり、各層の圧縮率情報が揃っている。
- 圧縮率が1の最初の層が層0より後にあり、その層が後続層向けの KV source (`kv_src`) を持つ。
- 全層で `nm == 1` かつデバイスが層0と同一。実装上、複数デバイスや層の multi-member 経路では対象層を返さない。
- 対象層より後の全層が圧縮率1で、独自の `kv_src` を持たない。
- `forward_chunks()` の `logits_rows` が `kWin` 以下。全行の logits を要求する場合 (`logits_rows > kWin`) は対象層を無効化する。
- 計算した省略開始位置 `a = n - keep` が少なくとも `kYocoMin`（1024行）分 prompt の先頭側を飛ばせること。

このため短い prompt、条件に合わないモデル層構成、または全行 logits の経路では、設定が非ゼロでも通常どおり全行を処理します。

## 実行時の詳細

`yoco_mode()` は関数内 `static` に整数値をキャッシュします。最初に参照された後の環境変数変更は再評価されません。`yoco_layer()` が最初の ratio-1 層を探し、適用可能性を判定します。既定モードでは対象層以降が再計算に必要とする prompt 末尾を `keep = (g.nl - yl) * (g.win - 1) + g.win` 行保持します。mode 2 では保持行数を `g.win` とします。この式は適用可能性がある場合にのみ使われ、`DS4_YOCO_KEEP` が正なら `max(DS4_YOCO_KEEP, g.win)` 行で上書きされます。`DS4_YOCO_KEEP` が未設定または `atoi` 結果0以下なら上記モード別の既定値です。

省略を行うと、末尾側の開始位置 `a` を chunk index と chunk 内 row に分けて `Run::cut_k` / `Run::cut_r` に設定します。cut より前の chunk は対象層より前まで進み、対象層では後続層が使う圧縮 KV と index key だけを作ります。その層より後の計算は省略します。cut chunk は cut row までは同様に処理し、残りの行と後続 chunk は全層を処理します。`kv_only` 経路では attention/expert 等の通常計算を行わず、必要な KV source の計算・保存を続けます。

実装に `DS4_YOCO` 専用のログ出力はありません。リポジトリ内の GPU 前提テスト `tools/dsv41/test_prompt_skip.py` は、`STRATA_DS4_PROMPT_SKIP=0` と `1` で採点結果を比較するコードを持ちますが、この調査では実行していません。`docs/DETAILS.md` にこの設定の説明や測定値は見つかりませんでした。

## 根拠

- `src/dsv41/ds4_model.cu:8160-8171` — mode の優先順位、`atoi`、既定値1、static cache。
- `src/dsv41/ds4_model.cu:8173-8184` — chunk/model 条件、対象層の選択と multi-device/member 制限。
- `src/dsv41/ds4_model.cu:823` — 最低省略行数 `kYocoMin = 1024`。
- `src/dsv41/ds4_model.cu:8202-8217` — 長い prompt の処理概要、全行 logits の除外、保持行数と開始位置。
- `src/dsv41/ds4_model.cu:7454-7477, 7520-7527, 7568-7575, 7619-7625, 7640-7648` — chunk/layer のスキップと cut 行からの処理。
- `src/dsv41/ds4_model.cu:7025-7030, 7064-7068, 7224` — `kv_only` が通常計算を省き、KV source の処理後に戻る経路。
- `tools/dsv41/test_prompt_skip.py:1-11, 38-52` — テストの適用条件と比較方法（本番挙動の根拠ではなく、調査時点で未実行）。
