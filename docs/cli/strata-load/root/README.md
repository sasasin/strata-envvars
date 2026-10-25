# `strata-load`（expert arena load）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load`（サブコマンドなし） |
| 主な実装 | `src/core/load_main.cpp`、`src/core/pinned.cu` |
| ビルド条件 | CMake の `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効 |

## 役割

expert arena 用のバイナリファイルから指定した層数分をホストメモリへ読み込み、層ごとの FNV-1a 64 checksum と読み込み速度を表示する開発・測定用 CLI です。既定ではメモリ領域を GPU driver に登録する pinned arena として確保します。任意の `--stream` を付けると、その領域から GPU への転送速度も複数の転送サイズで測ります。Terminal CLI のユーザー向け `strata` コマンドや、推論エンジン本体の `strata` とは別の実行ファイルです。

## 基本的な使い方

ビルド済み `strata-load` と `pack/full/experts.bin` がある環境で、先頭の1層を通常メモリに読み込んで checksum を確認する例です。

```sh
./build/strata-load --file pack/full/experts.bin --layers 1 --no-pin
```

既定の2層を pinned arena に読み込み、ホストから GPU への転送測定も行う例です。

```sh
./build/strata-load --file pack/full/experts.bin --stream
```

CMake は `strata-load` を GPU backend 有効時に定義します。`pack/full/experts.bin` が configure 時に存在する場合は、`--layers 1` で実行する `expert_arena_load` CTest も登録します。この文書では CLI やテストを実行していません。

## 実行モード

- **arena load（既定）**: 指定層分を入力ファイルから並列読み込み、コピー時に各層の checksum を計算し、読み込み量・所要時間・スレッド数・chunk サイズ・速度を表示します。
- **非 pinned load（`--no-pin`）**: pinned arena の代わりに `malloc` で領域を確保して同じ load を行います。
- **GPU stream 測定（`--stream`）**: load 成功後、1 blob、16 blobs、1層、全 arena の granularity で host-to-device 転送を測り、設計上の expert miss 率を仮定した token あたりの転送量・速度の試算も表示します。転送先 GPU buffer は再利用されます。
- **help**: `--help` または `-h` は usage を stdout に表示して終了します。

`--file` は必須です。既定の読み込み量は2層、8 reader threads、16 MiB chunks で、1層は512 blobs、1 blob は1,382,400 bytes として計算されます。従って既定の arena は約1.32 GiBです。`--layers` の指定を増やすと確保量も比例して増えます。ファイルの書き換えや削除は行いませんが、読み込み対象と同量のホストメモリを確保し、既定ではその一部または全体を pin / resident にする処理が発生します。

## 主な動作と注意点

- `--layers` で計算する範囲はファイル先頭からの連続領域です。実際の読み込みは layer ごとに seek し、chunk 単位で読み込み・コピー・checksum 計算をします。短い読み込みはゼロ埋めせず失敗として扱います。
- デフォルトの pinned arena で全領域を GPU driver に登録できない場合、arena の backing 状態や登録結果を `backing:` 行に表示します。確保自体が失敗すれば終了コード1です。`--no-pin` は `malloc` のみを使い、確保失敗時は `malloc failed` を stderr に出して終了コード1です。
- `--stream` は GPU buffer と stream を作って転送します。`--no-pin` との組み合わせを拒否する parser validation は見当たりませんが、この組み合わせで pinned host memory の転送性能を測れるとは限りません。
- `--stream` は parser で認識される一方、同じソース内の `--help` usage には記載されていません。ソース上の受理仕様と表示される help にこの差があります。
- 数値引数には専用の範囲 validation がありません。`--layers` と `--chunk-mb` は `strtoull`、`--threads` は `atoi` で変換し、`--threads` が1未満なら読み込み側で1に補正されます。特に0の chunk や極端な値は通常利用例として使わないでください。
- 引数の値不足・未知の引数・`--file` 欠落は stderr に理由を出して終了コード2です。open / seek / short read などの load 失敗は終了コード1です。成功時は checksum と全入力に基づく速度を出し、指定範囲が34 GB全体でない場合も既定の全体サイズに対する投影時間を続けて表示します。投影値は実測した全体 load 時間ではありません。
- `--stream` 時に CUDA buffer の確保に失敗した場合、その granularity の測定は stderr に警告を出してスキップします。測定に対応する GPU・backend の実行環境は、この checkout 上で実機確認していません。

## 関連文書

- [CLI オプション索引](../../README.md) — `strata-load` のオプション文書リンク一覧
- [CLI 調査基準](../../001_investigation.md)
- [Strata CLI と配布形態](../../000_cli_tools.md)

## 根拠

- Strata `src/core/load_main.cpp:14-45` — 引数 parser、既定値、help、必須入力と未知引数の扱い。
- Strata `src/core/load_main.cpp:47-81` — arena サイズ、確保方式、load 呼び出し、失敗表示、結果と checksum の出力。
- Strata `src/core/load_main.cpp:83-120` — `--stream` の転送 granularity、反復測定、token あたり試算、全体サイズの投影。
- Strata `src/core/pinned.cu:408-523` — pinned arena の確保、GPU 登録・fallback・resident lock の処理。
- Strata `src/core/pinned.cu:681-686,832-949` — load 範囲の構成、threads の補正、chunk 読み込み、checksum、open / seek / short read の失敗経路。
- Strata `src/core/pinned.cu:951-980` — stream 測定の GPU buffer 確保と host-to-device copy。
- Strata `CMakeLists.txt:333-354` — CUDA/HIP 有効時の `strata-load` target 定義。
- Strata `CMakeLists.txt:365-373` — `pack/full/experts.bin` が存在するときだけ load CTest を登録する条件。
