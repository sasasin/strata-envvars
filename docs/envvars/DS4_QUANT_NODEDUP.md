# `DS4_QUANT_NODEDUP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の DSV41 GGUF device `mv()` で、同一の活性値入力を int8 に量子化する job が複数ある場合に、量子化結果を共有する最適化を無効にします。設定時は同一入力でも各 job を別 item として登録し、量子化を個別に行います。変数名の `NODEDUP` はこの重複 item の排除を無効にする意味です。

## 値と判定

値の内容は parse せず、`std::getenv("DS4_QUANT_NODEDUP") != nullptr` だけで判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | 重複排除を行う。同じ活性値ポインタ、stride、row 数、幅 `k` の item が既にあれば、その item の量子化結果を共有する |
| 設定あり | 重複排除を行わない。値が `1` 以外でも、空文字でも有効 |

文字列の大小文字、数値としての妥当性、空白、値の範囲は関係しません。

## 有効になる条件

この判定があるのは CUDA 実装 `src/dsv41/ds4_gguf.cu` の `quant_add()` です。`mv()` の GGUF (`kFmtGG`) と Q8_0 job が量子化 item を追加します。BF16 と MXFP4 の job はこの `quant_add()` を通りません。このため、変数が設定されていても、該当 `mv()` 呼び出しに同一入力の GGUF または Q8_0 job がなければ重複排除の差はありません。

## 実行時の詳細

`mv()` ごとに `QuantItems` を初期化し、job を順に `quant_add()` へ渡します。重複排除が有効な場合、`x` ポインタ・`ldx`・`rows`・`k` の4項目が一致すると既存 item の番号を返します。呼び出し側はその item の `q` と `d` を後続の GEMV job に設定します。重複排除を無効にすると、この検索ループを飛ばし、job ごとに独立した scratch の出力領域を登録します。

job 登録後、`quant_flush()` が登録 item を CUDA stream 上で量子化します。通常は複数 item を `q8_quant_multi_kernel` の1 launch で処理し、別変数 `DS4_QUANT_SINGLE` が設定されていれば単一 item ごとの `q8_quant` launch に切り替わります。`DS4_QUANT_NODEDUP` 自体は量子化の計算式や launch 方式を変えません。

設定有無は `quant_add()` 内の function-local `static const bool` に初期化されます。したがってプロセス内では最初に `quant_add()` が評価されたときの値が保持され、以降の環境変更は再評価されません。各 `mv()` の `QuantItems` は呼び出しごとに作り直されるため、同一呼び出し内の job 間でだけ重複が検出されます。

## 根拠

- `src/dsv41/ds4_gguf.cu:230-242`: 環境変数の判定、重複 item の一致条件、および item 追加処理。
- `src/dsv41/ds4_gguf.cu:244-258`: 量子化結果を生成する単一 item / multi-item の処理。
- `src/dsv41/ds4_gguf.cu:1129-1164,1189-1205`: `mv()` の初期化、GGUF および Q8_0 からの追加、結果参照と flush。
- `docs/DETAILS.md` にこの変数の説明や測定値は見つからなかったため、性能や結果への測定済み影響は記載していません。
