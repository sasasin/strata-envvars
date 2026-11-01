# `DS4_TRACE_FREE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

Metal 版 DeepSeek runtime が管理する GPU / host allocation を解放するとき、解放対象のサイズ・host allocation かどうか・ポインターを stderr に出す診断スイッチです。割り当てや解放の選択を変えず、解放を追跡するログだけを追加します。

## 値と判定

| 環境変数の状態 | `free_alloc()` のログ |
|---|---|
| 未設定 | 出さない |
| 空文字を含む、何らかの値が設定済み | 出す |

値は `getenv()` の null 判定だけに使われ、文字列・数値として parse されません。したがって `0`、`false`、任意の文字列も、空文字と同じく設定済みなら有効です。CLI 引数や別の環境変数による上書きはありません。

## 有効になる条件

この参照は `STRATA_DS4_RUNTIME` のコンパイル時分岐内にあります。該当 runtime object を含む `strata_ds4` は Metal 用 CMake プロジェクトで macOS 上にビルドされ、DeepSeek (`DS4`) エンジンと Metal C++ headers の条件を満たす場合に構成されます。通常の CUDA / HIP / SYCL build や同じ Metal runtime の `strata` (Qwen 側) にはこの診断コードは含まれません (`metal/CMakeLists.txt:1-2,50-55,132-165`)。

ログが出るのは runtime が追跡している allocation の先頭ポインターを非 null で解放したときです。null ポインターは成功扱いで早期 return し、追跡対象でないポインターや allocation 内部のアドレスはエラー扱いでログ行より前に return します (`metal/src/gpu/runtime.cpp:393-400`)。

## 実行時の詳細

`free_alloc()` は解放処理のたびに `std::getenv("DS4_TRACE_FREE")` を評価するため、判定結果を static cache しません。プロセス実行中に環境を変更した場合も、次の解放時に再読込されます。設定されていると stderr に次の形式で1行出します。

```text
gpu free <bytes> bytes (host=<0|1>) at <pointer>
```

`bytes` は Strata runtime の allocation 記録上のサイズ、`host` は host allocation なら `1`、それ以外なら `0`、`pointer` は解放対象アドレスです。ログの後に device synchronization、residency set からの除去、buffer release を行います (`metal/src/gpu/runtime.cpp:393-411`)。この経路は `cudaFree` / `cudaFreeHost`、および host unregister から呼ばれます (`metal/include/metal_compat/cuda_runtime.h:143-150`, `metal/src/gpu/runtime.cpp:512-522,541`)。

ログを書いた後に同期・解放で失敗した場合の専用メッセージや、この変数による終了・fallback は実装されていません。無効ポインターの経路は `kErrorInvalidValue` を返しますが、`DS4_TRACE_FREE` の行は出しません。

## 根拠

- `metal/src/gpu/runtime.cpp:393-411` — null / 不正アドレスの早期 return、設定有無の判定、stderr 出力、同期および実解放。
- `metal/src/gpu/runtime.cpp:512-522,541` — device free、host free、host unregister から共通解放関数への経路。
- `metal/include/metal_compat/cuda_runtime.h:143-150` — Metal compatibility layer の CUDA 名 free API の転送先。
- `metal/CMakeLists.txt:1-2,50-55,132-165` — macOS 専用 Metal project、DeepSeek runtime の macro 定義および `strata_ds4` への組み込み。
