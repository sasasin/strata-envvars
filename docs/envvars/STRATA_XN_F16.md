# `STRATA_XN_F16`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

prompt prefill の hyper-connection が作る `xn16` の画像を、通常の BF16 から「BF16 値を FP16 に変換した値」へ切り替える。CUDA の BF16 重み GEMM が入力 X を BF16 から FP16 へ変換して tensor core に渡す経路では、hyper-connection の正規化カーネルがあらかじめその変換後の FP16 値を書き、down / inject の GEMM で同じ入力変換を省ける。

## 値と判定

| 環境変数の状態 | `xn_env` |
| --- | --- |
| 未設定 | 有効（`true`） |
| 空文字 | 有効（先頭文字が `'0'` ではない） |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| その他の文字列 | 有効（例: `1`, `false`, `abc`） |

整数変換や文字列全体の比較は行わず、先頭 1 文字が ASCII の `0` かだけを調べる。大文字小文字の扱いはない。

## 有効になる条件

読み取った値が有効でも、実際に FP16 画像を使う条件は `xn_env && !m.f16_io && m.gemm.bf16_converts_x()`。また実行時には、`m.xn_f16 && !m.xn16_lo && ldx == D` が `xf16` 条件になる。したがって、FP16 入出力の prompt 経路、BF16 X を FP16 に変換しない GEMM 経路、BF16x2 の下位画像が存在する場合、または hyper-connection の行 stride が `D` でない場合はこの設定で FP16 画像に切り替わらない。

`bf16_converts_x()` は HIP と `STRATA_EXPERIMENTAL_SM60` ビルドでは常に false。通常の CUDA では `STRATA_BF16_TC` 等で決まる BF16 GEMM の経路が FP16 tensor-core 経路（`bf16_path() == 1`）のとき true となる。標準設定では compute capability 7.0–7.4 がその経路、7.5 は BF16 cuBLAS 経路であり、7.5 で FP16 経路を選ぶには `STRATA_BF16_TC=1` などが必要。`STRATA_BF16_TC` の強制値 `2` は既知の CUDA device でテスト用に FP16 経路を選ぶ。これらは別変数側の条件である。

## 実行時の詳細

値は prefill stage の GEMM 初期化時に関数内 `static const` として初回だけ評価・保持されるため、同一プロセスで後から環境を変更しても再評価されない。unset と空文字を含む「先頭文字が `0` でない」値が既定の有効状態。

有効条件を満たすと、hyper-connection の正規化カーネルが BF16 値 `h` を FP16 へ丸め、有限値の範囲外は ±65504 に飽和させて `xn16` に書く。down / inject の `bf16_proj` は `x_f16=true` を GEMM に渡し、FP16 tensor-core GEMM が同じ変換を繰り返さず、この画像を直接読む。GEMM が FP16 tensor-core 経路を取らないケース（たとえば出力行が1行、または scratch 不足時の fallback）では、GEMM 実装がこの入力を一時的に BF16 へ戻してから処理する。`STRATA_XN_F16=0` は変換前の BF16 画像を保持し、GEMM 側で通常どおり入力を変換する。

この変数固有のログ出力やエラー出力は確認できなかった。`docs/DETAILS.md` は `STRATA_BF16_TC` と `STRATA_XN_F16` を #2091 の項目に併記するが、具体的な性能測定値や条件はこの記述からは確認できない。

## 根拠

- `src/prefill/prefill.cpp:876` — `xn_f16` の状態。
- `src/prefill/prefill.cpp:1382-1393` — stage device 上の初期化、`STRATA_XN_F16` の読み取りと条件。
- `src/prefill/prefill.cpp:2951-2956,2973,3003` — stride / low-part 条件、画像書き込みと GEMM 呼び出し。
- `src/prefill/gemm.cu:657-668,714-725,910-915` — CUDA BF16 経路と `bf16_converts_x()` の適用範囲。
- `src/prefill/gemm.cu:1008-1017,1025-1035` — FP16 tensor-core 経路での入力変換省略と fallback 時の BF16 変換。
- `src/prefill/kernels.cu:70-76,127-144,2373-2382` — FP16 画像への変換・飽和と正規化カーネルへのフラグ伝播。
- `include/strata/prefill/gemm.hpp:35-43` — GEMM 入力画像の契約。
- `docs/DETAILS.md:2259-2261` — 関連設定の資料上の記載。
