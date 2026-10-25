# `--chunk-mb`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load`（トップレベル） |
| オプション | `--chunk-mb` |
| 別名 | なし |
| 値 | 10進整数として読み取る MiB 数。既定値は 16 MiB |

## 役割

expert arena のファイル読込で、各 reader thread が一度に読む最大バイト数を指定します。入力値を MiB 単位として `load_experts` に渡し、読み込みバッファの大きさと各 `fread` の要求量に使います（`src/core/load_main.cpp:18,33,66-67`; `src/core/pinned.cu:681-685,856-857,893-897`）。これは `strata-load` の測定・検証用 CLI の設定で、実行時の推論エンジン一般の chunk 設定ではありません。

## 使い方

```sh
strata-load --file experts.bin --chunk-mb 32
```

`experts.bin` は対象の expert arena ファイルです。`strata-load` はこのほかに `--layers`、`--threads`、`--no-pin` を受け付けます（`src/core/load_main.cpp:30-35,37-38`）。

## 値と既定値

- 省略時は `16ull << 20`、すなわち 16 MiB（16,777,216 bytes）です（`src/core/load_main.cpp:18`）。
- 値は `std::strtoull(value, nullptr, 10) << 20` で変換されます。専用の範囲検査、末尾文字検査、エラー検査はありません。したがって数値の後ろに文字がある値は数値部分が使われ、数字として変換できない値は 0 になり、負数や巨大値は unsigned 変換・左シフトの結果で扱われます（`src/core/load_main.cpp:33`）。
- `--chunk-mb` の直後に引数がなければ `--chunk-mb needs a value` を stderr に出し、終了コード 2 で終了します（`src/core/load_main.cpp:26-28,33`）。
- 0 を拒否する validation はありません。通常の `layers > 0` で 0 が渡ると、loader は `n = min(remaining, chunk)` を 0 とし、`remaining` を減らさないまま読み込みループを続けるため、処理が進まなくなります（`src/core/pinned.cu:893-925`）。0 は指定しないでください。

## 実行時の動作

parser は MiB 数を bytes に変換し、固定の expert arena 全体を読む `load_experts(path, ..., layers, threads, chunk)` に渡します（`src/core/load_main.cpp:16-20,33,47-50,66-67`; `src/core/pinned.cu:681-685`）。各 reader thread は `std::vector<uint8_t>` を chunk byte 数で確保し、各 layer の残量に達するまで `min(remaining, chunk)` bytes を `fread` して arena へコピーします。最後の読込単位だけは layer の残量に合わせて小さくなります（`src/core/pinned.cu:856-857,893-925`）。

reader 数は `--threads` の値ですが、loader は 1 未満を 1 に補正します。reader ごとに chunk サイズのバッファを確保するため、chunk を大きくすると reader 数に応じて一時メモリ使用量も増えます（`src/core/load_main.cpp:17,32,66-67`; `src/core/pinned.cu:846-857,932-935`）。このオプションは `--stream` の転送測定粒度を変更しません。stream sweep は blob・16 blob・layer・arena の固定粒度を使います（`src/core/load_main.cpp:83-94`）。

## 適用条件と副作用

`strata-load` の expert file 読み込み経路に適用されます。pinned arena の確保・登録または `--no-pin` の malloc 選択は `--chunk-mb` と別の処理です（`src/core/load_main.cpp:52-67`）。成功時には指定 chunk を MiB 表記で読み込み結果行に表示します（`src/core/load_main.cpp:73-75`）。chunk サイズ自体によるファイル書き込みや入力ファイルの変更は、この経路では確認できません。

大きすぎる値や unsigned 変換後の値は parser で拒否されません。実際に確保する `std::vector` のサイズは `(size_t) chunk` となるため、確保不能時の具体的な診断・終了コードはソースから保証できません（`src/core/pinned.cu:856-857`）。この調査では実行・境界値測定はしていません。

## 出力とエラー

- 読み込みに成功すると、処理 bytes、経過時間、thread 数、chunk MiB 数、スループットを stdout に表示します（`src/core/load_main.cpp:73-75`）。
- ファイル open、seek、short read の失敗は loader が詳細を stderr に出し、`LoadStats.ok` を false にします。呼び出し側は `loading the experts failed: ...` を stderr に出して終了コード 1 を返します（`src/core/pinned.cu:865-870,887-906,937-943`; `src/core/load_main.cpp:68-70`）。
- 未知の引数は `unknown argument: ...` を stderr に出して終了コード 2、必須の `--file` がない場合は `--file is required` を stderr に出して終了コード 2 です（`src/core/load_main.cpp:40-46`）。

## 根拠

- `src/core/load_main.cpp:14-45` — parser、既定値、値変換、欠落値・未知引数・usage の処理。
- `src/core/load_main.cpp:47-75,83-94` — arena サイズと reader 呼び出し、成功時の表示、`--stream` の固定粒度。
- `src/core/pinned.cu:681-685,846-857,893-948` — chunk 値の引き渡し、thread ごとの buffer、読み込みループ、I/O 失敗処理。
- `include/strata/core/pinned.hpp:126-138` — `load_experts` の用途と chunk 読み込み契約。
- `CMakeLists.txt:350-354` — `strata-load` の build target とリンク先。
