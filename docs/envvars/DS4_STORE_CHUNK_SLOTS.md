# `DS4_STORE_CHUNK_SLOTS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の RAM expert store で、一度に確保する arena の chunk の slot 数を指定します。GPU zero-copy 登録を使う場合、同じ chunk が GPU マッピングの単位です。実装コメントでは registration segment size を調整する「test knob」とされています。

この値は store の総 slot 上限を直接増減しません。総 slot 上限は store の byte budget と expert 1個分の slot サイズから別に決まり、`DS4_STORE_CHUNK_SLOTS` はその slot を何個ずつ確保・解放するかを変えます。

## 値と判定

値は `std::atol` で `long` に変換し、8 以上 4096 以下の場合だけその値を slot 数として採用します。変換結果がこの範囲外なら 64 に戻ります。

| 環境変数の状態・値 | 採用される chunk slot 数 |
|---|---:|
| 未設定 | 64 |
| 空文字、数値に変換できない文字列、`0`、`7`、負値 | 64 |
| 8 以上 4096 以下に変換される値 | 変換結果 |
| 4097 以上に変換される値 | 64 |

`atol` を使うため、文字列全体の厳密な数値検証はありません。先頭の空白と符号は変換規則に従い、数値の後ろに続く文字は検査されません（例: `8tail` は 8 として扱われます）。したがって空文字や非数値文字列は 0 に変換され、既定値 64 になります。

## 有効になる条件

環境変数の値は `ExpertStore` 構築時に読み取られます。実際に store が使われるには、DS4.1 エンジンの該当実装がビルドに含まれ、モデルの RAM store が有効である必要があります。`init_store()` は store サイズが正、層が存在し、先頭層の形式が MXFP4 で、expert がファイルから読む構成の場合に store を作ります。初期化が失敗した場合、呼び出し元は `ds4: --ssd-cache: the store could not start` を stderr に出します。

GPU 登録 chunk になるのは、別変数 `DS4_STORE_ZC` などの条件により `ExpertStore::Cfg::map_chunk` が設定される場合です。GPU 登録がない場合も chunk による RAM 確保・解放単位として値は使われます。

## 実行時の詳細

`ExpertStore` の各インスタンスはメンバー初期化時に `chunk_slots()` を呼び、その時点の環境から `kChunk` を決めます。値はプロセス全体の static cache には保存されませんが、構築後の当該インスタンスでは固定されます。

初期化時には `nmax`（budget 内に収まる slot 数）を `kChunk` 単位に切り上げて arena の仮想アドレス範囲を予約します。実 commit は最初に1 chunk を行い、以降 slot が必要になるたび `min(kChunk, 残り slot 数)` 個ずつ増やします。RAM 残量が chunk の byte 数と `floor_bytes` の合計を下回る場合や commit が失敗した場合、その grow は行われません。GPU mapping callback がある場合は、この単位の領域を登録します。Linux で GPU mapping がある構成では `DS4_STORE_PREGROW` の既定動作により全 chunk を初期化時に grow します。

RAM が不足した際の `shrink_chunks()` は末尾から chunk ごとに解放しますが、chunk 内に pinned、GPU-visible、または読み込み中の slot があるとそこで停止します。したがって chunk 数を大きくすると確保・GPU 登録・解放の単位も大きくなります。起動時の RAM store ログには最終的な slot 数と byte 数が出ますが、この変数の値そのものを示すログは確認できません。

## 根拠

- `src/dsv41/ds4_store.hpp:387-393`: `getenv` / `atol` による範囲判定、既定値、およびインスタンスごとの `kChunk`。
- `src/dsv41/ds4_store.hpp:73-108,480-493`: arena 予約、初回 grow、pregrow、chunk ごとの commit / GPU mapping。
- `src/dsv41/ds4_store.hpp:332-369`: chunk 単位での解放と、使用中 slot があれば停止する条件。
- `src/dsv41/ds4_model.cu:4633-4642,4657-4715`: DS4.1 RAM store の起動条件、GPU mapping callback、初期化失敗時のログ。
- `src/dsv41/ds4_model.cu:4721-4723`: 起動時に出す RAM store slot 数・サイズのログ。
- `docs/DEEPSEEK41.md:50-53,104`: DS4.1 の実行経路および RAM store の概要。`DS4_STORE_CHUNK_SLOTS` の値や効果は説明していないため、詳細は上記ソースに基づく。
