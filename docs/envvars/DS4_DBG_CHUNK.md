# `DS4_DBG_CHUNK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版の DeepSeek V4.1 エンジンで、`Model::feed` の入力 token 数と chunk 設定を stderr に出す診断フラグです。chunked prompt の実行を有効化したり、chunk の大きさを変更したりはしません。

## 値と判定

| ビルド | 未設定 | 設定時 |
|---|---|---|
| Metal (`STRATA_METAL`) | 出力しない | 空文字を含め、値が存在すれば出力する。値の文字列・数値は parse しない |
| CUDA / HIP (`STRATA_METAL` なし) | 出力しない | 常に出力しない。`ds4_dbg` はコンパイル時定数 `false` |

既定値は無効です。CLI 引数や他の環境変数との優先順位はなく、この変数は診断出力だけを選びます。chunk の設定と経路選択は別途 `--prefill-chunk`、`DS4_CHUNK`、`DS4_CHUNK_MIN` などで決まります。

## 有効になる条件

- `STRATA_METAL=1` を定義してビルドした Metal 版 `strata_ds4` であること。Metal の CMake target は `src/dsv41/ds4_model.cu` を含み、同 target に `STRATA_METAL=1` を定義します。
- モデルの `feed` が呼ばれること。chunk の実行設定や入力長にかかわらず `feed n ...` の行を出します。
- 2行目の `forward_chunks n ...` は `forward_chunks` に入った場合だけ出ます。通常の `feed` では `chunk > 0` かつ `n >= chunk_min` の上で、`logits_rows > kWin` または `pick_path(n)` が真のときこの関数が呼ばれます。`feed_mark` からも条件を満たして `pick_path(n)` が真なら呼ばれます。

## 実行時の詳細

Metal では `ds4_dbg(name)` が `std::getenv(name) != nullptr` を返し、結果を static cache しません。したがって各診断箇所で環境を確認します。`Model::feed` は stderr に `feed n %d chunk %d chunk_min %d` を出し、chunked 関数は stderr に `forward_chunks n %d nc %d per %d` を出します。ここで `nc` は計算された chunk 数、`per` は各 chunk の token 数です。

このフラグによる警告、エラー、終了、fallback はありません。変わるのは上記の stderr 出力だけで、モデル処理の分岐や出力値には影響しません。

## 根拠

- `src/dsv41/ds4_launch.h:30-37` — Metal では設定有無を `getenv` で確認し、Metal 以外では `false` を返す helper。
- `metal/CMakeLists.txt:138-146,165-170` — Metal エンジンのソース一覧に `ds4_model.cu` が含まれ、`strata_ds4` に `STRATA_METAL=1` が定義される。
- `src/dsv41/ds4_model.cu:10702-10714` — `Model::feed` の診断行と chunk 経路の条件・呼び出し。
- `src/dsv41/ds4_model.cu:9320` — chunked 経路の診断行。
- `src/dsv41/ds4_model.cu:10716-10729` — `feed_mark` から chunked 経路に進む条件。
- `src/dsv41/ds4_model.cu:2293-2303` — chunk 値と `DS4_CHUNK_MIN` の別設定。`DS4_DBG_CHUNK` の判定には使われない。
