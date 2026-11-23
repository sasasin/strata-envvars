# `STRATA_TEST_MAX_ALLOC_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL のテスト用ビルドで、Strata の `malloc_device_guarded` を通る単一 GPU device allocation の上限を MiB 単位で設定する fault-injection 用フック。要求サイズが上限を超えると `sycl::malloc_device` を呼ばず null を返す。通常の release build では `STRATA_SYCL_TEST_HOOKS` が定義されないため、この環境変数は読み取られず、実デバイスの `max_mem_alloc_size` が使われる。対象は helper 経由の割り当てだけで、SYCL の全 device allocation を一律に制限するものではない（`engine/sycl/include/strata/sycl_queue.hpp:298-327`、`engine/sycl/CMakeLists.txt:65-68`）。

## 値と判定

| ビルド・環境変数 | 判定と上限 |
|---|---|
| `STRATA_SYCL_TEST_HOOKS` 無効（CMake 既定） | 変数を参照せず、デバイスの `max_mem_alloc_size` を問い合わせる。問い合わせ例外時は上限 0。 |
| `STRATA_SYCL_TEST_HOOKS` 有効、未設定 | デバイスの `max_mem_alloc_size` を問い合わせる。問い合わせ例外時は上限 0。 |
| `STRATA_SYCL_TEST_HOOKS` 有効、設定あり | `std::strtoull(value, nullptr, 10)` の結果を `uint64_t` にし、20 bit 左シフトした値を上限とする。要求サイズが上限を**超える**と拒否し、上限と等しいサイズはこのフックでは拒否しない。 |

`strtoull` の戻り値や `errno` は検査せず、終端位置も受け取らない。このため数値の後ろの文字は無視され、先頭の空白や符号を含む入力も変換関数の規則で処理される。数字に変換できない空文字・`abc` は 0 となり、`0` も上限 0 になる。いずれも「変数が設定されている」状態ではあるものの、上限 0 は拒否条件の `max_alloc` を偽にするため、割り当てを遮断しない。負値や範囲外の入力も明示的に無効扱いせず、`strtoull` の unsigned 変換結果を左シフトした値が使われる。従って、入力全体の妥当性検査や範囲 clamp はない（`engine/sycl/include/strata/sycl_queue.hpp:304-312,315-327`）。

例としてテスト用ビルドで `1` は 1 MiB、`12MiB` は先頭の `12` を使って 12 MiB の上限になる。`1anything` も 1 MiB になる。`0`、空文字、`abc` は上限 0 となり、helper 側の拒否は無効になる。大文字小文字は数値変換に関係しない。

## 有効になる条件

- `engine/sycl` のビルドで CMake オプション `STRATA_SYCL_TEST_HOOKS=ON` が有効であること。オプションは既定で `OFF` で、ソースコメントも release build では有効にしない test-only hook としている（`engine/sycl/CMakeLists.txt:65-68`）。
- 対象の device allocation が `strata::malloc_device_guarded` を通ること。例えば重み arena、expert cache、MTP allocation などで使われる。直接 `sycl::malloc_device` を呼ぶ他の箇所にはこの上限判定は適用されない（`engine/sycl/src/program/generate.cpp:3142-3145`、`engine/sycl/src/core/expert_cache.cpp:697-700`、`engine/sycl/src/core/mtp.cpp:257-259`）。
- `STRATA_ARENA_ALIAS_CHECK`、CLI、サーバーモード、モデル状態はこの上限値の算出条件ではない。helper が null を返した後のエラー処理は呼び出し元ごとに異なる。例えば MTP Q4 projection は `mtp: the Q4_0 projections do not fit` をエラーにして `false` を返し、重み arena の失敗では上限を超えている場合に専用 stderr 文言を出して `1` を返す（`engine/sycl/src/core/mtp.cpp:257-259`、`engine/sycl/src/program/generate.cpp:3145-3154`）。

## 実行時の詳細

環境変数名を直接参照する箇所は `engine/sycl/include/strata/sycl_queue.hpp` の `device_max_alloc` と `malloc_device_guarded` のみ。前者は各 helper 呼び出しで値を取得し、後者も test-hook build では設定有無を別途 `getenv` で判定する。static cache はなく、次の割り当て時に再評価される。値を読むのは SYCL queue 上で helper が呼ばれた時点であり、起動時一括読み込みではない（同ファイル `:304-321`）。

test-hook build で設定値が非ゼロ上限となり、要求 byte 数がその上限より大きい場合、helper は `sycl::malloc_device` を呼ばず null のまま進む。上限が 0 または値が未設定なら実デバイスの割り当て上限を使う（未設定時）か、上限判定なしで `sycl::malloc_device` を試す（設定値を 0 に変換できた時）。実デバイス上限の問い合わせが例外になった場合も上限 0 で割り当てを試みる。null かつ非ゼロ上限超過なら helper は stderr に次の診断を出す:

```text
strata: the %s needs one %.2f GiB GPU allocation, and this GPU allows at most %.2f GiB in one allocation (max_mem_alloc_size)
```

（`engine/sycl/include/strata/sycl_queue.hpp:315-327`）。呼び出し元で失敗は伝播・報告されるが挙動は一様でない。重み arena では非ゼロ上限超過時に `strata generate: this model's GPU weights ...` と出して終了コード 1、上限が 0 の時やそれ以外の allocation failure は別の空き VRAM 診断経路に進む（`engine/sycl/src/program/generate.cpp:3142-3154,3171-3180`）。`DPCT_CHECK_ERROR` が例外を捕捉した場合は例外文字列を stderr に出してエラー値を返す（`engine/sycl/include/dpct/dpct.hpp:90-99`）。

## ログと測定値

測定値の記載はない。上記の拒否診断は実装上の文字列で、要求元の `what`、要求 GiB、上限 GiB を埋め込む。エラー終了や上位の診断は allocation の呼び出し元に依存する（`engine/sycl/include/strata/sycl_queue.hpp:322-327`、`engine/sycl/src/program/generate.cpp:3145-3154`）。

## 根拠

- 値の取得、上限判定、null 時の診断: `engine/sycl/include/strata/sycl_queue.hpp:304-327`
- test hook の build 条件と既定値: `engine/sycl/CMakeLists.txt:65-68`
- helper の主要な呼び出しと失敗処理: `engine/sycl/src/program/generate.cpp:3142-3154`、`engine/sycl/src/core/expert_cache.cpp:697-718`、`engine/sycl/src/core/mtp.cpp:257-259`
- `DPCT_CHECK_ERROR` の例外処理: `engine/sycl/include/dpct/dpct.hpp:90-99`
