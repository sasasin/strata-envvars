# `--ssd-cache`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（トップレベル） |
| オプション | `--ssd-cache` |
| 別名 | なし |
| 値 | GB 単位の数値。小数を受け付ける実装だが、数値形式・範囲の明示的な検証はない |

## 役割

VRAM に載らない DeepSeek-V4.1 の routed expert を保持する、追加の RAM store の上限を指定します。名前に `ssd` とありますが、値はディスク容量ではなく RAM 上のキャッシュ予算です。store はモデル pack の expert を要求時や先読み時に読み込み、LRU/LFU の置換対象となる slot に保持します（`src/dsv41/ds4_model.hpp:37-40`、`src/dsv41/ds4_store.hpp:1-15`）。

この CLI は `STRATA_BUILD_DSV41=ON` で生成される独立実行ファイル `strata-dsv41` 用で、CMake option は既定で OFF です（`CMakeLists.txt:797-811`）。索引上の tool ID は [`docs/cli/README.md`](../../../README.md) の `strata-engine-dsv41` 節を参照してください。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ssd-cache 16 --serve
```

`--ssd-cache` は `--pack` や `--serve` と同じトップレベル parser で解釈されます。`--pack` は必須で、通常は `--serve`、または推論用の `--ids` などと併用します（`src/dsv41/ds4_main.cpp:87-93,1200-1217,1263-1285`）。

## 値と既定値

- 省略時の内部値は `-1.0` です。負数は自動設定、`0` は無効化、正数は指定した GB 数を予算として扱います（`src/dsv41/ds4_model.hpp:37-40`、`src/dsv41/ds4_model.cu:4457-4468`）。
- 自動設定では、取得可能な空き RAM から 12 GB を差し引き、残りが 4 GB 以上なら最大 48 GB を予算にします。4 GB 未満、または空き RAM を取得できない場合は 0 GB になります（`src/dsv41/ds4_model.cu:4463-4467`）。
- 明示値は `std::atof` で読みます。parser に数値変換エラー、有限値、上下限の検査はなく、数値に変換できない文字列は `atof` の結果 0 として扱われます。値を省略すると `--ssd-cache needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207,1217`）。
- GB から byte への予算換算は `1e9` 倍です。slot のサイズに満たない予算では store 初期化に失敗します（`src/dsv41/ds4_model.cu:4487-4488`、`src/dsv41/ds4_store.hpp:78-82`）。

## 実行時の動作

モデル読み込み時に `DS4_STORE_GB` が設定されていれば、CLI 値より優先して store 予算に使います。環境変数の値も `std::atof` で読みます。解決した値は初回に決まり、モデル実行中はキャッシュされます（`src/dsv41/ds4_model.cu:4457-4468`）。

store は予算全体を最初から RAM に確保するのではなく、最大 slot 数を予算から計算し、必要に応じて chunk 単位で確保します。確保時には現在の空き RAM が chunk 分と `floor_bytes` を下回ると拡張を止めます。`floor_bytes` の既定値は 8 GiB で `DS4_STORE_FLOOR_GB` から変更できます（`src/dsv41/ds4_model.cu:4487-4490`、`src/dsv41/ds4_store.hpp:58-70,465-470`）。実行中、空き RAM が 4 GiB を下回る状態を監視して store chunk を解放する処理もあります（`src/dsv41/ds4_model.cu:5955-5965`）。

CPU lane の expert が RAM store にあればその slot を読み、なければ既存の RAM copy または pack ファイル上の expert を使います（`src/dsv41/ds4_model.cu:1689-1697`）。GPU から store を直接参照する経路は `DS4_STORE_ZC` などの追加条件を満たす場合に限られ、`--ssd-cache` 単独で有効化されるわけではありません（`src/dsv41/ds4_model.cu:4495-4519,4592-4617`）。

## 適用条件と副作用

実際に store を初期化するのは、解決後の予算が正で、layer が存在し、先頭 layer の形式が MXFP4 で、かつ expert をファイルから読む構成の場合です（`src/dsv41/ds4_model.cu:4470-4473`）。このコードでは GGUF pack は `file_experts` を有効にし、GGUF 以外では store 予算を 0 にします（`src/dsv41/ds4_model.cu:1948-1953,4460-4463`）。したがって、指定値が正でも条件外なら store は作られません。

指定予算は上限です。空き RAM が不足すれば chunk が増えず、利用可能 slot 数は指定値より小さくなります。キャッシュデータの保持先はプロセスメモリであり、option の処理として専用 SSD ファイルを作成する箇所は確認できません（`src/dsv41/ds4_store.hpp:1-12,465-470`）。置換方式は別 option `--ssd-policy` が選びます（`src/dsv41/ds4_main.cpp:1218-1221`、`src/dsv41/ds4_model.cu:4487-4492`）。

## 出力とエラー

store 初期化に失敗すると stderr に `ds4: --ssd-cache: the store could not start` を出し、store の設定だけを中止します。呼び出し元の `init_store()` は戻った後もモデル読み込みを続けます（`src/dsv41/ds4_model.cu:2775-2780,4524-4529`）。初期化に成功すると stderr に最大 slot 数、slot 容量、予算換算後の容量、policy、reader thread 数、読み込み方式を表示します（`src/dsv41/ds4_model.cu:4535-4537`）。推論後、store が動作していた場合は hit/miss、読み込み量、待ち時間、eviction、failed read などの統計を stderr に出します（`src/dsv41/ds4_main.cpp:1461-1473`）。

## 調査範囲

調査対象は上記 commit の parser、モデル実装、store 実装、および CMake target 定義です。同一 revision のビルド済みバイナリや Release artifact は確認しておらず、実行時 `--help` の出力照合、各 OS/backend での実動作、数値境界の実行検証は行っていません。ここでの値の説明はソースから確認できる範囲です。

## 根拠

- `src/dsv41/ds4_main.cpp:87-93,1200-1207,1217-1221,1263-1285` — usage、値の読み取り、関連 mode、必須引数と失敗経路。
- `src/dsv41/ds4_model.hpp:37-40` — option の役割と既定値。
- `src/dsv41/ds4_model.cu:1948-1953,4457-4468,4470-4494,4524-4537` — 対象条件、環境変数優先、自動予算、store 作成・失敗・初期化ログ。
- `src/dsv41/ds4_store.hpp:1-15,58-82,142-193,398-470` — RAM store の読み書き・slot 予算・空き RAM 制限。
- `src/dsv41/ds4_model.cu:1689-1697,2775-2780,5955-5965` — store miss 時の expert 参照先、モデル読み込みへの影響、実行中の縮小。
- `src/dsv41/ds4_main.cpp:1461-1473` — 推論後の store 統計出力。
- `CMakeLists.txt:797-811` — DSV41 engine target と既定 OFF の build option。
