# `STRATA_PF_FUSED_Q50`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MoE prompt prefill の Q5_0 down projection を、対応 GPU で Strata の fused native kernel に載せる opt-in / platform default スイッチ。CUDA は Q5_0 down kernel を device ごとの setup に加え、HIP は gfx12 で int8 native kernel、gfx11 で F16 matrix-core kernel を選ぶ判定に使う。主な実装は `engine/src/prefill/moe_fused_iq.cu` の `q50_cuda_requested`、`q50_on`、`d_covered_on`、`native_supported`、`dev_info`、`experts_native`。

対象モデルがこの形式を持つ場合でも、値だけで全層が必ず切り替わるわけではない。gate/up の型、GPU・kernel setup、fused prompt 全体の有効状態、backend 固有の条件が揃った Q5_0 down 層だけが対象になる。CUDA の対象層は従来の gather + FP16 dequantize/GEMM 経路から Q5_0 native kernel に移る（同ファイル `2951-2956`, `3500-3505`, `3930-3935`）。HIP gfx12 は native int8 kernel、gfx11 は `STRATA_PF_F16` の F16 kernel を使う（`3112-3116`, `3204-3208`, `3740-3749`）。

環境変数を直接読むのは CUDA と HIP の実装だけ。`STRATA_PF_FUSED_Q50` を読む CLI 引数・設定ファイルの参照は見つからなかった。ビルドに MMQ prompt kernels がない場合は別途起動前の helper が unset 変数を `1` に設定する（`engine/src/prefill/prefill.cpp:223-255`, `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-56`）。

## 値と判定

値は数値や真偽値として parse されず、先頭文字だけで判定される。前後空白の除去、文字列全体の比較、大文字小文字変換はない。

| 経路 | unset | 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|---|
| CUDA (`q50_cuda_requested`) | 無効 | 無効 | 先頭文字が `1`（例: `1`, `1abc`, `10`） | 先頭文字が `1` 以外（例: `0`, `true`, ` 1`） |
| HIP gfx12 / gfx11 (`q50_on`) | backend / OS の既定値 | unset と同じ既定値 | 先頭文字が `1`（例: `1`, `1abc`, `10`） | 空でない値の先頭文字が `1` 以外（例: `0`, `true`, ` 1`） |

CUDA は `getenv` が非 null かつ `v[0] == '1'` のときだけ要求を on とし、`static const bool` に初回評価結果を保存する（`engine/src/prefill/moe_fused_iq.cu:2715-2719`）。HIP は unset または空文字を `-1`（既定値を使う）にし、非空文字列は先頭が `1` のとき `1`、それ以外を `0` として `static const int` に保存する（同 `3118-3122`）。従って、明示的な空文字は CUDA では off、HIP では unset と同じ扱い。

unset / 空文字時の Q50 判定は次のとおり。HIP の既定値は `q50_on` の platform/device 判定に基づく（同 `3123-3133`）。

| Backend / device | unset または空文字 | 既定を無効にする関連変数 |
|---|---|---|
| CUDA | off | 該当なし（明示的に先頭 `1` が必要） |
| HIP gfx12 (RDNA4) | Linux on、Windows off（`kGfx12PromptDefaultsOn`） | 既定値は `STRATA_PF_FUSED_Q50=0` 等の明示値で置換 |
| HIP gfx11 discrete RDNA3 (`d.g11`) | on | `STRATA_GFX11_DEFAULTS` の先頭文字が `0` なら off |
| HIP gfx1151 | Windows on、その他の OS は off | Windows では `STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら off |
| HIP のその他 device | off | 該当なし |

gfx12 の OS 判定は `engine/include/strata/core/gfx12_platform_defaults.hpp:1-15`、gfx11 / gfx1151 の判定は `engine/src/prefill/moe_fused_iq.cu:3123-3133`。`STRATA_GFX11_DEFAULTS` と `STRATA_GFX1151_DEFAULTS` も先頭文字が `0` かだけを見ており、`0abc` も default off にする。

MMQ prompt kernel を含まない `STRATA_PREFILL_FUSED && !STRATA_PREFILL_MMQ` build では、起動時 initializer がこの名前を含む opt-in 一覧を処理し、変数が unset のとき `setenv` / `_putenv_s` で `1` を設定する。ユーザーが空文字を含む値をすでに設定していれば保持する。そのため、この build の unset は各 backend の通常の unset 規則ではなく、実装が補った `1` として読まれる（`engine/src/prefill/prefill.cpp:223-255`; `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-56`）。

## 有効になる条件

- **CUDA:** Compute Capability 8.0 以上で、Q5_0 down kernel の `setup_one<T_Q5_0, false>` が成功すること。`dev_info()` は 8.0 未満を通常の native setup 前に返し、Q5_0 は Turing の setup 対象にも含めない（`engine/src/prefill/moe_fused_iq.cu:2899-2903,2951-2956`）。
- **CUDA:** `STRATA_PF_FUSED=0` または fused prompt override が `0` なら Q50 の要求にかかわらず `native_supported` は false（同 `3415-3432`）。Q50 自体は `STRATA_PF_FUSED=1` を必須にせず、CUDA の Q5_0 専用判定は通常の GPU 世代別 default gate-format 判定より前に行われる（同 `3500-3505,3517-3532`）。
- **HIP gfx12:** device が gfx12 WMMA kernel 対応として認識され、`dev_info().ok` であること。Q5_0 down は `q50_on` を満たす gfx12 native int8 kernel の対象（同 `2858-2885,3204-3208`）。
- **HIP gfx11:** device が gfx1151 または対象の discrete RDNA3 と認識され、`q50_on` に加えて `STRATA_PF_F16` が `1` または `2` であること。gfx11 の Q5_0 down に fused int8 kernel はなく、F16 prompt kernel が必要（同 `3118-3137,3204-3208`; `engine/src/prefill/moe_f16_common.cuh:55-62`）。
- **HIP gfx11:** さらに fused native prompt を有効にする必要がある。通常は `STRATA_PF_FUSED=1`（または small-card prompt の internal override）であり、`STRATA_PF_FUSED` が unset のときの `native_supported` の default return は gfx12 に限られるため、gfx11 では Q50 が on でも対象にならない。MMQ なし build が unset の `STRATA_PF_FUSED` を `1` に補う場合も条件を満たす（`engine/src/prefill/moe_fused_iq.cu:3425-3432,3581-3586`; `engine/src/prefill/moe_fused.cu:723-729`; `engine/src/prefill/prefill.cpp:223-255`）。
- **HIP gfx12:** `STRATA_PF_FUSED=0` は全 fused native 経路を止める。unset 時は Linux の gfx12 default が有効になり得る。Windows では Q50 の既定は off だが、明示的な `STRATA_PF_FUSED_Q50=1` で Q5_0 を要求できる（`engine/src/prefill/moe_fused_iq.cu:3425-3432,3581-3586`; `engine/include/strata/core/gfx12_platform_defaults.hpp:7-15`）。
- モデル側では down 型が Q5_0、gate/up 型が `gu_covered` の対応型で、現在の device の `native_supported` がその pair を受理すること。`gu_covered` の型一覧は同 `3061-3079`、down 判定は同 `3204-3220,3415-3432`。
- CUDA では `STRATA_PF_FUSED_NT=256` または `STRATA_PF_FUSED_F16=1` により NT=256 kernel が有効、または `STRATA_PF_FUSED_WS=1` により warp-specialized kernel が有効な場合、Q5_0 pair はその kernel にないため `native_supported` が拒否する（同 `2783-2789,3500-3505`）。

## 実行時の詳細

CUDA は `q50_cuda_requested()` の初回呼び出し時に環境を static cache する。device 情報と Q5_0 kernel setup 結果は `dev_info()` の device ごとの `DevInfo` に保存され、二度目以降は再 setup しない（`engine/src/prefill/moe_fused_iq.cu:2717-2719,2847-2853,2951-2956`）。実行中に `STRATA_PF_FUSED_Q50` を変更してもこの要求値には反映されない。

HIP は `q50_on()` の初回評価時に Q50 の unset/明示値判定を static cache する。device 情報も `dev_info()` で cache される一方、unset 時に参照する `STRATA_GFX11_DEFAULTS` / `STRATA_GFX1151_DEFAULTS` は該当する `q50_on()` 呼び出し時に読む（同 `3118-3133,2847-2853`）。MMQ なし build の環境補完は static initializer で `main()` より前に行われる（`engine/src/prefill/prefill.cpp:223-255`）。

選択後、CUDA は Q5_0 down 用に個別計算した occupancy を使って `launch<T_Q5_0, false>` を呼び、他形式の occupancy とは分ける（`engine/src/prefill/moe_fused_iq.cu:2951-2956,3930-3935`）。HIP gfx12 は native WMMA kernel、gfx11 は `f16 && f16_d(g.d_type)` の条件で F16 kernel の Q5_0 down dispatch に進む（同 `3830-3849`）。対象外の層・device では Q50 kernel へは進まず、通常の対象形式経路（MMQ が使える構成なら MMQ、該当コメントが示す Q5_0 down 経路では gather + FP16 dequantize/GEMM）に残る（同 `2951-2955,3112-3116`）。

## ログと測定値

Q50 が unset / off、または CUDA Q5_0 setup が成功しなかった場合に限った専用ログは見つからなかった。CUDA の setup 失敗は `d.q50` を立てず、Q5_0 pair の native 対応判定を通さない（`engine/src/prefill/moe_fused_iq.cu:2951-2956,3500-3505`）。選択された kernel launch 後の CUDA/HIP 共通エラーチェックは失敗時に `stderr` へ `prefill fused experts (native): experts_native: <CUDA error>` の形式で出し、`exit(1)` する（同 `68-73,3948-3949`）。

`docs/SETTINGS.md:433` はこの変数を NVIDIA / AMD 共通の `on / off` として一覧化しているが、現行ソースでは CUDA の明示 on 判定、gfx12 の Linux/Windows 差、gfx11 の F16 条件と platform default が異なる。`docs/DETAILS.md` にこの GPU Q50 スイッチの追加説明や測定値は見当たらないため、ここでは性能値を記載しない。

## 根拠

- 読み取り、判定、device defaults: `engine/src/prefill/moe_fused_iq.cu:2715-2719,3118-3137`
- HIP OS default: `engine/include/strata/core/gfx12_platform_defaults.hpp:7-15`
- MMQ なし build による unset 補完: `engine/src/prefill/prefill.cpp:223-255`, `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-56`
- setup、条件、pair 判定、dispatch: `engine/src/prefill/moe_fused_iq.cu:2847-2903,2951-2956,3061-3079,3204-3220,3415-3432,3500-3505,3581-3586,3930-3949`
- F16 kernel 要件と Q5_0 dispatch: `engine/src/prefill/moe_f16_common.cuh:55-62`, `engine/src/prefill/moe_fused_iq.cu:3781-3787,3830-3849`
- 設定一覧との照合: `docs/SETTINGS.md:433`; `docs/DETAILS.md` に対象スイッチの説明なし。
