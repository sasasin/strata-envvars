# `DS4_STORE_PREGROW`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 の RAM expert store が持つ予約済み arena について、初期化時に追加チャンクを先に commit するかを制御します。CUDA/HIP のゼロコピー用にチャンクを GPU へ map する経路では、Linux の既定で store の使用可能チャンクを先に確保・登録します。無効にすると、初期化で最初のチャンクだけを確保し、残りは slot が必要になったときに `grow()` が確保します。

この変数は store の有効化や容量を決めません。store 自体は `--ssd-cache` / `DS4_STORE_GB` などで容量が正になり、MXFP4 のファイル expert を扱うときに限り初期化されます。

## 値と判定

値は `std::atoi` で整数変換し、0 かどうかだけを見ます。文字列全体の妥当性検査はありません。

| ビルド時の `__linux__` | 未設定 | 設定値で有効 | 設定値で無効 |
|---|---|---|---|
| 定義あり | `cfg_.map_chunk` がある場合に有効。ない場合は無効 | `atoi(value) != 0` で、かつ `cfg_.map_chunk` がある場合 | `atoi(value) == 0` または `cfg_.map_chunk` がない場合 |
| 定義なし | 無効 | `atoi(value) != 0` | `atoi(value) == 0` |

`atoi` のため、空文字・数値で始まらない値・`0` は0として無効です。`1`, `-1`, `2tail` はそれぞれ非0として有効です。`unset` は Linux では既定判定に入り、Linux 以外では無効です。Linux では設定値が非0でも GPU mapping callback がなければ有効になりません。

## 有効になる条件

`ExpertStore::init()` に到達するには、モデル起動時に store 容量が正で、モデルの layer があり、先頭 layer の形式が MXFP4 で、expert がファイルから読まれる必要があります。初期化時には最初の arena chunk の `grow()` を必ず試した後、この変数を評価します。

`cfg_.map_chunk` は、`DS4_STORE_ZC` が設定されて `atoi(...) != 0` であり、かつ単一 GPU で `L[0].nm == 1` の場合に設定されます。この条件を満たすと、callback は各 chunk を `cudaHostRegisterMapped | cudaHostRegisterPortable` で登録して device pointer を取得します。HIP ビルドでは `DS4_ZC_COARSE` の追加フラグ分岐もありますが、`DS4_STORE_PREGROW` 自体の判定は同じです。

各 `grow()` は予算上限と `ram_avail >= chunk_bytes + floor_bytes` を満たす必要があります。満たさない場合、または range commit に失敗した場合はそこで止まり、残りを事前確保しません。GPU mapping callback の失敗は chunk の host 側確保を取り消さず、`grow()` はその chunk の device pointer が null のまま成功します。

## 実行時の詳細

読み取りはモデルロード中の `init_store()` から呼ばれる `ExpertStore::init()` 内で一度行われます。値は static cache されていませんが、この `ExpertStore` の初期化後に環境を書き換えても既に確保した chunk には影響しません。

初期化では、まず `grow()` で一つ目の chunk を確保します。その後、判定が有効なら `while (grow())` で可能な限り追加 chunk を確保します。したがって Linux で `DS4_STORE_PREGROW=0` としても store は無効にならず、最初の chunk は初期化時に確保されます。後続の chunk は `take_slot()` が既存の空き slot を使い切った際に需要に応じて確保されます。

設定値に固有のログはありません。store が開始できない場合は `ds4: --ssd-cache: the store could not start`、開始時には slot 数・容量・読み取り方式を示す `ds4: RAM store: up to ...` が stderr に出ます。これらのログは pregrow の成否を直接示しません。

## 根拠

- `src/dsv41/ds4_store.hpp:73-108`: arena 初期化、最初の chunk 確保、OS 条件ごとの `DS4_STORE_PREGROW` 判定と追加 `grow()`。
- `src/dsv41/ds4_store.hpp:480-493`: `grow()` の容量・RAM floor・range commit 条件。GPU mapping が失敗しても chunk 自体は追加する。
- `src/dsv41/ds4_store.hpp:495-503`: 通常の slot 取得時にも `grow()` を呼ぶ。
- `src/dsv41/ds4_model.cu:2815-2823`: パス調整後、モデルロード中に store 初期化と preload を実施。
- `src/dsv41/ds4_model.cu:4633-4715`: store の有効条件、予算、`DS4_STORE_ZC` に基づく mapping callback、初期化失敗ログ。
- `docs/DEEPSEEK41.md:48-53, 99-104`: DeepSeek V4.1 の store はモデル起動時に容量を決めるとの説明。`DS4_STORE_PREGROW` の値や eager commit の条件は説明していない。
