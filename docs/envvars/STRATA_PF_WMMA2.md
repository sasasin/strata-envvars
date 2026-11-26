# `STRATA_PF_WMMA2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の prompt expert 計算で使う FP16 WMMA 経路に、IQ2_S の gate/up と IQ4_NL の down projection 用の第 2 grouped GEMM kernel を選ばせる opt-in です。変数自体が prompt 経路を有効化するわけではありません。専用 kernel に切り替わるのは `gemm_iq_f16_grouped()` が呼ばれ、型・寸法・アラインメント等の条件も満たした場合です。条件を満たさなければ同関数の既存 kernel 選択へ進みます（`engine/src/kernels/cuda/iq_kernels.cu:7915-7947`）。

prompt 側でこの関数を使う `wmma_l` 経路は、別の `STRATA_PF_WMMA=1` による `pf_wmma()`、MMQ の使用、fused layer でないこと等を必要とします。したがって `STRATA_PF_WMMA2=1` だけでは有効になりません（`engine/src/prefill/prefill.cpp:1970-1986,6322-6326,6851-6859,7361-7373`）。

## 値と判定

CUDA kernel ファイル内の `w2_on()` が `std::getenv("STRATA_PF_WMMA2")` を読み、値が存在し、かつ先頭文字が `'1'` なら true とします。文字列全体の parse や数値変換はしません。空文字は設定済みでも false、`1` と `1anything` は true、`10` も先頭が `1` なので true です。`0`、`true`、` 1`（先頭が空白）、未設定は false です。大文字小文字や後続文字は判定に影響しません（`engine/src/kernels/cuda/iq_kernels.cu:7915-7918`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `w2_on()` が評価される CUDA 実装 | false | `1`, `1anything` | 空文字、`0`, `true`, ` 1` |
| HIP / Metal / その他の非 CUDA 実装 | この変数を読む専用 kernel 経路なし | 該当なし | 該当なし |

`w2_on()` の結果は関数内 `static const bool` に保存され、初回評価後はプロセス内で再読込されません。実行中に環境を書き換えても反映されません。専用 kernel のこの判定について CLI 引数による上書きはありません（`engine/src/kernels/cuda/iq_kernels.cu:7915-7918`）。

## 有効になる条件

- CUDA 版の `gemm_iq_f16_grouped()` が呼ばれること。同関数の kernel 定義は `!__HIPCC__` 側にあり、非 CUDA build の同名 stub は常に `false` を返します（`engine/src/kernels/cuda/iq_kernels.cu:7572-7578,7975-7981`）。
- prompt 側では `wmma_l` 経路であること。これは `use_mmq && pf_wmma() && !fused_l`、peer 実行なら P2P・compact buffer・Hadamard fold なし、native layout、down 型が Q2_0 (42) または IQ4_NL (20)、tail なし、gate/up の IQ row bytes が有効、という条件です。`pf_wmma()` は別変数 `STRATA_PF_WMMA` の先頭文字が `'1'` で、CUDA device が 1 台以上あり、可視 CUDA device がすべて compute capability major 7 以上の場合に有効です（`engine/src/prefill/prefill.cpp:1970-1986,6322-6326`）。
- `gemm_iq_f16_grouped()` 内で、device の取得と compute capability 判定に成功し、major が 7 以上であること。失敗時は `false` を返します（`engine/src/kernels/cuda/iq_kernels.cu:7923-7929`）。
- 専用経路では、出力行数 `n_out` が 128 の倍数、`ldx` と `ldy` が 8 の倍数、`X` が 16 byte、`Y` が 32 byte、`W` と `expert_bytes` が 4 byte 境界に整列し、型と `K` の組合せが IQ2_S (type 22) かつ `K % 512 == 0`、または IQ4_NL (type 20) かつ `K % 128 == 0` であることが必要です。さらに `iq_row_bytes(ty,K) % 4 == 0`、`n_experts * ceil(max_rows/64) <= 65535` が必要です（`engine/src/kernels/cuda/iq_kernels.cu:7930-7942`）。
- prompt の gate/up 呼び出しと down 呼び出しはそれぞれ実際の weight type を渡します。専用 kernel の分岐が受けるのは上記の type 22 と 20 です（`engine/src/prefill/prefill.cpp:6853-6859,7363-7372`; `engine/src/kernels/cuda/iq_kernels.cu:7938-7941`）。

## 実行時の詳細

`wmma_l` 経路では、gate/up の入力を FP16 に gather して `gemm_iq_f16_grouped()` を呼び、出力に SwiGLU を適用して FP16 にし、続いて down projection を同関数で計算します（`engine/src/prefill/prefill.cpp:6851-6859,7361-7373`）。関数内で専用条件が成立すれば IQ2_S または IQ4_NL の `gemm_iq_f16_w2_kernel` を起動し、直後の `cudaGetLastError()` が成功なら `true` を返します（`engine/src/kernels/cuda/iq_kernels.cu:7800-7812,7930-7943`）。

専用条件が成立しない場合は、同関数内の既存 grouped WMMA kernel の型・K 判定へ進みます。そこも受け付けない場合は `false` です（`engine/src/kernels/cuda/iq_kernels.cu:7944-7974`）。専用 kernel の launch error では `false` を返し、内部で別 kernel を再試行しません。prompt 呼び出し元は gate/up または down のどちらかが false なら処理を失敗させます。peer path では `prefill: the peer WMMA expert tiles could not launch`、通常 path では `prefill: the WMMA expert tiles could not launch` をエラー文字列に設定して `false` を返します（`engine/src/prefill/prefill.cpp:6857-6864,7370-7374`）。

## ログと測定値

`w2_on()` と `gemm_iq_f16_grouped()` の専用分岐自体には有効化ログや条件不成立の警告はありません。prompt 呼び出し元で kernel launch 等が失敗した場合は、上記のエラー文字列が設定されます（`engine/src/kernels/cuda/iq_kernels.cu:7915-7918,7930-7943`; `engine/src/prefill/prefill.cpp:6860-6864,7373-7374`）。

`docs/NVIDIA_V100.md:134` は V100 で `STRATA_PF_WMMA2=1` の prompt が `+2.5-4.3%` と記載しますが、その表の行にはモデル、量子化、prompt 条件、比較対象、測定方法がありません。この調査ではソースから性能値を確認できないため、一般化できる性能値としては扱いません。

`docs/SETTINGS.md:231` は適用 GPU を “NVIDIA and AMD” としていますが、現行の環境変数読み取りと `gemm_iq_f16_grouped()` 実装は CUDA 側にあります。したがってこの変数について AMD/HIP 動作を裏付ける実装は確認できません（`engine/src/kernels/cuda/iq_kernels.cu:7575-7578,7915-7918,7975-7981`）。

## 根拠

- 値の読み取り・static cache: `engine/src/kernels/cuda/iq_kernels.cu:7915-7918`
- 専用 kernel、適用条件、既存経路への継続: `engine/src/kernels/cuda/iq_kernels.cu:7800-7812,7921-7974`
- CUDA 以外の stub: `engine/src/kernels/cuda/iq_kernels.cu:7975-7981`
- `STRATA_PF_WMMA` の判定、prompt 側の使用条件と効果: `engine/src/prefill/prefill.cpp:1970-1986,6322-6329,6851-6864,7361-7374`
- 関連する Strata 資料: `docs/SETTINGS.md:231`, `docs/NVIDIA_V100.md:74,134`
