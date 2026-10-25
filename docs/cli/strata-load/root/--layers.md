# `strata-load --layers`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load`（トップレベル） |
| オプション | `--layers` |
| 別名 | なし |
| 値 | 10 進整数として読む層数。省略時は `2` |

## 役割

expert arena のロード計測で、入力ファイルの先頭から何層分を読み込むかを指定します。モデルの層を名前や番号で選ぶ指定ではありません。実装は1層を `512 × 1,382,400` バイトとして扱い、その固定長の連続領域を読みます（`src/core/load_main.cpp:16-20,47-50,66-67`）。

## 使い方

```sh
strata-load --file experts.bin --layers 1
```

`experts.bin` の先頭から1層分（707,788,800 バイト）を arena に読みます。`--file` は必須です（`src/core/load_main.cpp:30-31,45-50`）。

## 値と既定値

- 省略時は `2` です（`src/core/load_main.cpp:16`）。
- 値は `std::strtoull(value, nullptr, 10)` で変換されます。終端文字や変換エラーを確認する処理、正の値かどうかの明示的な検証はありません（`src/core/load_main.cpp:26-32`）。したがって、整数として不正な文字列や範囲外の値に対する利用者向けの安定したエラー仕様は定義されていません。
- 数値に応じてロードサイズは `layers × 512 × 1,382,400` バイトになります（`src/core/load_main.cpp:19-20,47`）。乗算オーバーフローの検査もありません（同 `:47`）。

## 実行時の動作

算出したバイト数で pinned arena を作るか、`--no-pin` が併用されていれば同サイズの領域を `malloc` で確保します。その後 `load_experts` に層数を渡し、各層の入力 offset を `層番号 × 512 × 1,382,400` として先頭から順に読み込みます（`src/core/load_main.cpp:47-67`、`src/core/pinned.cu:681-685`）。

読み込みは層ごとにファイルを seek し、チャンク単位で全バイトをコピーします。ロード後は各層の FNV-1a 64 checksum を出力します（`src/core/pinned.cu:856-926`、`src/core/load_main.cpp:76-82`）。`--stream` も指定した場合は確保した領域を使った host-to-device 転送計測が追加されるため、`--layers` はその計測対象サイズにも影響します（`src/core/load_main.cpp:83-99`）。

## 適用条件と副作用

- この指定が適用されるのは `strata-load` の expert arena ロードです。CMake では実行ファイルを生成し、`pack/full/experts.bin` がある場合は `--layers 1` のロードテストを登録します（`CMakeLists.txt:353-354,365-373`）。
- 既定では pinned arena を確保します。確保サイズは `--layers` に比例し、メモリ確保や CUDA host registration 等を伴います（`src/core/load_main.cpp:52-64`、`src/core/pinned.cu:408-418,436-449`）。`--no-pin` 併用時は通常の `malloc` となりますが、読み込むバイト数は変わりません（`src/core/load_main.cpp:52-67`）。
- ソースには `--layers` の下限・上限 validation がありません。ゼロや極端に大きい値の実行結果は、算出サイズと確保・ロード処理に依存し、正常な計測になる保証は確認できません（`src/core/load_main.cpp:16,31,47-67`）。

## 出力とエラー

- 起動時に層数、blob 数、blob サイズ、総 GiB を標準出力に表示します（`src/core/load_main.cpp:47-50`）。成功時はロード量、時間、checksum、全体サイズへの速度投影を表示します（同 `:73-82,116-120`）。
- `--file` を省略すると標準エラーに `--file is required` を出して終了コード `2`、オプションに値がない場合は `<option> needs a value` を出して終了コード `2` です（`src/core/load_main.cpp:26-28,45`）。
- ファイルを開けない、seek に失敗する、要求バイト数より短く読み込む場合はロードを失敗として返します。短い読み込みをゼロ埋めせず、層番号・読み込み量・offset を記録します（`src/core/pinned.cu:865-870,887-906`）。呼び出し元はエラーを標準エラーへ出し終了コード `1` を返します（`src/core/load_main.cpp:66-71`）。
- arena または `malloc` の確保失敗は標準エラーへ出して終了コード `1` です（`src/core/load_main.cpp:54-64`）。

## 根拠

- `src/core/load_main.cpp:14-45` — parser、既定値、数値変換、必須引数、usage と未知引数の処理。
- `src/core/load_main.cpp:47-71` — 層数からの必要サイズ計算、arena 確保、ロード呼び出しと失敗処理。
- `src/core/load_main.cpp:73-120` — 成功時の計測・checksum・任意の stream 計測と投影出力。
- `src/core/pinned.cu:681-685` — 層ごとのファイル offset とバイト数の構成。
- `src/core/pinned.cu:856-926,937-948` — チャンク読み込み、短い読み込みの失敗、checksum と統計。
- `src/core/pinned.cu:408-418,436-449` — pinned arena の確保・登録処理。
- `CMakeLists.txt:353-354,365-373` — 実行ファイル定義と、入力 artifact が存在するときのロードテスト登録。
