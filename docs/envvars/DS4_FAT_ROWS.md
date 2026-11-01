# `DS4_FAT_ROWS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で未コミット変更なし。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek-V4.1 専用エンジン `strata-dsv41` の CUDA 経路で、ルーティングされた行数が一定以上の expert を「busy experts」用の FP16 GEMM 経路へ振り分けます。環境変数の値は expert ごとの行数しきい値です。対象 expert の重みを FP16 に復元して GEMM で処理し、しきい値未満の expert は従来の tile kernel に残します（`src/dsv41/ds4_model.cu:3468-3478,4209-4254`）。

## 値と判定

`std::atoi` で整数変換し、負値は `std::max(0, ...)` で 0 にします。正の値は最低 17 に丸めます。tile 側が 16 行以下の expert を扱うため、17 未満を指定しても 17 行以上が対象になります。未設定時と、変換後が 0 以下の場合は無効（しきい値 0）です（`src/dsv41/ds4_model.cu:3474-3479`）。

| 設定値 | 判定結果 |
|---|---|
| 未設定、空文字、`0`、`abc` | 無効（0）。空文字・数字で始まらない文字列は `atoi` が 0 に変換 |
| 負の整数（例 `-5`） | 無効（0） |
| 正の整数 1〜16 | 17 に丸める |
| 17 以上の正の整数 | その整数をしきい値にする |
| 数字の後ろに文字が続く値（例 `64abc`） | `atoi` が読み取る先頭の整数部分を使う（例では 64） |

`atoi` のため文字列全体の厳密な数値検証はしません。整数として表現範囲を超える値の結果は保証されません。CLI 引数や設定値による上書き処理はこの変数の読み取り箇所にはありません。

## 有効になる条件

しきい値が正でも、次の条件が満たされる `run_set` に限って経路が利用可能です（`src/dsv41/ds4_model.cu:3481-3502,4181-4215`）。

- `strata-dsv41` が CUDA backend で動作している。HIP と Metal では `fat_ready()` が常に `false` を返し、CUDA の確保・計算を行いません。
- 対象 layer が MXFP4 形式で、`gg::mx_experts()` に該当しない。
- `D` と `FF` がともに 256 の倍数。
- gate と up の expert 型が同じで、gate/up と down の型の双方が `f16_rows_ok()` を満たす。
- その Chunk で FP16 重み・入力・中間値用の GPU メモリ確保に成功する。

これらの条件が欠けると FP16 GEMM 経路へは振り分けず、tile 経路が処理します。条件を満たしても、実際にその Chunk 内の expert がしきい値以上の行数を持つ場合だけ対象になります。しきい値以上の expert がある場合、`skip_ge` を設定して gate/up と down の tile kernel からその expert を除き、FP16 GEMM で代わりに計算します（`src/dsv41/ds4_model.cu:4216-4254`; tile kernel の除外判定は `src/dsv41/ds4_iq.cu:742-746,834-838`）。

## 実行時の詳細

値は `fat_rows()` の関数内 static 変数に初回評価結果を保存します。評価されるのは対象の `run_set` が `fat_ready()` に到達したときで、同じプロセスでは以降の環境変更を再読込しません。FP16 バッファは各 Chunk で初回利用時に確保され、成功時に `ds4: CUDA%d busy experts (%d rows or more) as FP16 GEMMs, %d rows a piece (%.0f MB)` を stderr に出します。確保に失敗すると `no VRAM for the busy experts' path ...: the tiles take them` を出してその Chunk の `fat_off` を立て、tile 経路に戻ります（`src/dsv41/ds4_model.cu:634-667,3481-3501`）。

計算は gate/up と down の重みを `f16_rows()` で FP16 に復元し、`cublasGemmEx` で処理します。`DS4_FAT_PIECE` は別の環境変数で、入力を GEMM に渡す行数単位を設定します。しきい値自体は変更しません（`src/dsv41/ds4_model.cu:3488-3500,3505-3541`）。この経路は同じ積を使うものの和の順序が異なる、とソースコメントに記されています（同 `:3470-3473`）。

FP16 復元または GEMM が失敗すると helper は `false` を返し、`run_set` も失敗を返します。設定値の不正を知らせる専用警告や値の正規化ログはありません。確認できた有効化・メモリ不足ログは上記の通りです（`src/dsv41/ds4_model.cu:3508-3521,3528-3541,4243-4254`）。ビルドでは `STRATA_BUILD_DSV41` が既定 OFF で、CUDA/HIP backend のビルド設定内に別 executable `strata-dsv41` が定義されます。GPU backend なしではこの実行ファイルではなく host-side benchmark のみです（`CMakeLists.txt:906-920,2780-2793`）。

## 根拠

- 全参照検索では候補名は `src/dsv41/ds4_model.cu` のコメントと読み取り箇所に限られ、`getenv` を含む読み取りは `:3476` のみでした。共通 helper や動的な名前渡しによる追加読み取りはありません。
- DeepSeek-V4.1 が専用エンジン `strata-dsv41` を使うこと、およびビルド方法は `docs/DEEPSEEK41.md:1-6,92-94` に記載されています。同資料に `DS4_FAT_ROWS` 固有の説明はありません。
