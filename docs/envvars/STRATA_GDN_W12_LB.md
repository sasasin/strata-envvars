# `STRATA_GDN_W12_LB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

gfx12（`gfx1200` / `gfx1201`）向け HIP の chunked GDN scan で、チャンク処理の前後に使う barrier の実装を選びます。有効時は LDS アクセスを待ってから workgroup barrier を実行する経路、無効時は `__syncthreads()` を使う経路になります。値はカーネルのテンプレート引数として選ばれます。

この環境変数が選ぶのは scan 内の同期方法です。chunked 経路そのものを有効にする設定ではありません。

## 値と判定

各読み取り箇所は `getenv()` と `std::atoi()` を使い、結果が 0 かどうかで判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（`v == nullptr` で `true`） |
| 空文字 | 無効（`atoi("") == 0`） |
| 10 進整数として 0 になる文字列 | 無効。例: `0`, `-0`, `abc`, `1.5` |
| 10 進整数として非 0 になる文字列 | 有効。例: `1`, `-1`, `2tail`, ` 1` |

全体一致の検証やエラー処理はありません。`atoi` が先頭の空白と符号を許し、数字列の後ろを読み飛ばすため、`2tail` は有効、`1.5` は `1` として有効です。整数変換の範囲外入力に対する明示的な処理もありません。

## 有効になる条件

この名前を読む実装は `src/prefill/kernels.cu` にあり、`#if defined(__HIPCC__)` の範囲にあります。CUDA build はこの変数を読みません。

変数が scan の barrier 選択に使われる経路は次のとおりです。

- **通常の recurrence 経路**: `STRATA_GDN_CHUNKED` が非 0、`STRATA_GDN_REC_HEADS` が未設定で、HIP recurrence の variant が 0 または 1 であることが必要です。そのうえで現在の device が gfx12、token 数 `T >= 64`、`ld16` が 8 の倍数なら WMMA scan が実行され、この変数が参照されます。device 取得失敗、別の GPU 世代、短い `T`、不整列の `ld16` では通常の recurrence に進みます。
- **conv と recurrence の fused 経路**: 通常の出力付き prompt GDN から fused 関数が呼ばれ、`STRATA_GDN_CHUNKED` が非 0、`STRATA_GDN_FUSE` が未設定または `atoi` で非 0であることが必要です。さらに `T >= 64`、`ld16` が 8 の倍数、gfx12 であればこの変数が参照されます。条件を満たさない場合、呼び出し元は通常の conv と recurrence に fallback します。

gfx12 の判定は `gcnArchName` が `gfx1200` または `gfx1201`（後ろに `:...` が付く形式を含む）であることを確認します。カーネル本体の WMMA intrinsic も `__gfx1200__` / `__gfx1201__` の build pass に限られます。HIP の fused 経路は state-only KVA では呼ばれません。state-only recurrence は通常の recurrence dispatch 条件に従います。

## 実行時の詳細

通常経路では、`gdn_recurrence_impl()` が chunked scan を試し、`gdn_rec_wmma()` が gfx12 と `T >= 64` を確認した後に `STRATA_GDN_W12_LB` を読みます。fused 経路では `gdn_fused_impl()` が chunked / fuse 設定、長さ、device、alignment を確認してから同じ環境変数を読みます。両関数それぞれに関数内 `static const bool` があるため、それぞれの経路で最初にこの判定へ到達した時の値が cache され、同じ関数内では以後再評価されません。二つの経路の cache は別々です。

有効（`lb == true`）なら `gdn_w12_scan_kernel<true, ...>`、無効なら `<false, ...>` を launch します。`src/prefill/gdn_wmma12.inc:27-41` の実装では、true は `s_wait_dscnt 0x0`、`__builtin_amdgcn_s_barrier()` と memory clobber を使い、false は `__syncthreads()` を使います。scan 内の 3 箇所の barrier で同じテンプレート選択が使われます。Strata はこの環境変数に関するログや無効値警告を出しません。kernel launch error が `cudaGetLastError()` で検出された場合は `prefill <処理名>: <CUDA/HIP error>` を stderr に出して `exit(1)` します。

## 根拠

- 環境変数の全読み取り、値判定、通常 WMMA scan の launch: `src/prefill/kernels.cu:2121-2155`。
- HIP fused 経路の設定、条件、scan launch: `src/prefill/kernels.cu:2160-2199`。
- HIP recurrence dispatch と chunked 経路への条件: `src/prefill/kernels.cu:2876-2892`。
- 通常の prompt 呼び出しと fused fallback: `src/prefill/prefill.cpp:3817-3831,6948-6956`。
- gfx12 runtime arch 判定: `include/strata/kernels/gfx_arch.hpp:15-19,28-30`。
- gfx12 の build pass、最低 token 数、同期実装: `src/prefill/gdn_wmma12.inc:10-19,27-41,196-203,257-264,306-317`。
- launch error の stderr と終了処理: `src/prefill/kernels.cu:102-105`。
