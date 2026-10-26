# `DS4_GG_IQ512`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 実行ファイル `strata-dsv41` の ggml 量子化 expert 用 CPU lane で、対応する i-quant 型の gate/up/down 行 dot に Strata の AVX-512 実装を選ぶか制御します。AVX-512 行実装は `ggml-cpu` の dot と結果が一致するか、型ごとに実行時検査されます。これは DSV4.1 専用の実行経路で、一般の Strata CPU expert 経路を切り替える変数ではありません。

## 値と判定

変数は `std::atoi` で整数化され、結果が 0 かどうかで判定されます。文字列全体の妥当性検査はありません。

| 状態 | 判定 |
|---|---|
| 未設定 | AVX-512 対応 CPU なら自動選択規則を使う（mode 2） |
| 数値化結果が 0 | AVX-512 行を使わない（mode 0） |
| 数値化結果が 0 以外 | 自動選択規則を外し、対応型では AVX-512 行を常に候補にする（mode 1） |
| AVX-512 非対応 CPU | 値にかかわらず無効（mode 0）。環境値の有無・内容による上書きはない |

`atoi` のため、`1`, `-1`, `2`, `1tail`, ` 1` はいずれも非 0 になり有効です。`0`, `00`, `junk`, 空文字は 0 となり無効です。先頭の空白と符号は `atoi` の規則に従い、数値の後ろにある文字列は判定に使われません。オーバーフローなど `atoi` で表現できない入力の結果は、このコードから定義できません。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` ではない構成で `strata-dsv41` がビルドされ、さらに `STRATA_NATIVE_EXPERTS=ON` の場合が対象です。後者で `STRATA_DSV41_TQ_CPU` が定義され、ggml CPU lane が有効になります。
- `DS4_GG_IQ256` の処理が先に CPU lane を許可している必要があります。`DS4_GG_IQ256` が `0` と解釈される場合、AVX-512 の判定へ到達せず、この変数も効果を持ちません。未設定時の `DS4_GG_IQ256` は CPU の AVX2/FMA/F16C 対応時に mode 2 となり、対応がない場合は mode 0 です。
- `cpu_avx512_ok()` が true である必要があります。Strata の ISA 上限設定 `STRATA_FORCE_ISA` が AVX2 以下を指定する場合や、`STRATA_FORCE_AVX2` の先頭文字が `1` の場合も AVX-512 は無効です。CPU と OS の AVX-512 状態保存、および必要な AVX-512 feature bits も検査されます。
- 型は `IQ2_XXS` (16), `IQ2_XS` (17), `IQ3_XXS` (18), `IQ1_M` (29), `IQ3_S` (21), `IQ3_M` (22) に限られ、加えて AVX512_VPOPCNTDQ が必要です。その他の型ではこの変数が有効でも AVX-512 行へ進みません。
- AVX-512 候補になった後も、`own_ok()` が型ごとの複数 token 数の結果を `ggml-cpu` と比較します。不一致または検査条件不足なら AVX-512 を使わず、AVX2 行または `ggml-cpu` dot にフォールバックします。

## 実行時の詳細

`use_iq256()` が ggml CPU lane の gate/up dot 処理ごとに AVX-512 を候補にし、必要に応じて `want_512(type, nt)` を呼びます。最初の判定で `g_iq512` に値を保存し、以後そのプロセス内では環境変数を読み直しません。したがって実行中に環境を書き換えても判定は変わりません。CPU 非対応の場合は `cpu_avx512_ok()` 自体も結果を static cache するため、そのときの環境・CPU 判定が固定されます。

環境変数を未設定にした mode 2 は、AMD CPU family が `0x19` (Zen 3/4) 以上の場合にだけ自動規則を使います。それより古い AMD family、Intel、その他の vendor では AVX-512 を選びません。自動規則は `IQ2_XXS` と `IQ2_XS` では token 数を問わず選択、`IQ3_XXS` では2 token以上、`IQ1_M` では2 token以上または Zen 5 以降に限り選択します。`IQ3_S` と `IQ3_M` は自動規則では選択されません。環境変数を非 0 にすると vendor/family と token 数のこの規則は適用されませんが、CPU feature、型対応、実行時一致確認は引き続き必要です。

この変数の値による専用ログはありません。動作差は CPU lane が AVX-512 行、AVX2 行、または `ggml-cpu` dot のどれを呼ぶかです。Strata の資料にこの環境変数についての測定条件付き性能値は見つかりませんでした。ソースコメントには Zen 5 の16 thread、および Zen 4 Ryzen 5 7600 の6 threadで行単体を測った値がありますが、資料中の測定結果であり、ここでは他環境での性能保証とは扱いません。Intel AVX-512 は未測定とソースコメントに記載されています。

## 根拠

- `src/dsv41/ds4_gg_cpu.cpp:179-200` — mode 判定、CPU 自動規則、型と token 数の選択条件。
- `src/dsv41/ds4_gg_cpu.cpp:203-232` — `DS4_GG_IQ256` との優先関係、AVX-512/AVX2/ggml dot への分岐。
- `src/dsv41/ds4_gg_cpu.cpp:99-148` — 型ごとの一度だけの結果比較と不一致時の fallback。
- `src/kernels/cpu/expert_layout.cpp:26-38,42-75` — `STRATA_FORCE_ISA`、`STRATA_FORCE_AVX2`、CPU/OS feature 判定とキャッシュ。
- `src/kernels/cpu/iq_avx512.cpp:586-605` — AVX512_VPOPCNTDQ と対応型の確認。
- `src/dsv41/ds4_iq_cpu.cpp:770-774` — ggml CPU lane から ggml 型 gate/up 計算への呼び出し。
- `CMakeLists.txt:800-811,833-835` — DSV4.1 実行ファイルと native expert CPU lane のビルド条件。
