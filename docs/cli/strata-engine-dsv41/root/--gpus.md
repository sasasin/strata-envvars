# `--gpus`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41` |
| オプション | `--gpus` |
| 別名 | なし |
| 値 | GPU device ID の整数列。usage 例はカンマ区切り（`0,1,...`） |

## 役割

推論エンジンが使用する CUDA device ID を指定します。`--tp` などの並列化設定とは別に、利用対象となるデバイスの集合と順序をこの値で決めます。エンジンは指定順に device を初期化し、その並びを後続のモデル配置に使います。

## 使い方

```sh
strata-dsv41 --pack /models/maya-ds4 --gpus 0,1 --ids 1,2,3
```

`--pack` にはモデル pack、`--ids` には入力 token ID 列を指定する例です。`strata-dsv41` は `STRATA_BUILD_DSV41=ON` で生成される独立 engine CLI で、CMake 上では既定 OFF です。Release での配布有無はこの調査では確認していません（`CMakeLists.txt:797-811`、索引 [`README.md`](../../README.md#strata-dsv41-optional-deepseek-v41-engine-executable)）。

## 値と既定値

- 値は必須です。値が後続引数なしで終わると `--gpus needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。
- `parse_ids` は10進整数を読み、各整数の後ろにあるカンマまたは ASCII 空白を読み飛ばします（`src/dsv41/ds4_main.cpp:71-83`）。usage は `0,1,...` の形を示します（同 `:85-94`）。
- 明示値を省略した場合の `Options::gpus` は空です（`src/dsv41/ds4_model.hpp:25-29`）。モデルロード時に空なら、CUDA が報告する全 device ID `0` から `ndev - 1` が選ばれます（`src/dsv41/ds4_model.cu:1870-1878`）。
- `--gpus` を複数回指定すると、各回の解析結果が既存リストへ追加されます（`src/dsv41/ds4_main.cpp:1210-1212`）。重複 ID を除去する処理は確認できません。
- parser は整数列全体の厳密な検証を行いません。整数として読めない位置で解析を止め、それまでの整数を返します。値の先頭が整数として読めなければ空リストとなり、結果的に全可視 GPU を選ぶ可能性があります。負数、重複、device 数を超える ID の範囲検査もこの parser にはありません（`src/dsv41/ds4_main.cpp:71-83,1210-1212`）。

## 実行時の動作

通常のモデルロードでは、CUDA の device 数を取得し、指定が空なら全 ID を補います。得られた各 ID は `Dev::id` に保存され、順番に `cudaSetDevice`、stream/event 作成、scratch 準備、空き VRAM 取得を行います（`src/dsv41/ds4_model.cu:1870-1890`）。その後、`devs` の順序を使って device group を構成し、モデル層を配置します（同 `:1912-1944`）。したがって、複数 GPU では ID の順序も配置に影響します。

`--tp` はグループ幅などに別途使われます。`--gpus` 自体が tensor parallel 数を設定するわけではありません（`src/dsv41/ds4_model.cu:1892-1917`）。一方、`--pack-info` の分岐はモデルの GPU load より前に終了するため、そのモードでは `--gpus` の値は GPU 初期化に使われません（`src/dsv41/ds4_main.cpp:1275-1281`）。

## 適用条件と副作用

- GPU device を使うモデル load の経路に適用されます。CUDA device 数を取得できない、または0台の場合は `no CUDA device` で load が失敗します（`src/dsv41/ds4_model.cu:1870-1875`）。
- 指定 ID は範囲検証を通らず `cudaSetDevice` に渡されます。無効 ID など CUDA API が失敗する条件では load が失敗します。指定された device ごとに CUDA stream と event を作成し、カーネル scratch を準備して空き VRAM を照会します（同 `:1880-1890`）。
- `STRATA_BUILD_DSV41` が有効で、かつ `STRATA_HIP_GFX906` ではない場合に `strata-dsv41` 実行 target が定義されます。CMake では GPU backend の構成ブロック内にあります（`CMakeLists.txt:797-811`）。別 backend や Release 配布物での実動作はこの checkout のソース調査だけでは確認していません。

## 出力とエラー

- CUDA device が0台、または device 初期化 API が失敗すると `Model::load` が false を返し、main は `maya-ds4: <理由>` を stderr に出して終了コード 1 で終了します（`src/dsv41/ds4_model.cu:1870-1890`; `src/dsv41/ds4_main.cpp:1289-1294`）。`cudaSetDevice` 等の API エラー理由は `CK` macro が `cudaGetErrorString` で作ります（`src/dsv41/ds4_model.cu:67-74`）。
- 引数値が欠落した場合は parser のエラーとして stderr と終了コード 2 になります（`src/dsv41/ds4_main.cpp:1202-1207`）。

## 根拠

- 索引上の tool-id、root scope、予定リンク: `docs/cli/README.md:1353-1369`。
- parser と整数列解析: `src/dsv41/ds4_main.cpp:71-94,1200-1212`。
- 空リスト時の全 device 選択、device 初期化・後続 group 構築: `src/dsv41/ds4_model.hpp:25-29`; `src/dsv41/ds4_model.cu:1870-1944`。
- 起動時の引数・load エラー経路と `--pack-info` の早期終了: `src/dsv41/ds4_main.cpp:1275-1294`。
- 実行ファイルの build 条件: `CMakeLists.txt:797-811`。
- 文書形式と調査基準: `docs/cli/001_investigation.md:89-114,125-134`。
