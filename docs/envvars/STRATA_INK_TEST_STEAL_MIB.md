# `STRATA_INK_TEST_STEAL_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 Inkling バックエンドの初期化中、モデルの expert を GPU に配置した後に指定量の GPU メモリを追加確保し、後続の runner 初期化に使える空き容量を意図的に減らすテストフックです。コメント上の目的は、配置計画で残り容量が少なかった場合を模擬することです。生成内容や expert の配置を直接変更する設定ではなく、後続ワークスペースの容量選択や確保成否に間接的に影響します。`InkCudaBackend::init` の CUDA 固有コードで読み取ります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:227-231,271-282`）。

## 値と判定

`std::getenv` で設定有無を判定し、設定されていれば `std::atoll` で整数に変換します。変換値が正の場合だけ MiB 単位の `cudaMalloc` を試みます。文字列全体の妥当性検査、範囲制限、エラー時の fallback 値はありません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:277-281`）。

| 条件 | 未設定 | 確保を試みる値 | 確保しない値 |
|---|---|---|---|
| CUDA Inkling backend の初期化 | 何もしない | 変換後の整数が正（例: `1`, `64`, `+12junk`） | 変換後が0以下（例: 空文字、`0`, `-1`, `true`, `junk`, `0anything`） |

`atoll` の整数変換なので、先頭空白と符号は整数変換規則に従い、数字列の後ろにある文字は値として使われません（`12MiB` は12、`12.5` は12、`0x10` は先頭の0）。大文字小文字は意味を持ちません。空文字は「設定済み」ですが変換結果が0のため確保しません。正の値を `size_t` に変換して `<< 20` したバイト数を要求し、コード上の上限や安全な最大値への丸めはありません。要求が大きすぎる場合の `cudaMalloc` 失敗処理は下記のとおりです（同ファイル `:278-281`）。

## 有効になる条件

- `strata-inkling` が Inkling の CUDA backend をビルドしており、通常の backend 選択で `make_cuda_backend()` が選ばれる必要があります。`INKLING_ENABLE_CUDA` が優先され、その macro がない場合は EP CUDA、HIP、Metal、SYCL の順に選択されます。`force_cpu` が真なら CPU backend です（`engine/src/inkling2/ink_backend.h:198-215`）。CUDA 実装は `strata_inkling_cuda` に含まれます（`engine/src/inkling2/cuda/CMakeLists.txt:56-66`）。
- 選ばれた backend の `init` が成功し、モデルのロードと expert 配置まで到達する必要があります。フックはその直後に実行されます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:227-231,277-282`）。
- 値が正でも、GPU が要求量を確保できなければメモリを保持しません。その失敗を理由としたエラーや専用ログは出しません（同ファイル `:278-281`）。
- CLI 引数によるこのフックの上書きはありません。`--chunk` や `STRATA_INK_CHUNK_AUTO=0` は自動 chunk 選択の抑止に関係しますが、確保済みメモリ自体は解放しません。runner の確保が足りなくなると、`STRATA_INK_OOM_RETRY` の判定に応じて retry または初回失敗になります（同ファイル `:284-300,303-337`）。
- CPU、HIP、Metal、SYCL backend にはこの名前の読み取り箇所がなく、この設定ではそれらの backend のメモリ確保は変わりません（候補名の全参照は CUDA 実装の `:278` とメンバーコメントの `:1217`、設定登録 JSON のみ）。

## 実行時の詳細

`InkCudaBackend::init` のたびに読みます。値を static cache する処理はなく、プロセス起動後に環境を変更できる呼び出し元なら、その後の初期化で新しい値が評価されます。一般的なプロセス環境は起動時に親から渡されます。モデルロード後、空き容量 `led_loaded` を測る直前に確保するため、確保成功時はこの測定値と、それを使う自動 prefill chunk 選択に反映されます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:271-300`）。

確保したポインターは `d_test_steal_` に保持され、backend の `cleanup` で `cudaFree` されます。これにより runner の初期化に残るメモリが少なくなり、自動 chunk は空き容量の条件に従って小さく選ばれます。また、runner の確保が失敗した場合には、通常の初期化経路で chunk を半分ずつ下げて再試行します（最小64でも失敗なら init を失敗させます）。`STRATA_INK_OOM_RETRY=0` はこの再試行を無効にします（同ファイル `:284-337,1174-1180`、`engine/include/strata/core/ink_chunk.hpp:42-49`）。

これは server 専用ではなく、CUDA backend の `init` を呼ぶ CLI 経路に適用されます。通常生成では init 失敗時に `init: <理由>` を stderr に出して終了コード1となり、serve mode では `ERR init: <理由>` を返して終了コード1です（`engine/src/inkling2/ink_main.cpp:1086-1094`）。この変数の `cudaMalloc` 失敗自体は無視されます。成功した場合も専用ログはありませんが、後続の `[InkCUDA] memory: ...` と、workspace 確保に失敗した場合の retry / 最終失敗ログに間接的に現れることがあります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:324-356`）。

## ログと測定値

この環境変数の読み取りや確保成功・失敗を直接示すログはありません。runner の確保失敗時は `[InkCUDA] not enough free GPU memory for the working buffers at chunk ...; retrying with chunk ...`、64でも確保できない場合は `not enough free GPU memory for the working buffers even at the smallest size. Use a smaller --max-context, a lower --vram-experts-gb, or close other programs that use the card.` を init error に含めます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:324-335`）。この変数に結び付けられた測定値は確認できません。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-131,227-231,271-300,303-337,1174-1180,1213-1218`
- `engine/src/inkling2/ink_backend.h:198-215`
- `engine/src/inkling2/cuda/CMakeLists.txt:56-66`
- `engine/src/inkling2/cuda/ink_cuda.cuh:60-80`
- `engine/include/strata/core/ink_chunk.hpp:23-49`
- `engine/src/inkling2/ink_main.cpp:1078-1094`
