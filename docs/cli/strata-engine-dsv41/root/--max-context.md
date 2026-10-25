# `--max-context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立 engine CLI） |
| オプション | `--max-context` |
| 別名 | なし |
| 値 | 整数 `N`（トークン数として扱う） |

## 役割

DeepSeek-V4.1 engine が扱う context の上限を指定します。prompt の処理可能量と生成可能量を制限し、上限に応じた GPU scratch および圧縮 KV/indexer 用容量の確保に使われます。オプションは `strata-dsv41` の root parser に属します。この実行ファイルは `STRATA_BUILD_DSV41=ON` の CMake build で生成されます（`CMakeLists.txt:797-810`）。

## 使い方

```sh
strata-dsv41 --pack ./model/maya-ds4 --max-context 65536 --serve
```

`--pack` にモデル pack のディレクトリを指定し、`--serve` で起動する例です。`--max-context` を省略した場合はモデル実装の既定値が使われます。

## 値と既定値

- 値は `--max-context` の直後の引数を `std::atoll` で読み取ります。option の値が省略された場合は `--max-context needs a value` を stderr に出し、終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207,1212`）。
- parser に数値の形式・正数・上限の validation はありません。非数値文字列を含む値は `atoll` の変換結果がそのまま設定されます。負数や 0 を有効な context として使える保証はソース上で確認できません。
- 既定値は `32768`（`src/dsv41/ds4_model.hpp:25-29`）。
- 同じ option を複数回指定した場合は parser の走査順で後の指定が `o.max_context` を上書きします（`src/dsv41/ds4_main.cpp:1200-1213`）。

## 実行時の動作

- `Model::load` に option 値を渡し（`src/dsv41/ds4_main.cpp:1286-1293`）、圧縮 KV の source ごとの容量を `(max_context + ratio - 1) / ratio + 1` で算出します（`src/dsv41/ds4_model.cu:2035-2041`）。
- GPU ごとの scratch では `max_context + 64` を容量として score buffer 等を確保します（`src/dsv41/ds4_model.cu:2251-2262`）。したがって大きな値は確保量を増やし、GPU メモリ確保に影響します。`cudaMalloc` が失敗するとモデル load は失敗し、main はエラーを `maya-ds4: ...` として stderr に出して終了コード 1 を返します（`src/dsv41/ds4_model.cu:1282-1290`; `src/dsv41/ds4_main.cpp:1289-1294`）。
- prompt の feed は `pos + T > max_context` のとき `the context is full` で失敗します（`src/dsv41/ds4_model.cu:7891-7896,8277-8285`）。通常の `--ids` 実行ではこの失敗を `maya-ds4: ...` として stderr に出し、終了コード 1 で終了します（`src/dsv41/ds4_main.cpp:1360-1365`）。
- `--serve` 起動時は `READY <context> stop` に上限値を出します（`src/dsv41/ds4_main.cpp:318-323`）。各要求では prompt token 数と正の `max_new` の合計が上限を超えると stdout に `ERR ... more than the context ...` を出して、その要求を拒否して次の要求へ進みます（`src/dsv41/ds4_main.cpp:722-727`）。`max_new` が正でないときは生成 limit を残り context から計算し、decode は context 上限で止まります（`src/dsv41/ds4_main.cpp:837-840,891-894`）。
- `--n` を使う直接実行では、生成数の指定とは別に model の context 上限が適用されます。上限に達した後の feed が失敗すると stderr にエラーを出して終了コード 1 になります（`src/dsv41/ds4_main.cpp:1385-1405`; `src/dsv41/ds4_model.cu:7891-7896`）。

## 適用条件と副作用

- `--pack-info` は引数処理後、モデルをロードする前に処理を終了するため、このモードでは `--max-context` はモデル容量に適用されません（`src/dsv41/ds4_main.cpp:1275-1280`）。それ以外の通常のモデル load 経路では `--serve`、`--ids`、画像 encoder 等の動作に先立ち load に渡されます（`src/dsv41/ds4_main.cpp:1282-1296`）。
- option 固有の環境変数上書きや、値の clamp/fallback は確認できません。context 値は `INFO context` と `INFO kv_resident` にも出力されます（`src/dsv41/ds4_model.cu:9008-9016`）。
- 受理される最小値・最大値は parser で定義されていません。特に 0、負数、極端に大きい数を指定した際の安全な動作は保証できません。モデル load の GPU 容量確保や後続処理で失敗し得るため、正の実用値を指定してください。

## 出力とエラー

- 値の欠落: stderr に `--max-context needs a value`、終了コード 2。
- GPU scratch 確保失敗: load エラーを stderr に出力し、終了コード 1。
- serve の要求が上限を超過: stdout に `ERR ...` を出し、その要求を拒否して serve は継続。
- 直接 prompt feed が上限を超過: stderr に `maya-ds4: the context is full` 相当のエラーを出し、終了コード 1。

## 根拠

- parser、値変換、欠落値エラー、実行モード分岐: `src/dsv41/ds4_main.cpp:1187-1213,1275-1296`
- 既定値と option 構造体: `src/dsv41/ds4_model.hpp:25-29`
- 圧縮 KV capacity と GPU scratch 容量: `src/dsv41/ds4_model.cu:2035-2041,2251-2262`
- CUDA 割当て失敗の伝播: `src/dsv41/ds4_model.cu:1282-1290`; `src/dsv41/ds4_main.cpp:1289-1294`
- context 境界の検査: `src/dsv41/ds4_model.cu:7891-7896,8277-8285`
- serve の READY 表示、要求 validation、生成 limit: `src/dsv41/ds4_main.cpp:318-323,722-727,837-840,891-894`
- 直接実行の prompt feed と `--n` decode: `src/dsv41/ds4_main.cpp:1360-1365,1385-1405`
- 索引での option scope と build 条件: `docs/cli/README.md:1353-1374`; `CMakeLists.txt:797-810`

調査時の Strata checkout は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。Release artifact の配布有無、同一 revision の build 済み CLI help、および境界値の実行結果は確認していません。
