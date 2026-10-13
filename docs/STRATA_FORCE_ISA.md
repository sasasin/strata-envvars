# `STRATA_FORCE_ISA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ（ggml-cpu 含む）の環境変数は対象外。

## 役割

Strata 自身の x86 CPU 命令セット・プローブ（`cpu_avx512_ok()` / `cpu_avx2_ok()` / `cpu_avx1_ok()` / `cpu_gather_fast()` / `cpu_avxvnni_ok()`）に上限を掛けます。この PC が実際に AVX-512 を持っていても、エンジンのディスパッチは「この CPU は指定したレベルで止まっている」と判断して、下のランク（世代別カーネル）を選びます。

実装は `src/kernels/cpu/expert_layout.cpp:25-39` の `cpu_isa_cap()` 一つだけで、返す整数は 3（上限なし）、2（AVX2）、1（AVX）、0（SSE4.2）です。用途はコードの注釈どおり「tests, the experimental older-CPU builds」で、通常の利用者向け設定ではありません（`docs/INSTALL.md:157-161` は older-CPU ビルドの検証をこの変数でやったと記しています）。

ggml-cpu は影響を受けません。注釈の言い方: 「ggml-cpu is not affected: it runs what the build compiled it for」（`src/kernels/cpu/expert_layout.cpp:27`）。つまりビルド時に選ばれた ggml-cpu のコードパスはそのままです。GPU 側のカーネル選択にも影響しません。

## 値と判定

文字列全体を parse します。`atoi` ではなく `std::string` の完全一致比較で、大文字小文字・空白・接尾辞を区別します。

| 値 | `cpu_isa_cap()` の結果 |
|---|---|
| 未設定 | 3（上限なし） |
| 空文字 | 3（上限なし。`f[0] == '\0'` を未設定と同じ扱い） |
| `avx2` | 2 |
| `avx` | 1 |
| `sse` / `sse4.2` / `none` | 0 |
| それ以外の任意の文字列 | 3（無視）。stderr に一度だけ `strata: STRATA_FORCE_ISA=<値> is not avx2, avx or sse; ignored` |

- 数値（`2`, `1`, `0`）は有効値ではありません。`STRATA_FORCE_ISA=2` は警告が出て上限なしとして扱われます。
- 警告文は受け付ける語を `avx2, avx or sse` とだけ列挙しますが、コードは `sse4.2` と `none` も 0 として受け入れます（`src/kernels/cpu/expert_layout.cpp:34-35`）。
- 判定結果は `static const int cap` に一度だけ保存されます。プロセス起動後の環境変更は反映されません。

## 上限が効くプローブと効かないプローブ

効く（`src/kernels/cpu/expert_layout.cpp`）:

| プローブ | 上限の条件 | 行 |
|---|---|---|
| `cpu_avx512_ok()` | `cap < 3` で false | 44 |
| `cpu_avx2_ok()` | `cap < 2` で false | 108 |
| `cpu_avx1_ok()` | `cap < 1` で false | 143 |
| `cpu_gather_fast()` | `cap < 3` で false | 213 |
| `cpu_avxvnni_ok()` | `cap < 3` で false（older-CPU ビルドでも false） | 255 |

効かない:

- `cpu_sse42_ok()`（165-178）は `cpu_isa_cap()` を見ません。実 CPUID の結果です。したがって `cap = 0` は「上のランクを SSE4.2 まで下げる」効果で、SSE4.2 自体を偽にするものではありません。
- `cpu_avx512bw_ok()`（74-104）も `cap` を見ません。この commit のソースでは呼び出し箇所が見つかりません（宣言と定義のみ）。
- `cpu_features()` / `cpu_require_expert_support()`（314-346）は `cap` を見ません。canonical Q2_0 pack の AVX-512（VNNI + VBMI）必須チェックは実際の CPUID で決まります。
- `STRATA_FORCE_AVX2=1`（先頭文字 `1`）は `cpu_avx512_ok()` / `cpu_avx512bw_ok()` 側で `cap` より先に検査されます（43, 76）。

## 有効になる条件

`cap` が 1 や 0 になった場合、エンジンは起動時に拒否します。条件はビルドの種類で違います。

- 通常ビルド（`isa_floor_build()` が空、AVX2 フロア）: `cap < 2` なら `strata generate` は `this CPU (...) does not support AVX2 with FMA and F16C ...` として exit code 2 で終了します（`src/program/generate.cpp:2660-2667`）。つまり通常ビルドで `STRATA_FORCE_ISA=avx` や `sse` を設定してもエンジンは動きません。この値が効くのは older-CPU ビルド（`STRATA_ISA_FLOOR=avx` / `none` でビルドされたもの）とテストバイナリです。
- older-CPU ビルド: ビルドのフロアより下には下がれません。`STRATA_ISA_FLOOR=avx` ビルドで `cap = 0` にすると `this engine is the older-CPU build for AVX, which this CPU (...) does not have; compile it with STRATA_ISA_FLOOR=none` として exit 2（`src/program/generate.cpp:2668-2676`）。`STRATA_ISA_FLOOR=none` ビルドでは `cap` の任意値で起動します（この場合 ggml-cpu は SSE4.2 用にコンパイルされており、`cap` は Strata 自身のプローブだけを変えます）。
- 起動が通った older-CPU ビルドでは `EXPERIMENTAL older-CPU build (ggml-cpu for ...)` の警告が出ます（`src/program/generate.cpp:2677-2682`）。
- テストバイナリ（`router_dot_parity`, `q8k_quant_parity`）はエンジンの起動拒否を経ないため、モダン CPU 上で `STRATA_FORCE_ISA=avx` により older 経路だけ検査できます（`CMakeLists.txt:1321,1344`）。

native pack（i-quant）の CPU 側で実際に選ばれるランクは、native pack を使う場合に限って観測されます。canonical Q2_0 pack は AVX-512 カーネル必須です（`docs/INSTALL.md:152`）。

## 実行時の詳細

読み取りは `cpu_isa_cap()` の最初の呼び出し時、つまりエンジンの起動時プローブ（`generate.cpp:2660` の `cpu_avx2_ok()`）で一度行われます。結果は static cache され、リクエストごとに読み直しません。子プロセスへの転送や上書きは Strata 側にはありません（`setup.py` はこの変数を読みません）。

値がディスパッチに現れる箇所:

- Q2_0 行と activation quantizer: `q2_rows_any()` / `act_quant_any()`（`src/kernels/cpu/expert_layout.cpp:348-366`）。ただし CPU pool は `q2_native_kernels()`（`include/strata/kernels/cpu/expert_layout.hpp:81`）が真の型だけをここに送るので、`cap < 2` では Q2_0 層は ggml-cpu の `vec_dot` 側になります。`q2_rows_any()` の AVX1 ランクはテスト（`src/kernels/cpu/q2_bitplane_parity.cpp:28-35`）で検査される経路です。
- i-quant の gate/up・down 行: `native_gu_rows()` / `native_down_rows()`（`src/kernels/cpu/native_expert.cpp:141,149,157,170,218`）。`cap = 1` では AVX2 不在扱いになり `iq128_*`（128-bit AVX）ランクが選ばれ、`cap = 0` では Strata 自身のカーネルを全部通らず ggml-cpu の dot になります。
- Q8_K activation quantizer: `q8k_avx2()` / `q8k_avx1()`（`src/kernels/cpu/native_expert.cpp:91-100`）。`cap < 2` で AVX2 コピーは使われません。
- ルーター lookahead の BF16 dot: `src/kernels/cpu/kq_avx2.cpp` の `bf16_rows_dot_multi` は `cpu_avx2_ok()` の後ろ、`kq_avx1.cpp` の `bf16_rows_dot_multi_avx1` は `cpu_avx1_ok()` の後ろ（`sycl/src/core/expert_source.cpp:1495-1500`）。
- IQ256 の gather variant: `iq256_variant()` は `STRATA_IQ256_GATHER` が未設定なら `cpu_gather_fast_here()`（→ `cpu_gather_fast()`）で決めます（`src/kernels/cpu/iq_avx2.cpp:458-461`）。`cap < 3` では gathered variant が off になり、スカラー decode 側になります。明示的な `STRATA_IQ256_GATHER=1` は `cap` より優先されます。
- AVX-VNNI 形: `vnni_on()`（`src/kernels/cpu/iq_avx2.cpp:383`）と `q2_avx2.cpp:169` は `cpu_avxvnni_ok()` を通るので、`cap < 3` で off です。
- `STRATA_IQ3S_MT1` の条件（`src/kernels/cpu/native_expert.cpp:129-131`）は `cpu_gather_fast()` を要求するので、`cap < 3` では効きません。

native pack で `cap < 3` の場合、起動時に選んだランクが stderr に出ます（`src/program/generate.cpp:2776-2783`）。

## 生成結果について

`docs/INSTALL.md:157-161` は、Ryzen 5 7600 + RTX 5070、expert cache 1500 slots、Coder と IQ3_XXS、10 prompts 各 1 回で、older 経路を強制した decode が 26 → 11-17 tok/s（AVX ビルド）、3.5-3.8 tok/s（SSE4.2 ビルド）と記しています。同じ資料は、この強制検証では「答えは正しくエンジンのチェックを通るが、normal build と token by token で同じではない」（ggml-cpu が CPU expert を別 rounding するため）と明記しています。これは記載された測定環境での値で、`STRATA_FORCE_ISA` 単独の性能保証ではありません。

## 根拠

- `src/kernels/cpu/expert_layout.cpp:25-39`（読み取り・判定・警告）、`include/strata/kernels/cpu/expert_layout.hpp:57-59`（意味と 3/2/1/0 の対応）
- `src/kernels/cpu/expert_layout.cpp:44,108,143,165-178,213,255`（cap を見るプローブと見ないプローブ）
- `src/program/generate.cpp:2660-2683,2776-2783`（起動拒否、older-CPU ビルド警告、ランク表示）
- `src/kernels/cpu/native_expert.cpp:91-100,129-131,141,149,157,170,218`、`src/kernels/cpu/iq_avx2.cpp:383,458-461`、`src/kernels/cpu/q2_avx2.cpp:169`、`sycl/src/core/expert_source.cpp:1495-1500`
- `CMakeLists.txt:1321,1344`（テストでの使用）、`docs/INSTALL.md:148-161`（older-CPU ビルドとの関係と測定）

## 確認できていない点

- `cpu_avx512bw_ok()` はこの commit のソースに呼び出し箇所がないため、`cap` を見ないことが実際の挙動に影響するか確認できません。
- 実機の古い CPU（AVX2 がない CPU）での動作は Strata 側で確認されていません。資料の記述はモダン CPU 上で `STRATA_FORCE_ISA` により older 経路を強制した結果です。
- older-CPU ビルド（`STRATA_ISA_FLOOR`）はビルド macro 依存で、この環境でビルドして `cap` とフロアの相互作用を実測していません。
