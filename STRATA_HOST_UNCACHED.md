# `STRATA_HOST_UNCACHED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリや GPU ドライバー自身の環境変数動作は対象外。

## 役割

SYCL 実装で、GPU kernel が実行中に poll するホストメモリの割り当て方法を選びます。Level Zero ヘッダーを使ってビルドし、キューの backend が Level Zero の場合、既定では `zeMemAllocHost` に `ZE_HOST_MEM_ALLOC_FLAG_BIAS_UNCACHED` を渡して割り当てます。この経路を無効にすると `sycl::malloc_host` に fallback します。

この helper は Verifier の doorbell/window 用バッファ、session の staging buffer、MTP の mapped buffer などから呼ばれます。値が allocator を選ぶだけで、CUDA/HIP 実装にはこの環境変数の読み取り箇所はありません。

## 値と判定

`sycl_queue.hpp` の `host_malloc_polled()` 内で `getenv()` の結果を調べ、先頭文字が `0` かどうかだけで判定します。文字列全体の parse、空白除去、大文字小文字変換はありません。

| 値 | Level Zero allocator の選択 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効（設定済みだが先頭文字は `\0`） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| その他（例: `1`, `true`, `false`, `abc`） | 有効 |

## 有効になる条件

- SYCL の `host_malloc_polled()` が呼ばれること。
- `sycl_queue.hpp` のコンパイル時に Level Zero の `ze_api.h` と oneAPI Level Zero backend header の両方が利用可能であること（`STRATA_HAVE_ZE`）。どちらかがないビルドではこの環境変数を読まず、`sycl::malloc_host` を使います。
- 実行時キューの backend が `sycl::backend::ext_oneapi_level_zero` であること。別 backend では `sycl::malloc_host` を使います。

Level Zero allocator が失敗するか null を返す場合も、処理は `sycl::malloc_host` に fallback します。したがって、この変数が有効でも常に `zeMemAllocHost` が成功するとは限りません。

## 実行時の詳細

判定値は `host_malloc_polled()` 内の function-local `static const bool` に保存され、初回評価後はプロセス内で再評価されません。実行中に環境を変更しても、その後の割り当てには反映されません。

Level Zero allocator が成功したポインタは `uncached_set` に登録されます。対応する `host_free_polled()` は登録済みポインタを `zeMemFree` で解放し、それ以外のポインタは `sycl::free` に渡します。割り当てエラー時のログや、この変数専用のログ出力は実装にありません。

Verifier には別の制御 `STRATA_VERIFY_STEPPED` / `STRATA_VERIFY_HOST_UNCACHED` があります。stepped mode では、`STRATA_VERIFY_HOST_UNCACHED` が有効でない限り Verifier の window バッファは通常の `sycl::malloc_host` を直接使い、`STRATA_HOST_UNCACHED` の allocator 判定を通りません。`STRATA_VERIFY_HOST_UNCACHED` を有効にすると `host_malloc_polled()` を呼びますが、そこで `STRATA_HOST_UNCACHED=0` なら Level Zero allocator は使われず `sycl::malloc_host` に fallback します（`verify.cpp:224-239`）。session staging と MTP buffer の呼び出しは `host_malloc_polled()` を直接使うため、上記の Level Zero 条件下でこの変数が適用されます。

## 根拠

- `sycl/include/strata/sycl_queue.hpp:42-47,63-90`: 用途の説明、値判定、Level Zero 条件付き割り当て、fallback、解放方法。
- `sycl/src/core/verify.cpp:92-103,218-241,1687-1693`: verifier の環境変数判定、stepped mode の別条件、window buffer の allocator 選択。
- `sycl/src/core/session.cpp:750-772,813-814`: session staging buffer の割り当てと解放。
- `sycl/src/core/mtp.cpp:84-95,179`: MTP mapped buffer の割り当てと解放。
- `sycl/CMakeLists.txt:194-203`: Level Zero loader のリンク設定。ヘッダーの有無によるコンパイル時条件は `sycl_queue.hpp:48-53`。

`docs/DETAILS.md` と関連設計資料には、この環境変数の利用者向け説明や測定値は見つかりませんでした。ヘッダー中のコメントは背景説明として扱い、動作の根拠は上記の allocator 分岐に置いています。
