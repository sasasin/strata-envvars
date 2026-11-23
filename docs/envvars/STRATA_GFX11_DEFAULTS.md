# `STRATA_GFX11_DEFAULTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

RDNA3 の discrete gfx11 系で Strata が選ぶ一連の既定動作を停止するスイッチです。中心となる実装 `gfx11_defaults_disabled(defaults026)` は、呼び出し側が `defaults026=true` を渡すと常に停止扱いにし、それ以外ではこの変数の先頭文字が `0` の場合に停止扱いにします。通常の arch-default 経路は `qwen_defaults_026()` の値を渡します（`engine/include/strata/core/gfx11_extra.hpp:27-31,83-85`; `engine/include/strata/core/defaults_026.hpp:26-29`）。一部の個別経路は `false` を渡すか、直接この環境変数を読みます。

起動時には gfx1100 / gfx1101 / gfx1102 向けの bitwise-exact 既定値、matrix-core prompt/MoE 既定値、batch slot が 2 以上のときの並列既定値を適用しないようにします。適用対象は `apply_arch_defaults()` 内の `!integrated` 経路です。変数が止めるのは Strata 側の既定選択であり、利用者が個別に設定した機能変数を一律に消去するものではありません（`engine/include/strata/core/gfx11_extra.hpp:41-73,90-109,116-133`; `engine/src/core/arch_defaults.cpp:302-358`）。

同じ停止判定は CPU prefill share、bare `--prefill auto` の chunk 上限、PCIe 自動調整、Q8/WMMA 系の一部にも使われます。対象機能は backend とデバイス条件に依存し、全 Strata 実行経路で同じ意味の包括的な無効化スイッチではありません（`engine/src/prefill/prefill.cpp:3842-3864`; `engine/src/program/generate.cpp:2888-2903,4532-4587`; `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-749`; `engine/src/kernels/cuda/dflash2.cu:542-560`; `engine/src/prefill/moe_fused_iq.cu:3095-3132`）。

## 値と判定

`std::getenv()` の結果について、未設定なら停止しません。設定されていて先頭文字が ASCII `0` なら停止します。それ以外の値は停止させません。文字列全体の比較、数値変換、空白除去、大文字小文字変換はありません（`engine/include/strata/core/gfx11_extra.hpp:27-31`）。

| 条件 | unset | 停止になる値の例 | 停止にならない値の例 |
|---|---|---|---|
| `STRATA_DEFAULTS=026` が無効 | gfx11 既定値を有効にする側 | `0`, `0anything`, `00` など先頭が `0` の文字列 | 空文字、`1`, `false`, `off`, ` 0`, `anything` |
| 呼び出し元が `defaults026=true` を渡す | gfx11 既定値を停止 | 値にかかわらず停止 | なし |

したがって `0anything` は停止、`false` と先頭に空白のある ` 0` は停止になりません。空文字は設定済みですが、先頭文字が `0` ではないため停止になりません。通常の arch-default 経路で参照する `STRATA_DEFAULTS` は `qwen_defaults_026()` がプロセス内で一度だけ読み取って cache し、値全体を `026` / `0.2.6` / `v0.2.6` と比較します（`engine/include/strata/core/defaults_026.hpp:21-29`）。

個別経路には例外があります。たとえば `STRATA_PF_FUSED_Q50` の非空値は先に判定され、先頭が `1` なら gfx11 master switch が `0` でもその経路を有効にします。一方、Q8 down の `q8d_f16_default()` は gfx11 master switch を先に調べて false を返すため、同関数の `STRATA_PF_Q8D_F16=1` より master switch が優先します（`engine/src/prefill/moe_fused_iq.cu:3095-3107,3118-3132`）。

## 有効になる条件

- **起動時の既定値投入:** HIP 実行経路で GPU の情報を取得でき、対象が discrete gfx1100 / gfx1101 / gfx1102 のときに exact と WMMA 既定値を候補にします。parallel 既定値は加えて `batch_slots >= 2` が必要です。`apply_arch_defaults()` は設定済みの個別スイッチを `getenv(...) != nullptr` で保護するため、値が空文字や `0` でも上書きしません（`engine/src/program/generate.cpp:4282-4315`; `engine/src/core/arch_defaults.cpp:302-358`）。
- **`STRATA_DEFAULTS=026`:** `gfx11_defaults_disabled()` に `true` が渡る経路では無条件で停止扱いです。通常の起動時適用では `qwen_defaults_026()` の結果が渡されます（`engine/include/strata/core/gfx11_extra.hpp:27-36,83-85`; `engine/include/strata/core/defaults_026.hpp:26-29`）。
- **CPU prefill share:** HIP build で `STRATA_USE_HIP` が定義され、既定 share を選ぶ段階に到達し、single-GPU discrete gfx11 である必要があります。明示的な `STRATA_PREFILL_CPU_SHARE` があると既定選択に入りません（`engine/src/prefill/prefill.cpp:3842-3864`; `engine/include/strata/core/gfx11_extra.hpp:139-146`）。
- **prefill chunk 上限:** HIP build の bare `--prefill auto` が対象です。Linux では discrete RDNA3 で master switch が停止扱いでなく、chunk ceiling が正の場合に上限を上げます。Windows では `STRATA_GFX11_CHUNK` が空でなく先頭が `0` でもないことが追加で必要です（`engine/src/program/generate.cpp:4532-4587`）。
- **PCIe 自動調整:** HIP build の gfx11 discrete 分岐で参照されます。`STRATA_PCIE_FRAC_DEFAULT` が未設定または空なら master switch による停止判定が効きます。明示値がある場合はこの停止早期 return を通らず、`pcie_auto_hip_default()` が値を判定します。実際の利用は `--pcie-frac`、split、resident expert などの条件にも依存します（`engine/src/program/generate.cpp:2890-2904,5507-5550`）。
- **Q8/WMMA 系:** HIP の gfx11 向け EXP8 と Q8 down、HIPBLASLt packaged tuning table、gfx11 WMMA の DFlash2 attention で個別に参照されます。それぞれに明示設定やアーキテクチャ例外があります。特に packaged tuning table は `arch != "gfx1151"` のときだけ `g11_auto` を gate に使うため、gfx1151 ではこの変数単独で同 table を止めません。`STRATA_DFLASH_WMMA` が非空で先頭が `0` 以外なら、DFlash2 の既定判定を上書きします（`engine/src/prefill/gemm.cu:344-355`; `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-749`; `engine/src/prefill/moe_fused_iq.cu:3095-3132`; `engine/src/kernels/cuda/dflash2.cu:542-560`）。
- CUDA build では gfx11 系の起動時既定投入ブロックは呼び出し側の HIP build guard 内にあります。DFlash2 のこの変数参照も AMD HIP 用の条件付き実装です（`engine/src/program/generate.cpp:4282-4283`; `engine/src/kernels/cuda/dflash2.cu:542-562`）。

## 実行時の詳細

通常の `strata` 起動では GPU 情報を取得した後、engine の機能スイッチが初回参照される前に `apply_arch_defaults()` が呼ばれます。対象の master switch は `gfx11_defaults_disabled()` が呼ばれるたびに環境から読み直され、関数内 static cache には保存しません。一方、`STRATA_DEFAULTS` は別の helper で一度だけ cache されます。起動後にプロセス環境を変更した場合、対象変数の後続読み取りには反映され得ますが、すでに投入した既定値や各機能が持つ別の cache を巻き戻すものではありません（`engine/src/program/generate.cpp:4282-4315`; `engine/include/strata/core/gfx11_extra.hpp:27-36`; `engine/include/strata/core/defaults_026.hpp:26-29`; `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`; `engine/src/kernels/cuda/dflash2.cu:542-560`）。

既定値投入時、Strata は各個別変数が未設定の場合だけ `set_default()` で値を設定します。Windows は `_putenv_s`、他の OS は `setenv(..., 0)` を使います。どれか一つ以上を設定したグループでは、そのグループ名を列挙する stderr 行が出ます。master switch でグループが空になる場合や、全スイッチが利用者設定済みの場合はそのグループ行は出ません（`engine/src/core/arch_defaults.cpp:218-224,318-357`）。

## ログと測定値

既定値が投入されたグループごとに、次の format string の stderr 行が出ます（`%zu` / `%d` と名前一覧は投入された値に応じて展開されます）。

- `strata: gfx11 (RDNA3): %zu exact speed switches on by default (STRATA_GFX11_DEFAULTS=0 turns them off; a switch you set is kept): `
- `strata: gfx11 (RDNA3): %zu matrix-core prompt & MoE switches on by default (STRATA_GFX11_WMMA_DEFAULTS=0 or STRATA_GFX11_DEFAULTS=0 turns them off; NAME=0 turns one off): `
- `strata: gfx11 (RDNA3): exact parallel-request switches on for %d batch slots (STRATA_GFX11_DEFAULTS=0 turns them off; a switch you set is kept): `

文字列と出力条件は `engine/src/core/arch_defaults.cpp:325-357` にあります。prefill 既定 share が選ばれる場合は `prefill: the CPU share is ON by default for prompt chunks up to %lld tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly: first-token KL ~0.01-0.02 below 3K tokens). STRATA_PREFILL_CPU_SHARE=0 or STRATA_GFX11_DEFAULTS=0 turns it off, STRATA_PREFILL_CPU_SHARE_MAX=1024 keeps a 1,024 limit.` の stderr 行が出ます（`engine/src/prefill/prefill.cpp:3855-3862`）。

この文書では Strata のコメントにある個別機種・モデルの性能値を、変数全体の効果として一般化しません。測定値は機能単位の条件に結びついており、ここで扱う master switch 自体の比較測定ではありません。

## 根拠

- 判定と既定値グループ: `engine/include/strata/core/gfx11_extra.hpp:27-36,41-73,90-109,116-143`
- 起動時適用、個別値の保持、ログ: `engine/src/core/arch_defaults.cpp:218-224,302-358`; 呼び出し位置 `engine/src/program/generate.cpp:4282-4315`
- 既定 switch の cache: `engine/include/strata/core/defaults_026.hpp:21-29`
- CPU prefill share: `engine/src/prefill/prefill.cpp:3842-3864`
- bare `--prefill auto` chunk 上限: `engine/src/program/generate.cpp:4532-4587`
- PCIe 自動調整 gate: `engine/src/program/generate.cpp:2888-2904,5507-5550`
- HIPBLASLt tuning table: `engine/src/prefill/gemm.cu:344-355`
- Q8 down / Q50: `engine/src/prefill/moe_fused_iq.cu:3095-3132`
- HIP EXP8: `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-749`
- DFlash2 WMMA: `engine/src/kernels/cuda/dflash2.cu:542-562,1699`
