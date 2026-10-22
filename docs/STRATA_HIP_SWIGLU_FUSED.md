# `STRATA_HIP_SWIGLU_FUSED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

gfx906 向けの grouped expert 処理で、SwiGLU の計算と q8_1 量子化を別々の kernel launch で行うか、一つの kernel にまとめるかを選びます。対象となる一般経路では、既定は分離した2段階で、環境変数を有効にすると SwiGLU と q8_1 量子化をまとめた kernel を使います。このスイッチがまとめるのは SwiGLU と量子化であり、gate/up の計算までを一つにするものではありません。

## 値と判定

`env_on()` は、変数が設定されていて、空文字でなく、先頭文字が `0` でない場合に true を返します。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0` または `0` で始まる文字列（例: `0abc`） | 無効 |
| `1`、`true`、`false`、その他 `0` 以外で始まる非空文字列 | 有効 |

大文字小文字や後続文字は判定に影響しません。したがって `false` も有効です。

## 有効になる条件

- `STRATA_HIP_GFX906` が定義されたビルドに限られます。CMake の `STRATA_HIP_GFX906` オプションは gfx906 向け HIP ビルドを選び、同じ compile definition をターゲットに付けます。
- `native_expert_grouped()` の汎用 grouped expert 経路が対象の SwiGLU 段まで到達したときに参照されます。先行する別の kernel 経路が処理を終える場合、この分岐には到達しません。
- 呼び出し側の grouped-v1 (`v1`) が有効なら `sw_v1` は常に true となり、この変数を有効にしても分離 kernel を使います。
- `L.had_block > 0` の場合も、入力に Hadamard 変換を適用するため分離 kernel を使います。
- gfx906 以外の CUDA/HIP/SYCL ビルドでは、この変数を読む分岐がプリプロセッサで除かれます。通常の CUDA ビルドは `v1` だけで分離/融合を選びます。

## 実行時の詳細

`native_expert_grouped()` 内の関数ローカル `static const bool` として判定されるため、最初にその分岐へ到達した時点で値が固定されます。その後に環境を変更しても、同じプロセスでは再評価されません。`cap_groups <= 0` または `cap_entries <= 0` で関数が早期 return する呼び出しでは判定に到達しません。

gfx906 で `v1` が false、`L.had_block == 0`、かつ環境変数が有効なら、`swiglu_q8_1_entries_kernel` を起動し、各要素について `silu(gate) * up` を計算して q8_1 ブロックへ格納します。無効の場合は `swiglu_entries_kernel` と `quantize_q8_1_kernel` を別々に起動します。Hadamard 経路では、分離処理の間に `hadamard_rows()` も実行します。ソースコメントは融合 kernel の結果が分離処理と bitwise 同一になる設計としていますが、この調査では性能測定を行っていません。

この変数自体に対応する利用者向けログや警告は実装されていません。CMake の gfx906 向け `native_grouped_fused_parity` テストは、この変数を `1`、`STRATA_EXP_MODE` を `7` にして実行するよう構成されています。

## 根拠

- `CMakeLists.txt:75-78,149-164` — gfx906 build option と `STRATA_HIP_GFX906` compile definition。
- `src/kernels/cuda/iq_kernels.cu:3273-3276`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3202` — 共通の `env_on()` 判定。
- `src/kernels/cuda/iq_kernels.cu:5212-5230`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5692-5755` — gfx906 限定の読み取り、v1/Hadamard 条件、分離・融合 kernel の選択。
- `src/kernels/cuda/iq_kernels.cu:2730-2756` — 融合 SwiGLU/q8_1 kernel の計算。
- `CMakeLists.txt:1055-1058` — gfx906 parity test における環境変数設定。
- `docs/AMD_HIP.md:822-850` — gfx906 のビルド条件。文書内にこの環境変数の一般的な利用手順や性能測定値は見つかりませんでした。
