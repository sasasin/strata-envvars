# `STRATA_GFX906_ATTN_QUERY_SWIZZLE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの動作は対象外。

## 役割

gfx906 向け QSA batched attention の query データを shared memory（LDS）へ置くとき、次元の並びを XOR で入れ替える特殊化を選びます。スコア計算時には並びを逆変換するため、論理上の query 値と演算順序は変えない実装です。対象は `qsa_decode_attn_batch()` のみで、通常の decode step 用 `qsa_decode_attn_step()` はこの変数を読みません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定値の先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` など |
| その他 | 無効。`0`, `true`, ` 1` など |

文字列全体の比較や数値変換はせず、`v[0] == '1'` だけを見ます。判定結果は関数内の `static const bool` に保存されるため、最初の `qsa_decode_attn_batch()` 呼び出し後に環境変数を変更しても反映されません。根拠: `src/kernels/cuda/qsa_decode_attn.cu:639-643`。

## 有効になる条件

この変数の分岐自体が `STRATA_HIP_GFX906` ビルドにだけコンパイルされます。通常の CUDA、wave32 HIP、SYCL では同名の読み取り箇所がなく、設定しても Strata のこの処理には影響しません。gfx906 backend は CMake の `STRATA_HIP_GFX906` オプションで有効になり、`STRATA_HIP_GFX906=1` の compile definition が付与されます（`CMakeLists.txt:64-70,122-138`）。

ビルド後も、各 batched dispatch で以下をすべて満たす必要があります。

- 変数の値判定が有効。
- `STRATA_ATTN_LANECELL` が有効でない。こちらも先頭文字 `1` を判定し、有効なら lane-cell kernel が優先されます。
- KV pool が `kv_mode == 1`（Q8/INT8 K pool）。Q4 または hybrid pool では対象外です。
- 呼び出しスレッドの現在の HIP device が gfx906 で、wavefront 幅が 64。

device 判定は各対象 dispatch で現在 device を問い合わせます。device properties はスレッドごとに直近の device ordinal についてキャッシュします。gfx906 の名前は `gfx_arch_is()` により `gfx906` と完全一致するか、`gfx906:` で始まる場合に許可されます。HIP API が失敗した場合は無効として扱います（`src/kernels/cuda/qsa_decode_attn.cu:547-572`, `include/strata/kernels/gfx_arch.hpp:15-20`）。

## 実行時の詳細

条件を満たした場合、`attn_chunk_kernel` の query LDS 書き込みで次元 `d` を `d ^ ((d >> 3) & 4)` に置き換え、スコア読み出し側で逆変換します。カーネル注釈では 16-byte alignment と 12 KiB tile を維持し、FP operand と演算順序を変えない設計とされています（`src/kernels/cuda/qsa_decode_attn.cu:117-123,144-152`）。

この dispatch は prompt、verification、MTP から呼ばれる batched 経路に含まれます。各経路では pool 形式などの条件次第で別 kernel が選ばれるため、呼び出しがあることだけでは swizzle の実行を意味しません（`src/prefill/prefill.cpp:2840-2850`, `src/core/verify.cpp:1367-1393`, `src/core/mtp.cpp:823-826`）。通常の decode step は `qsa_decode_attn_step()` を呼びます（`src/core/layer.cpp:1136-1138`）。

関連する `STRATA_GFX906_ATTN_QUERY_SWIZZLE_TRACE` が設定されていると、各スレッドの最初の batch 呼び出しで stderr に `strata attn-query-swizzle: active=%d nq=%lld cap=%lld kv_mode=%d lane_cell=%d` を出します。この trace 変数は値の内容ではなく設定有無を判定します（`src/kernels/cuda/qsa_decode_attn.cu:644-650`）。また、swizzle が選ばれた後に `STRATA_GFX906_ATTN_REDUCE12` が正確に文字列 `1` なら、同 kernel の別 specialization が選ばれます（同:664-687）。

## 文書・測定値との照合

`docs/AMD_HIP.md:465-477` は gfx906 向けの opt-in 機能で、gfx906 build にだけ含まれ、既定では無効と説明しています。これは compile guard と値判定に一致します。

リポジトリ内の `bench/results/2026-10-08-gfx906-qsa-query-swizzle/README.md:13-20,33-41,61-72` には、クリーン upstream patch の component 測定（特定の2台の gfx906、`n_q=32`、context 65,536 の A/B/B/A で約14.65%）と、単一の 65,536 token 入力・1,024 token 出力のモデル比較が記録されています。レポート自身が限定的な測定で一般的な速度向上を示さないと明記しており、実験対象の patch/build と本調査対象 HEAD 全体は同一とは確認できないため、この数値を現 HEAD の一般的な性能としては扱いません。

## 根拠

- 環境変数の読み取り、先頭文字判定、dispatch 条件、trace: `src/kernels/cuda/qsa_decode_attn.cu:637-650`
- gfx906/wave64 guard と device cache: `src/kernels/cuda/qsa_decode_attn.cu:547-572`
- kernel specialization と LDS layout: `src/kernels/cuda/qsa_decode_attn.cu:117-152,660-703`
- gfx906 build 条件: `CMakeLists.txt:64-70,122-138`
- 呼び出し元: `src/prefill/prefill.cpp:2840-2850`, `src/core/verify.cpp:1367-1393`, `src/core/mtp.cpp:823-826`, `src/core/layer.cpp:1136-1138`
