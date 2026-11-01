# `STRATA_TC_SM75`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の native GGUF weight dequantization で、出力の 32 要素グループを通常の要素ごとの store ではなく 16-byte の vector store で書く経路を選びます。名前に `TC` が含まれますが、この分岐で切り替わるのは dequant kernel の store 形式です。

本番では `src/prefill/prefill.cpp` から `Gemm::native()` に入り、native 型の weight を `dequant_f16()` で FP16 scratch に変換する経路などで使われます（`src/prefill/prefill.cpp:2698`, `src/prefill/gemm.cu:1346-1347,1456-1457`）。同じ `launch<T>()` は `dequant_bf16()`, `dequant_f16()`, `dequant_f16_ld()`, `dequant_f32()` からも呼ばれます（`src/kernels/cuda/dequant_bf16.cu:429-459`）。

## 値と判定

対象 GPU が compute capability 7.5 と判定された場合だけ `sm75_switch("STRATA_TC_SM75", ...)` が環境変数を読みます。変数が設定されていれば `std::atoi(value) != 0`、未設定なら `STRATA_SM75_PERF` の判定に従います（`include/strata/core/tc_sm75.hpp:21-23`, `include/strata/core/sm75_series.hpp:39-44`）。

| `STRATA_TC_SM75` | 判定 |
|---|---|
| 未設定 | `STRATA_SM75_PERF` が 0 以外なら有効、それ以外は無効 |
| 空文字 | `atoi("") == 0` なので明示的に無効 |
| `0`, `junk`, `0x1` | `atoi` の結果が 0 なので無効 |
| `1`, `2`, `-1`, `1junk`, ` 1x` | 先頭の数値部分が 0 以外なので有効 |

全体の文字列検証はせず、先頭の空白・符号と、先頭から続く整数部分を `atoi` が変換します。したがって、設定値が `0` と解釈される場合は、`STRATA_SM75_PERF=1` でも個別設定が優先して機能を無効にします。反対に、変数が未設定なら系列設定が fallback になります。系列側は `sm75_series()` の関数内 `static const bool` として初回評価時に cache されますが、`STRATA_TC_SM75` 自体は `sm75_switch()` の呼び出しごとに `getenv()` されます（`include/strata/core/sm75_series.hpp:24-30,39-44`）。

## 有効になる条件

- CUDA dequantizer が使われ、実行時の device 属性が compute capability 7.5 であること。`STRATA_EMULATE_CC=75` が設定されたテスト経路では、`cc_major_of()` / `cc_minor_of()` が 7.5 として扱います（`include/strata/core/sm75_series.hpp:33-37`, `include/strata/core/emulate.hpp:14-24`）。
- dequant 出力先が 16-byte aligned で、`ld * sizeof(T)` が 16 の倍数であること。device 選択または compute capability 属性取得に失敗しても vector 経路を選びません（`src/kernels/cuda/dequant_bf16.cu:384-395`）。
- `launch<T>()` の実行まで到達すること。Q8_0 の contiguous・aligned 専用 kernel が選ばれた場合は先に return します。Q4_K/Q5_K/Q6_K/IQ4_XS は、ブロックと出力の alignment などに加え `STRATA_DEQUANT_WIDE` 経路が有効なら wide kernel が先に選ばれ、この変数の分岐には到達しません（`src/kernels/cuda/dequant_bf16.cu:361-382`）。
- `dequant_f16()` は IQ-only type では `iq_dequant_f16()` に早期 return します。`dequant_f16_ld()` も IQ-only type、未対応 type/shape、`ld < cols` または `ld % 8 != 0` なら kernel を起動せず `false` を返します（`src/kernels/cuda/dequant_bf16.cu:424-426,434-450`）。

`STRATA_TC_SM75` と `STRATA_SM75_PERF` のほかに CLI 引数でこの分岐を上書きする処理は見つかりません。`STRATA_TC_SM75` の未設定時には `STRATA_SM75_PERF` が既定値を決めます。

## 実行時の詳細

`Gemm::native()` の通常経路では、量子化 weight を `dequant_f16()` で FP16 化してから `f16()` の GEMM に渡します。scratch に収まらない場合は行スライスごと、`STRATA_DEQUANT_SIDE` の side-stream 経路では別 stream 上で同じ dequantizer を呼びます。HIP の padded-weight 経路でも `dequant_f16_ld()` / `dequant_f16()` の呼び出しがありますが、Turing の 7.5 条件を満たさない device ではこのスイッチは true になりません（`src/prefill/gemm.cu:1357-1362,1366-1378,1426-1457`）。

条件を満たすと `dequant_kernel<TYPE, T, true>` が 32 個分を register buffer に変換し、16-byte store で出力します。条件を満たさない場合は `dequant_kernel<TYPE, T, false>` が要素ごとに書きます。カーネルのコメントは算術と順序は同じで store 幅だけが異なると説明しています（`src/kernels/cuda/dequant_bf16.cu:172-194,393-409`）。

環境変数の有効・無効を知らせるログや無効値警告はありません。通常の dequant launch が失敗した場合は `dequant launch: <CUDA error>` を stderr に出して `exit(1)` します。未対応 type/shape は `dequant: unsupported type ...` を stderr に出して `exit(1)` します。いずれもこの環境変数専用の失敗経路ではありません（`src/kernels/cuda/dequant_bf16.cu:351-355,411-412`）。

## 根拠

- 候補名の直接参照は `include/strata/core/tc_sm75.hpp:22` の helper 引数と同 header のコメントです。実際の環境読み取りは `include/strata/core/sm75_series.hpp:40-44` の動的な `getenv(name)` に到達します。
- 値変換、系列 fallback と cache: `include/strata/core/sm75_series.hpp:24-30,39-44`。
- compute capability 判定とテスト用 emulation: `include/strata/core/sm75_series.hpp:33-37`, `include/strata/core/emulate.hpp:14-24`。
- kernel の vector store と選択条件、先行する Q8_0 / wide 経路: `src/kernels/cuda/dequant_bf16.cu:172-194,284-304,347-412`。
- native weight prompt GEMM の呼び出し: `src/prefill/prefill.cpp:2698`, `src/prefill/gemm.cu:1346-1457`。
- `docs/DETAILS.md:1069-1079` は Turing 向け kernel 群を opt-in と説明し、この変数を個別スイッチの一つに挙げています。同資料は対象 Turing kernel の実機確認がない旨も記しています。実装コメントも測定機について説明していますが、本調査では性能測定を行っていません。
