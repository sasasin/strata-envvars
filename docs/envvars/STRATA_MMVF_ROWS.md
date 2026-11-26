# `STRATA_MMVF_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

BF16 重み・FP32 activation の multi-row MMVF で、出力行を 4 行ずつ 1 block が計算する rows kernel を選ぶ opt-in スイッチです。従来の multi kernel は出力行ごとの block が activation 行を走査しますが、rows kernel は 4 出力行分をまとめ、各 activation の読み込みを共有します。カーネル内では同じ順序の 2 回の FMA と warp / block reduction を使います。対象は CUDA/HIP 実装と SYCL 実装の `bf16_gemv_fp32_mmvf_multi` および router・shared-expert 用の `bf16_gemv_fp32_mmvf_multi_aux` です（`engine/src/kernels/cuda/native_bf16.cu:217-220,223-309,387-435`、`engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:183-201,537-579`）。

## 値と判定

両 backend とも関数内 `static const bool` 初期化時に `std::getenv` を呼び、値が存在し、かつ先頭 byte が文字 `'1'` の場合だけ有効にします。文字列全体の parse、数値検証、空白除去、大文字小文字変換はしません（`engine/src/kernels/cuda/native_bf16.cu:390,420`、`engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:540,589`）。

| 状況 | 有効になる値 | 無効になる値 |
| --- | --- | --- |
| CUDA/HIP または SYCL の rows kernel 選択 | `1`、`10`、`1anything` など先頭 byte が `1` | 未設定、空文字、`0`、`0anything`、`true`、` 1` など |

未設定は通常 `false` です。ただし後述の AMD architecture defaults が適用される起動経路では、未設定の変数に `1` が設定されます。既定値の注入は `getenv(...) != nullptr` で設定有無を見ているため、明示した空文字や `0` もユーザー設定として保持され、rows kernel を無効にします（`engine/src/core/arch_defaults.cpp:307-310,318-323`）。

## 有効になる条件

- 関数が CUDA/HIP または SYCL の BF16-weight / FP32-activation multi-row MMVF 経路に到達する必要があります。単一行は `n_tok == 1 && ldy >= n_out` の早期分岐で単一行関数へ進み、この変数を読む rows 分岐を通りません（CUDA/HIP: `engine/src/kernels/cuda/native_bf16.cu:413-421`、SYCL: `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:582-590`）。
- rows kernel は `n_out >= 64` の場合に選択されます。CUDA/HIP は加えて `n_tok <= 8` を条件にしています。`n_out < 64`、または CUDA/HIP build で `n_tok > 8` のときは通常の multi kernel に進みます。SYCL multi entry は `n_tok` を 1..8 に制限しており、範囲外は `std::invalid_argument` です（CUDA/HIP: `engine/src/kernels/cuda/native_bf16.cu:416-437`、SYCL: `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:585-625`）。
- 代表的な MoE router 呼び出しでは、switch に到達する前に verify window が複数行 (`dec_batch && n > 1`) で、router weight があり、native router が有効で、CUDA/HIP は `NE == 512 && K == 10`、SYCL は `(NE == 512 || NE == 256) && K == 10` という条件があります。これらを満たさない router は別の経路を使います。ほかに PLE / GR projection や shared-expert gate からも同じ multi API が呼ばれます（CUDA/HIP router: `engine/src/core/verify.cpp:2635-2645`、SYCL router: `engine/sycl/src/core/verify.cpp:1581-1592`、GR: `engine/src/kernels/cuda/gr.cu:485-490`、shared expert: `engine/src/kernels/cuda/shared_expert.cu:265`）。
- rows kernel の有効化に必要な `n_in`・stride・pointer の検査は通常 multi 関数の共通入力検証で行われます。不正な形状や null / misaligned pointer は rows switch より先に `std::invalid_argument` になります（CUDA/HIP: `engine/src/kernels/cuda/native_bf16.cu:416-420`、SYCL: `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:585-589`）。
- `multi_aux` はさらに rows 設定、`n_out >= 64`、`2 <= n_tok <= 8`、正の偶数 `n_in`、偶数 `ldx`、全 pointer の存在と `x` の 8-byte alignment を必要とします。条件に合わないと何も launch せず `false` を返し、verify 側は通常の `multi` 呼び出しへ進みます（CUDA/HIP: `engine/src/kernels/cuda/native_bf16.cu:387-410`、SYCL: `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:537-579`、呼び出し元: `engine/src/core/verify.cpp:2635-2645`、`engine/sycl/src/core/verify.cpp:1581-1592`）。
- AMD gfx1151 では `apply_arch_defaults` が起動時にこの変数を `1` に設定します（ユーザーが先に設定していない場合）。`STRATA_GFX1151_DEFAULTS` が存在し先頭 byte が `0` の場合は、この architecture table 自体が無効です（`engine/src/core/arch_defaults.cpp:64-66,79-82,307-310`）。
- 非統合 AMD discrete RDNA3 の gfx1100 / gfx1101 / gfx1102 でも `apply_arch_defaults` が `1` を設定します。`STRATA_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致するか、`STRATA_GFX11_DEFAULTS` が存在して先頭 byte が `0` の場合はこの defaults table は空です（`engine/include/strata/core/gfx11_extra.hpp:27-30,39-59`、`engine/src/core/arch_defaults.cpp:318-323`、`engine/include/strata/core/defaults_026.hpp:21-29`）。
- architecture defaults の適用対象外、または該当する defaults 無効化スイッチが使われる場合、値が未設定なら通常は off です。CUDA build の NVIDIA GPU などではこのコードの gfx1151 / gfx11 条件を満たしません。明示的に設定した値は architecture defaults より優先します。

## 実行時の詳細

CUDA/HIP の `multi` と `multi_aux`、SYCL の同名関数はそれぞれ個別の関数内 `static const bool` で最初に呼ばれた時に値を cache します。したがって各関数の最初の読み取り後に環境を変更しても、その関数の判定には反映されません。2 関数は別々の cache を持ちます（`engine/src/kernels/cuda/native_bf16.cu:387-394,413-421`、`engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:537-544,582-590`）。

rows 分岐では `RPB = 4` とし、`ceil(n_out / 4)` 個の block を起動します。`n_tok <= 4` なら 4 token 列、5..8 なら 8 token 列の kernel specialization を選び、各出力行の結果を `y[k * ldy + output]` に書き込みます（CUDA/HIP: `engine/src/kernels/cuda/native_bf16.cu:223-309,312-333`、SYCL: `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:189-201`）。`STRATA_TSUM` が別途先頭 byte `1` で有効なら rows kernel 内で transposed butterfly warp sum の template も選びます（CUDA/HIP: `engine/src/kernels/cuda/native_bf16.cu:317-333`）。

AMD の自動設定は engine の GPU 起動時に `apply_arch_defaults` が呼ばれた後、kernel が switch を初めて読む前に行われます。CUDA/HIP generate は `engine/src/program/generate.cpp:4320`、SYCL/HIP generate は `engine/sycl/src/program/generate.cpp:2223-2228` で適用します。既存値の有無を見てから環境に設定するため、空文字を含む明示値は上書きされません（`engine/src/core/arch_defaults.cpp:218-224,302-323`）。CLI 引数がこの変数を直接上書きする分岐は見当たりません。

CUDA/HIP では row kernel launch 後の `cudaGetLastError()` が失敗した場合、`bf16_gemv_fp32_mmvf_multi[_aux] launch: <CUDA error>` を含む `std::runtime_error` を送出します（`engine/src/kernels/cuda/native_bf16.cu:407-410,433-435`）。router 呼び出し元は例外を捕捉し `verify router: <error>` として失敗を返します（`engine/src/core/verify.cpp:2636-2646`）。SYCL 側の該当箇所では変換後の launch error result は定数 0 で、実際の非同期実行エラーは SYCL の実行経路に依存します。rows switch 固有のログはありません（`engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:557-579,602-624`）。

## ログと測定値

rows switch を直接報告するログはありません。gfx1151 の defaults が未設定変数を含む switch を設定した場合は `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...`、discrete gfx11 の defaults が設定した場合は `strata: gfx11 (RDNA3): ... exact speed switches on by default ...` という一覧が stderr に出ます。変数がユーザー設定済みなら一覧には含まれません（`engine/src/core/arch_defaults.cpp:307-332,397-405`）。

`docs/DETAILS.md` には本変数固有の説明や測定値は見当たりません。ソースコメントは rows kernel の設計と演算順序を述べていますが、この文書ではそのコメントを独立に測定した性能値として扱いません。

## 根拠

- `engine/src/kernels/cuda/native_bf16.cu:217-333,387-435` — CUDA/HIP rows kernel、条件、cache、launch とエラー処理。
- `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:183-201,537-624` — SYCL rows kernel、条件、cache、fallback。
- `engine/src/core/arch_defaults.cpp:28-106,218-224,302-332` — gfx1151 / gfx11 defaults、ユーザー設定優先、設定ログ。
- `engine/include/strata/core/gfx11_extra.hpp:27-59`、`engine/include/strata/core/defaults_026.hpp:21-29` — discrete gfx11 defaults の無効化条件。
- `engine/src/program/generate.cpp:4320`、`engine/sycl/src/program/generate.cpp:2223-2228` — defaults の適用時点。
- `engine/src/core/verify.cpp:2635-2646`、`engine/sycl/src/core/verify.cpp:1581-1593` — fused auxiliary 呼び出しと例外経路。
