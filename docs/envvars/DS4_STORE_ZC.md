# `DS4_STORE_ZC`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DS4 の RAM expert store にある expert を GPU から参照できるよう、store の arena chunk を GPU に登録し、decode 時に選ばれた expert を GPU 側の staging buffer にコピーして GPU 計算へ渡します。設定しない場合、この GPU mapping 経路は構成されません。これは DS4 実装の opt-in です。

## 値と判定

`src/dsv41/ds4_model.cu` は `DS4_STORE_ZC` が設定されているかを調べたうえで `std::atoi()` の結果が 0 以外かを判定します。文字列全体の厳密な数値検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | `atoi("") == 0` のため無効 |
| `0`、`00`、`false`、数値で始まらない文字列 | `atoi()` が 0 を返すため無効 |
| `1`、`-1`、`2abc` など、`atoi()` が 0 以外を返す文字列 | 要求あり。後述の条件をすべて満たす場合に限り mapping を試みる |

## 有効になる条件

要求値が非 0 でも、store の初期化自体に成功する必要があります。`init_store()` は store 容量が正、layer が存在し、先頭 layer の形式が MXFP4 で、expert がファイル由来の場合にのみ store 初期化を進めます。さらに `DS4_STORE_ZC` の要求は、GPU が1台（`devs.size() == 1`）かつ `L[0].nm == 1` の場合だけ採用されます。

採用時は arena chunk ごとに `cudaHostRegisterMapped | cudaHostRegisterPortable` で host memory 登録を試し、device pointer の取得も試みます。store が GPU mapped と判定されなければ `zero-copy off` とログに出して各 layer の ZC 管理を解除します。staging buffer または layer table の GPU allocation に失敗した場合も ZC 用の layer 管理が解除されます。したがって変数が非 0 であるだけでは有効化を保証しません。

統合 GPU の場合、取得できた device properties が integrated を示し、かつ GPU の空きメモリーが store 容量より少ないと、stderr にメモリー圧迫の警告を出します。警告は無効化や fallback を実行する分岐ではありません。

## 実行時の詳細

判定は DS4 model の `init_store()` 中に行われます。環境変数の再読み込みや、初期化済み model への動的な適用はありません。

store chunk が GPU mapping されると、window 境界で ready な store slot の一部が device table に登録されます。`DS4_STORE_ZC_FRAC`（別変数）が GPU 可視 expert の選別率を制御し、既定値は 50 です。GPU 可視の候補は、VRAM にない expert、pin 中でない slot、prefetch ではない slot に限定され、slot 予約数を確保するため一部が後で可視状態から戻されることもあります。

decode の token 数が 1 の経路では、device table に該当 expert の store address があると、GPU kernel が host memory から expert blob を staging buffer へコピーし、実行 plan をその staging copy に向けます。CPU 側の expert load はこの token では省略されます。prompt など token 数が 1 以外の経路は、この ZC staging 分岐を通りません。expert が VRAM に戻ると device table の entry を消し、slot の再利用時に古い pointer を使わないようにします。

## ログと資料との照合

初期化成功時は RAM store の slot 数・容量・policy・reader 数・読み取り方式を stderr に出します。ZC 要求時は `ds4: RAM store: the GPU takes its slots over PCIe (...)` を出し、mapping 失敗なら `ds4: RAM store: the arena could not be mapped for the GPU: zero-copy off` を出します。統合 GPU の警告文は `DS4_STORE_ZC=1` と表記しますが、実際の判定は値が `1` と等しいかではなく、`atoi()` が 0 以外かです。

ソースコメントは RTX 5070 / PCIe 5.0 で staging copy が layer の critical path に入り、CPU lane 単独より遅かった測定を理由に opt-in としています。また回答は CPU lane の mmap path と byte for byte 同一ではないとも記しています。測定回数やモデルなどの条件はこのコメントに記載がないため、一般的な性能・正確性の保証としては扱えません。`docs/DETAILS.md` にはこの DS4 変数を直接説明する記述は見つかりませんでした。

## 根拠

- 値の読み取り、適用条件、GPU memory 登録、統合 GPU 警告、mapping と staging allocation の fallback: `src/dsv41/ds4_model.cu:4633-4707,4721-4745`
- slot の GPU 可視化条件と予約 slot の確保: `src/dsv41/ds4_store.hpp:286-330`
- decode 1 token での staging 経路と GPU 計算への plan 差し替え: `src/dsv41/ds4_model.cu:9077-9093`, `src/dsv41/ds4_kernels.cu:1879-1903`
- expert が VRAM に戻る際の table entry 解除: `src/dsv41/ds4_model.cu:6282-6295`
- ZC opt-in と測定に関するソース注釈: `src/dsv41/ds4_model.cu:4665-4668`
