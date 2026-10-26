# `DS4_XIN_DUMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の chunked prompt 経路で、各 trunk layer の router 入力ベクトルをバイナリファイルに記録する診断用フックです。通常の短い prompt / decode の window 経路には、この書き出し箇所はありません。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | ファイルを開かず、記録しない。 |
| 設定あり、指定パスを `fopen(..., "wb")` で開ける | `Model::Impl` の生成時にファイルを開き、対象データを記録する。既存ファイルは `wb` により切り詰められる。 |
| 空文字、または開けないパス | `fopen` が null になり、記録しない。エラーは検査・報告されない。 |

値の文字列を数値や真偽値として parse しません。設定値全体がファイルパスとして使われます。環境変数は `Model::Impl` のメンバー初期化時に読み取られるため、同じモデルインスタンスの実行中に環境を変えても反映されません。モデルの再生成では再評価されます。

出力上限は別の `DS4_XIN_N` で決まります。同変数は未設定時 1024、設定時は `atoi` で変換されます。これは記録対象の各 layer ごとの上限です。`DS4_XIN_N` が 0 以下なら記録条件を満たさず、出力レコードは追加されません。

## 有効になる条件

- `Model::feed` から chunked prompt 経路が選ばれ、`forward_chunks` が layer-major の chunk 処理を行うこと。通常の window 経路からは記録されません。
- 対象が trunk layer であること（`l.mtp` の drafter layer は除外）。
- layer group の member index `mi` が 0 であること。group の他の member では書き出しません。
- 当該 layer の記録数が `DS4_XIN_N` の上限未満であること。

`DS4_XIN_DUMP` が設定されてファイルを開けても、これらの条件を満たす chunk がなければレコードは書かれません。記録の `fwrite` 戻り値も検査されません。

## 実行時の詳細

各レコードは、3 byte のヘッダーと router 入力ベクトル群です。ヘッダーは `u8 layer` と `u16 tk`（今回のレコードに含める token 数。下位 byte、上位 byte の順）で、続けて `tk × D` 個の `float`（fp32）をホスト表現の生データとして書き込みます。`D` はモデルの router 入力次元です。レコード間に別の区切りはありません。

一つの chunk からは最大 32 token を記録します。実装は `stride = max(1, T / tk)` とし、chunk 内の行 `min(T - 1, i * stride)` を選びます。chunk を処理するごとに layer ごとの累計 `xin_got` を増やし、`DS4_XIN_N` に達した後はその layer の記録を止めます。このため上限が 1024 の場合も、1 chunk から一度に 1024 件を出すのではなく、複数 chunk にわたり最大 32 件ずつ記録します。

ファイルポインターは `Model::Impl` のフィールドで、同実装のデストラクターにはこのポインターを `fclose` する処理がありません。`fwrite` のエラーや部分書き込み、`fopen` 失敗についてもログ・エラー返却はありません。

## 根拠

- `src/dsv41/ds4_model.cu:572,800-825,1151-1156`: `mi` が layer group 内の member index であること、`Model::Impl` のフィールド初期化、ファイルを開く処理、`DS4_XIN_N` の既定値と layer ごとのカウンター。
- `src/dsv41/ds4_model.cu:9352-9368`: モデルインスタンス生成と `feed` が chunked prompt / window 経路を選ぶ条件。
- `src/dsv41/ds4_model.cu:7325-7354`: trunk layer・`mi == 0` の条件、chunk 単位の最大件数、stride による行選択、バイナリヘッダーと fp32 入力の書き出し。
- `src/dsv41/ds4_model.cu:1243-1286`: `Model::Impl` のデストラクター。`xin_f` を閉じる処理はない。
- `docs/DETAILS.md`: `DS4_XIN_DUMP` の追加説明・測定値は確認できなかった。
