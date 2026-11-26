# `STRATA_PF_Q8D_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の gfx1151（Strix Halo）および discrete gfx11 で、MoE 層の down projection が Q8_0 の場合に、native fused prompt path の F16 matrix-core kernel を既定で選ぶかを制御する。unset では既定 ON、値の先頭文字が `0` ならこの既定選択を OFF にする。対象は Q8_0 down のみで、gate/up や他形式の選択は変えない。F16 kernel は int8 kernel と出力が異なるとソースコメントに記載されている。CUDA build と gfx12 build ではこの変数を実行時に読まない。実装は `engine/src/prefill/moe_fused_iq.cu` の `q8d_f16_default()` と `experts_native()` にある。(`engine/src/prefill/moe_fused_iq.cu:3088-3107,3781-3787,3830-3835`)

## 値と判定

HIP build で `q8d_f16_default()` が GPU 条件と gfx11 defaults の判定を通過した後の初回に `getenv` し、`v != nullptr && v[0] == '0'` の結果を関数内 `static` に保持する。したがって未設定は OFF 指定ではなく既定 ON、空文字は OFF 指定ではない。`0`, `0anything`, `00` は OFF 指定、`1`, `true`, `false`, `anything`, 空文字は OFF 指定ではない。数値変換、文字列全体の比較、空白除去、大文字小文字変換はしない。CUDA build ではこの関数は常に false を返し、環境変数を読まない。(`engine/src/prefill/moe_fused_iq.cu:3095-3107`)

| 条件 | unset | OFF 指定 | OFF 指定でない例 |
|---|---|---|---|
| HIP の gfx1151（`d.g1151`） | 既定 ON | 先頭が `0` なら既定選択を OFF | 空文字、`1`、`true`、`0anything` 以外の文字列は既定 ON |
| HIP の discrete gfx11（`d.g11`）かつ `STRATA_GFX11_DEFAULTS` が `0` でない | 既定 ON | 先頭が `0` なら既定選択を OFF | 上記と同じ |
| HIP の discrete gfx11 かつ `STRATA_GFX11_DEFAULTS` の先頭が `0` | 既定 OFF | 既定 OFF | 既定 OFF |
| HIP gfx12、HIP の他の GPU、CUDA build | この変数による既定選択なし | この変数は使われない | この変数は使われない |

gfx1151 と discrete gfx11 の区別は `dev_info()` が GPU arch を `g1151` / `g11` に分けることによる。`STRATA_GFX11_DEFAULTS` の確認は `d.g11` の場合だけなので、ここでの gfx1151 判定には影響しない。`STRATA_PF_F16=1` または `2` が有効なら通常の F16 経路が優先され、この変数の Q8_0 既定判定は選択に使われない。(`engine/src/prefill/moe_fused_iq.cu:2847-2885,3095-3107,3781-3787`; `engine/src/prefill/moe_f16_common.cuh:55-61`)

## 有効になる条件

- HIP build であり、実行中 device が gfx1151 または discrete gfx11 で、native kernel がその build の GPU code object に存在して `dev_info().ok` になること。`dev_info()` は architecture と kernel attributes / occupancy を調べ、条件を満たさない場合は native path を利用可能にしない。(`engine/src/prefill/moe_fused_iq.cu:2813-2818,2847-2885`; `engine/src/prefill/moe_f16_common.cuh:38-43`)
- 層の down format が Q8_0 であること。native fused path の layer format 判定が `d_covered_on()` を通り、実行時は `f16_q8d` の条件で Q8_0 down に F16 kernel を選ぶ。(`engine/src/prefill/moe_fused_iq.cu:3204-3219,3781-3787,3830-3835`)
- native fused prompt path 自体が有効であること。`native_supported()` は `STRATA_PF_FUSED=0` または `STRATA_PF_FUSED_NATIVE=0` 等で false になり得る。gfx11 では通常 `STRATA_PF_FUSED=1`（または同等の small-card override）が必要で、override が 0 の場合は false。対象変数を unset にしても native path を単独で有効化しない。(`engine/src/prefill/moe_fused_iq.cu:3415-3432,3572-3586`; `engine/src/prefill/moe_fused.cu:723-729`)
- `STRATA_PF_F16=1` または `2` が F16 kernels を要求しているとき、この変数が制御する既定 Q8_0 経路ではなく F16 switch 側の経路が先に使われる。逆に `STRATA_PF_F16` が未設定または `1` / `2` 以外の場合、gfx11 では `q8d_f16_default()` が true なら Q8_0 down のみを F16 kernel に含める。(`engine/src/prefill/moe_f16_common.cuh:55-61`; `engine/src/prefill/moe_fused_iq.cu:3095-3107,3781-3787`)
- `STRATA_GFX11_DEFAULTS` の先頭が `0` なら discrete gfx11 (`d.g11`) の既定 F16 Q8_0 down は抑止される。gfx1151 (`d.g1151`) ではこの追加判定を行わない。(`engine/src/prefill/moe_fused_iq.cu:3095-3103`)
- prompt path からの down 出力を FP16 にするかは別条件 `STRATA_PF_DM16` による `g_dm16_want` が決める。この変数だけで `dm` の出力形式は決まらない。(`engine/src/prefill/moe_fused_iq.cu:3596-3601,3786-3788`)

## 実行時の詳細

`native_supported()` が layer の down type を確認する際、HIP の非 gfx12 で Q8_0 なら `f16::requested()` または `q8d_f16_default(d)` を使って down type をカバーできるか判定する。`q8d_f16_default()` は GPU が gfx1151 / gfx11 でなければ false、gfx11 では `STRATA_GFX11_DEFAULTS` の先頭 `0` でも false を返す。その後 static cache の `STRATA_PF_Q8D_F16` 判定により既定値を決める。(`engine/src/prefill/moe_fused_iq.cu:3095-3107,3204-3209`)

実際の `experts_native()` では、`f16 = !d.w12 && f16::requested()` が false で、down type が Q8_0、かつ `q8d_f16_default(d)` が true のときだけ `f16_q8d` が true になる。これにより gate/up は既存の対応 kernel、Q8_0 down は `native_f16_kernel<T_Q8_0, false>` を使う。条件を満たさなければ、対応する native int8 kernel または fused native path 外の既存経路を選ぶ。コメントは gfx1151 の Q8_0 down 層を F16 matrix-core kernel に移すと、その層以外は従来の bit のままとし、対象層の出力は int8 kernel と異なると説明している。(`engine/src/prefill/moe_fused_iq.cu:3088-3094,3781-3787,3830-3835`; `engine/src/prefill/prefill.cpp:402-404,777-806`)

環境変数の値は、GPU 条件と gfx11 defaults の判定を通過した `q8d_f16_default()` の初回呼び出し時に一度だけ読み static cache される。プロセス実行中に環境を変えても、この判定には反映されない。GPU とモデル layer の適用判定は `native_supported()` から行われるが、対象変数の読み取り値は関数内 static でプロセス共有である。(`engine/src/prefill/moe_fused_iq.cu:3095-3107,3415-3432`)

## ログと測定値

`STRATA_PF_Q8D_F16` の値を表示する専用ログ、無効値警告、または専用エラー分岐は確認できない。環境値が `0` 以外かを検証せず、F16 の既定選択を有効のままにする。native path が実行される際には kernel launch 後に `ck(cudaGetLastError(), "experts_native")` が呼ばれるが、これは本変数に固有のログではない。(`engine/src/prefill/moe_fused_iq.cu:3095-3107,3852-3853`)

ソースコメントには Windows gfx1151、eng034 で `STRATA_PF_F16=1` とした A/B（`phaseA-tests/strix-u`）として、4K / 8K prompt の値が本既定経路ありで 1,192 / 1,257 tok/s、なしで 1,057 / 1,128 tok/s と記録されている。コメントは測定回数や詳細な測定手順を示していないため、この条件の記録としてのみ扱う。(`engine/src/prefill/moe_fused_iq.cu:3091-3094`)

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:3091-3107` — gfx1151 / gfx11 の既定条件、`STRATA_GFX11_DEFAULTS` と対象変数の読み取り。
- `engine/src/prefill/moe_fused_iq.cu:3204-3209,3415-3432,3572-3586` — down format coverage、native path 有効条件。
- `engine/src/prefill/moe_fused_iq.cu:3781-3788,3830-3853` — F16 kernel の選択と launch 後の確認。
- `engine/src/prefill/moe_f16_common.cuh:38-61` — 対象 GPU build と `STRATA_PF_F16` の判定。
- `engine/src/prefill/moe_fused.cu:723-729` — `STRATA_PF_FUSED` と native fused path の要求判定。
- `engine/src/prefill/prefill.cpp:777-806` — model layer ごとの native support に基づく fused layout 判定。
