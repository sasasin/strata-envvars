# `STRATA_FORCE_ISA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata が持つ CPU 命令セットの実行時 probe を低い tier に制限し、CPU kernel の dispatch を狭める診断・互換確認用の変数。実 CPU や OS が持たない命令を追加で使えるようにはしない。主なエンジン実装は `engine/src/kernels/cpu/expert_layout.cpp` と `engine/src/quant/isa.cpp` で、HY4 CPU experts と Vision ツールにも独立した読み取り実装がある。Strata が同梱する ggml-cpu のコンパイル済み ISA はこの変数では変更されない（`engine/src/kernels/cpu/expert_layout.cpp:26-39`）。

## 値と判定

同じ名前でも、実装ごとに受け付ける文字列と不正値の扱いが異なる。数値変換はせず、C++ 実装は値全体を大文字小文字を区別して比較する。

| 実装 | unset / 空文字 | 有効値と効果 | 無効値 |
|---|---|---|---|
| CPU expert dispatch (`engine/src/kernels/cpu/expert_layout.cpp`) | 上限なし（cap 3）。空文字も unset と同じ | `avx2` は AVX-512/VNNI を抑止し AVX2 まで、`avx` は AVX2 以上を抑止し AVX1 まで、`sse` / `sse4.2` / `none` は AVX1 以上を抑止 | それ以外（例: `0`, `1`, `true`, `AVX`, `avx2 `）は無視して上限なし。stderr に警告 |
| Quant layer (`engine/src/quant/isa.cpp`, x86) | 上限なし。空文字も unset と同じ | `avx2`, `avx`, `sse` は順に AVX-512、AVX2、AVX を上限から外す | それ以外（`sse4.2`, `none` を含む）は無視して上限なし。stderr に警告 |
| HY4 CPU experts (`engine/src/hy4flash/run/hy4_cpu_experts.cpp`, x86) | probe を制限しない。空文字も制限しない | `avx2`: AVX-512 と AVX-VNNI を抑止。`avx2-vnni` / `no-avx512`: AVX-512 を抑止。`avx` / `sse`: AVX2 以上を抑止 | その他は無視。ここでは `STRATA_FORCE_ISA` 自身の警告なし |
| HY4 CPU experts (NEON) | dot-product probe を制限しない。空文字も制限しない | `scalar` / `lib` は NEON dot-product kernel を無効化 | その他は無視し、警告なし |
| Vision の CPU tower (`terminal/tools/vision/own/cpu_caps.h`) | x86 は上限なし。AArch64 は NEON | x86: `scalar`, `sse41`, `avx`, `avx2`, `avx512` は該当 tier を上限にする。AArch64: `scalar` のみ NEON を scalar にする | x86 の未知値（空文字を含む）は `avx512` 上限として扱われる（通常は CPU の最高 tier より上限が高く、結果を変えない）。AArch64 の `scalar` 以外は NEON のまま |

エンジンの expert dispatch は `cpu_isa_cap()` が `static const` に値を一度保存し、cap 3/2/1/0 を返す。x86 CPU feature probe も関数内 `static` で保存される。`STRATA_FORCE_AVX2=1` が設定されると、その expert dispatch では `STRATA_FORCE_ISA` の値に関係なく AVX-512 probe も false になる（`engine/src/kernels/cpu/expert_layout.cpp:26-39,75-82`）。

Quant layer は `strata::quant::caps()` の初回呼び出しで CPU feature と cap を保存し、以後同じ値を使う。cap 3 は無制限、2 は AVX-512系を除外、1 はさらに AVX2系、0 はさらに AVXを除外する（`engine/src/quant/isa.cpp:48-57,59-87,109-112`）。

## 有効になる条件

- **エンジンの CPU expert kernels**: x86 では `cpu_avx512_ok()`、`cpu_avx2_ok()`、`cpu_avx1_ok()` などの gate が cap を参照し、Q2_0、native expert、IQ/KQ/NVFP4 等の Strata 所有 kernels の選択を狭める。実 CPU/OS の CPUID・XGETBV 条件も引き続き必要（`engine/src/kernels/cpu/expert_layout.cpp:80-110,206-265`; dispatch 例 `engine/src/kernels/cpu/expert_layout.cpp:465-485`）。
- `STRATA_FORCE_ISA=avx2` は VNNI tier を有効にする cap 3 未満のため `cpu_vnni_ok()` も無効にする。`STRATA_VNNI_TIER=1` があっても cap が上書き条件となり、AVX-512 VNNI tier は選ばれない（`engine/src/kernels/cpu/expert_layout.cpp:188-203`）。
- 通常の x86 build は起動時に AVX2 + FMA + F16C が必要。`avx`, `sse`, `sse4.2`, `none` により `cpu_avx2_ok()` が false になると、`STRATA_ISA_FLOOR` のない通常 build の `strata generate` は AVX2 不在として stderr に理由を出し、status 2 で終了する。低 ISA build は対応する `STRATA_ISA_FLOOR=avx` または `none` と、その CPU が build floor を実行できることが別途必要（`engine/src/program/generate.cpp:5331-5367`）。
- この変数は ggml-cpu が build 時に含めた ISA を変えない。よって cap により Strata 自前 kernel が使えなくなったとき ggml-cpu に fallback する経路も、build floor・モデル pack 条件による（`engine/src/kernels/cpu/expert_layout.cpp:26-39`; `engine/src/program/generate.cpp:5332-5367`）。
- **Quant layer / Inkling host kernels**: x86 の `strata::quant::caps()` を参照する dispatch で有効。Inkling の host AVX2/AVX-512 kernels は対応する TU が build に含まれることも必要。AVX-512 gate は `INK_HOST_AVX512_BUILT` がない build では常に false（`engine/src/quant/isa.cpp:59-87,109-120`; `engine/src/inkling2/ink_host_avx2.cpp:12-25`; `engine/src/inkling2/ink_host_avx512_gate.cpp:12-19`）。Quant layer の ARM64 probe は NEON/feature 判定にこの変数を適用しない（同 `isa.cpp:88-103`）。
- **HY4 CPU experts**: `HY4_KERNELS` の x86 kernel build、または `HY4_NEON_KERNELS` の ARM build でのみ対応する branch がある。x86 で `STRATA_CPUEXP_KERNEL` に明示値を指定すると、それが probe 後の自動選択より優先するが、cap 後の probe が false にした kernel を強制できない。unsupported 指定は `best` に戻る（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1131-1185,1820-1857`）。
- **Vision CPU tower**: tower load 時 `quant::best_isa()` を使って ops table を選ぶ。これは独立の helper であり、engine quant helper と値規則が異なる（`terminal/tools/vision/own/vit_cpu.cpp:142-148`; `terminal/tools/vision/own/cpu_caps.h:88-106`）。

## 実行時の詳細

通常の engine path では、`cpu_isa_cap()` の最初の呼び出し時に環境を読む。expert probe の `static` 結果と quant の `static const Caps` も初回評価後に保持されるため、プロセス起動後に環境を変更しても該当プロセス内の選択は更新されない。値を子プロセスへ転送する Strata 側の処理は確認できなかった。CPU dispatch の cap は CLI 引数ではなく、別環境変数 `STRATA_FORCE_AVX2=1` が AVX-512 probe をさらに止める。ggml-cpu の選択はこの cap を受け取らない（`engine/src/kernels/cpu/expert_layout.cpp:26-39,75-82`; `engine/src/quant/isa.cpp:109-112`）。

HY4 は初期化時に `probe_kernel_caps()` を呼び、その結果から best kernel を選んだ後で `STRATA_CPUEXP_KERNEL` を読む。`STRATA_FORCE_ISA` の probe は呼び出しごとで static cache ではないが、実際の kernel は初期化時に `kern` に保存される。別途 `CpuExperts::selftest_kernels()` も同じ probe を使う（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1154-1185,1820-1857,2957-2975`）。

Vision helper は CPU feature `caps()` のみ static cache し、`best_isa()` ごとに `getenv("STRATA_FORCE_ISA")` を評価する。実際の tower load は `VitCpu::load()` で `best_isa()` を呼んで ops table を決める（`terminal/tools/vision/own/cpu_caps.h:67-70,88-106`; `terminal/tools/vision/own/vit_cpu.cpp:142-148`）。

## ログと測定値

engine expert dispatch と quant layer は、無効値に対して `strata: STRATA_FORCE_ISA=%s is not avx2, avx or sse; ignored\n` を stderr に出す。engine expert dispatch は `sse4.2` と `none` を有効値として受け入れる一方、quant layer は同じ値を無効として警告する。空文字は両者とも unset 相当で警告しない（`engine/src/kernels/cpu/expert_layout.cpp:29-38`; `engine/src/quant/isa.cpp:49-56`）。

通常 build で強い cap を指定して AVX2 gate が閉じた場合、`strata generate` は `this CPU (...) does not support AVX2 with FMA and F16C...` の理由を stderr に出し、status 2 を返す（`engine/src/program/generate.cpp:5344-5351`）。HY4 の無効 `STRATA_FORCE_ISA` はそれ自体ではログを出さないが、最終的な kernel 名は起動時の `[cpuexp] ... kernel=%s` 行で観測できる。ここでは性能値を記載しない。

## 根拠

- `engine/src/kernels/cpu/expert_layout.cpp:26-39,75-82,80-110,188-208,241-265,319-327,465-485`
- `engine/src/quant/isa.cpp:48-57,59-112,114-140`
- `engine/src/inkling2/ink_host_avx2.cpp:12-25`
- `engine/src/inkling2/ink_host_avx512_gate.cpp:12-19`
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1131-1185,1820-1858,2957-2975`
- `engine/src/program/generate.cpp:5331-5367`
- `terminal/tools/vision/own/cpu_caps.h:67-106`
- `terminal/tools/vision/own/vit_cpu.cpp:142-148`
- `docs/DETAILS.md:1274`（資料の説明は主 engine の `avx2|avx|sse` cap と一致。実装上の差異は上記 helper ごとに記載。）
