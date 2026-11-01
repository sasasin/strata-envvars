# `STRATA_GPU_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや Metal driver の環境変数動作は対象外。

## 役割

DeepSeek 用 Metal runtime（`strata_ds4`）が compute encoder の open / close、command buffer の signal、Metal buffer 間の blit copy を stderr に記録する診断フラグです。GPU 処理を有効化・無効化したり、コピーや同期の選択を変えたりする設定ではありません。確認できた Strata 内の参照は `metal/src/gpu/runtime.cpp` の4箇所だけで、すべてログ出力の直前に `std::getenv("STRATA_GPU_TRACE")` を確認します。

## 値と判定

値を数値や文字列として parse せず、`getenv` が null pointer を返すかどうかだけで判定します。

| 環境変数の状態 | 判定 | 動作 |
|---|---|---|
| 未設定 | 無効 | trace 行を出さない |
| 設定あり（空文字を含む） | 有効 | 該当イベントの trace 行を出す |
| `0`、`false`、その他の文字列 | 有効 | 文字列の内容に関係なく trace 行を出す |

この変数に無効値の parse、境界値、fallback はありません。CLI 引数や他の環境変数による上書きも実装にありません。

## 有効になる条件

- macOS 向け `metal/` ビルドが対象です。CMake は Apple 以外では構成を停止し、Metal C++ headers がなければ device runtime と engine をビルドせずに終了します（`metal/CMakeLists.txt:16-18,51-55`）。
- 4箇所の読み取りとログはすべて `#if defined(STRATA_DS4_RUNTIME)` の中にあります。この macro を付けて `runtime.cpp` を別途コンパイルするのは `strata_ds4` 用の `ds4_rt_gpu` target です（`metal/CMakeLists.txt:152-165`）。通常の `strata` が使う `strata_gpu_metal` では macro が定義されず、この変数は参照されません（同:57-62,129-130）。
- Metal engine 自体が有効である必要があります。`STRATA_METAL_ENGINE=OFF` なら CMake は engine target の定義前に return します（`metal/CMakeLists.txt:73-77`）。
- ソース上に CLI、モデル状態、別 backend による追加条件はありません。ログは runtime の該当イベントが発生した場合にだけ出ます。

## 実行時の詳細

判定結果は static 変数に保存されず、各ログ箇所で `std::getenv` を呼び直します。したがって runtime は設定を cache しません。C++ プロセス内で環境値が変更された場合は、その後のログ判定に反映されます。単に親 shell の環境を変更しても、既に起動済みのプロセスの環境が変わる処理は Strata 内にありません。

設定時に出るログは次のとおりです（いずれも stderr）。

- encoder が存在して `end_encoder()` が呼ばれると `[gpu] close compute enc %p`（`metal/src/gpu/runtime.cpp:206-212`）。
- compute encoder が新規作成されると `[gpu] open compute enc %p (cb %p` と両 encoder / command buffer のポインタ値（同:214-224）。
- `flush()` に command buffer があり commit する場合、signal の符号化前に `[gpu] signal %llu on cb %p (enc %p)`。表示する連番は `submitted + 1`（同:226-240）。
- 両端が Metal device allocation で buffer-to-buffer blit になる場合、コピー符号化前に `[gpu] blit copy %zu` と byte 数（同:271-292）。host memory を含む copy はこの blit ログ箇所を通りません。

これらの出力は処理状況を観測するものです。環境変数による追加の終了、警告、GPU API 呼び出しの変更は確認できません。

## 根拠

- `metal/src/gpu/runtime.cpp:206-224,226-240,271-292` — 4つの直接読み取り、設定有無判定、ログ位置とイベント条件。
- `metal/CMakeLists.txt:16-18,51-77,129-130,152-165` — macOS / headers / engine 条件、通常の Metal target と `STRATA_DS4_RUNTIME` 付き `strata_ds4` runtime の区別。
- `docs/MAC.md:268-274` — Metal runtime の配置と役割の概要。環境変数の値判定や挙動の根拠は上記ソースコード。
