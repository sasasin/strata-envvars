# `STRATA_SM70_TABLE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の Volta（compute capability 7.0、sm_70）で、3つの最適化経路を opt-in で有効にします。

- hyper-connection（HC）の multi-token read に、Volta 向け latency-hidden norm/up カーネルを選びます。
- grouped native expert の expert mode 8（SwiGLU と q8_1 quantize を含む fused gate/up 経路）を選びます。
- interleaved native MMVQ の対応判定で Volta 向け rows table を許可します。

## 値と判定

3つの読み取り箇所はいずれも `std::atoi` の結果が 0 以外かで判定します。文字列全体の数値 parse や `1` との比較ではありません。

| 値 | 各経路での判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数値に変換できない文字列（例: `true`） | `atoi` が 0 を返すため無効 |
| `0`、`0abc`、`0.5` | 先頭の整数変換が 0 のため無効 |
| `1`、`2`、`-1`、`1abc`、` 1` | `atoi` が 0 以外を返すため有効 |

したがって、`STRATA_SM70_TABLE=1` が一般的な指定ですが、コード上は正の `1` に限定されません。空白や後続文字の扱いも `atoi` の変換に従います。

## 有効になる条件

- **HC norm/up:** CUDA ビルドで、現在の GPU が sm_70 であることが必要です。`STRATA_GR_FAST` が `atoi` で 0 以外なら、この変数より優先して fast path を選び、`STRATA_GR_FAST=0` ならこの変数が有効でも fast path を使いません。HIP GFX906 ビルドでは別の既定経路が使われ、この変数は参照されません。
- **expert mode 8:** CUDA ビルドの grouped native expert 経路で、現在の GPU が sm_70 であることが必要です。`STRATA_EXP_MODE` の `atoi` 結果が 0 以上なら、その値が自動選択より優先されます（例: `STRATA_EXP_MODE=0` は CUDA layout）。CUDA の grouped expert 呼び出しで `grid_groups > 0 && grid_groups < cap_groups` の場合は mode 0 を使うため、この変数による mode 8 選択はその呼び出しでは適用されません。mode 8 でも、実際の fused gate/up カーネルには expert weight type と `n_ff % 32 == 0` の条件があります。
- **interleaved MMVQ rows table:** CUDA のみの機能です。GPU が sm_70 であり、`STRATA_MMVQ_IL` が有効で、対応する type・shape に非ゼロの rows 数がある場合に限って使われます。`STRATA_MMVQ_IL` は未設定なら有効、先頭文字が `0` なら無効です。対応する `native_mmvq_il` の type は 23、12、13、14、11 で、列数は 1〜4です。Volta の table に登録がない type や shape は通常の `native_mmvq` に fallback します。`STRATA_MMVQ_IL_ROWS` のユーザー指定行設定が一致する場合は、architecture table より先にその値が使われます。
- Pascal sm_60、他の GPU 世代、および HIP の interleaved MMVQ stub をこの変数で有効化することはありません。

## 実行時の詳細

HC の `gr_fast()` は、ベンチ用 setter `fused_gr_set_fast()` の値を最優先し、続いて `STRATA_GR_FAST` を関数内 static 値として一度 parse します。そのどちらも指定されていない CUDA の場合に、この変数を読みます。sm_70 判定は device ordinal ごとに static cache されますが、`STRATA_SM70_TABLE` 自体は HC の呼び出し時に再度 `getenv` / `atoi` されます。

Expert mode は `STRATA_EXP_MODE` をプロセス内 static 値として一度読みます。環境指定とベンチ setter `native_expert_set_mode()` のいずれも mode を指定しない場合に、現在の CUDA device の能力を調べ、`STRATA_SM70_TABLE` を読んだ結果を device ordinal ごとの mode cache に保存します。mode 8 は shared memory 上で grid とグループ activation を扱い、条件に合う形式では SwiGLU / q8_1 quantize と gate/up を fused kernel で処理します。

Interleaved MMVQ は verifier が `native_mmvq_il_supported()` を確認して選びます。sm_70 の opt-in を含む architecture 判定結果は device ordinal ごとに cache されるため、その device で最初に判定した後の環境変更は再評価されません。対応しない場合、呼び出し側は標準 `native_mmvq` に進みます。HIP では interleaved support 関数が常に false を返します。

これらの環境値判定自体による専用ログや警告はありません。GPU 属性取得失敗などで選択条件が成立しないときは、その経路の fallback が使われます。

## 資料との照合

`docs/NVIDIA_V100.md` は、この3経路を sm_70 向け opt-in として説明し、`STRATA_EXP_MODE`、`STRATA_MMVQ_IL`、`STRATA_GR_FAST` が個別に引き続き適用されると記しています（`docs/NVIDIA_V100.md:38-44,85-91`）。同資料の 22.8 ms→21.2 ms は V100-SXM2 上の verify window GPU work についての資料中の測定値であり、他の環境での性能を示すものではありません。

HEAD 内のコミュニティ測定記録は、Tesla V100-SXM2-32GB 1台、UD-IQ4_XS native-experts pack、262144 context、int8 KV、同一条件で変数だけを切り替えた2組の順序入れ替え run を報告しています。decode は 28.16/28.64→30.92/32.94 tok/s（+9.8%/+15.0%）、生成 token は4 run間で bit-identical と記録されています。これは同記録の測定結果で、異なるモデル・GPU・設定の性能を保証しません（`bench/results/2026-10-08-community-v100-sm70-table/README.md:1-16,35-42,55-60`; 集約は `docs/COMMUNITY_BENCHMARKS.md:30-37`）。

## 根拠

- `src/kernels/cuda/fused_gr.cu:28-33,882-898,1813-1828,1030-1045`: ビルド条件、sm_70 判定、優先順位、実際に選ぶ norm/up kernel。
- `src/kernels/cuda/iq_kernels.cu:2816-2832,3406-3431,3492-3538`: CUDA/HIP layout 条件、mode 優先順位と cache、grouped call の mode 0 条件、mode 8 kernel の条件。
- `src/kernels/cuda/native_mmvq.cu:2518-2526,2560-2567,2640-2709,2711-2747`: CUDA 専用実装、Volta rows table、architecture cache、shape/type gate と fallback。
- `src/core/verify.cpp:136-139,1085-1095`: `STRATA_MMVQ_IL` の既定値と interleaved path の呼び出し。
- `docs/NVIDIA_V100.md:38-44,85-91`, `bench/results/2026-10-08-community-v100-sm70-table/README.md:1-16,35-42,55-60`, `docs/COMMUNITY_BENCHMARKS.md:30-37`: 設計説明と測定記録。
