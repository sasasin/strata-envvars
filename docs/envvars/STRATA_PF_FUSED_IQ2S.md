# `STRATA_PF_FUSED_IQ2S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の HIP gfx12 で既定有効になっている、ネイティブ fused prompt kernel の IQ3_S pack 内 IQ2_S / IQ4_XS gate/up 層を既定経路から外すスイッチです。値が `0` で始まると既定の fused 経路を拒否し、それ以外の値で既定経路を有効にします。これは IQ2_S / IQ4_XS を個別に opt-in する変数ではありません。判定は `gfx12_iq2s_default()` と `native_supported()` にあります（`engine/src/prefill/moe_fused_iq.cu:3389-3398,3562-3587`）。

fused 経路が選ばれると、Strata の HIP `native_w11_kernel` が gate/up と down を計算します（`engine/src/prefill/moe_fused_iq.cu:3810-3827,3845-3849`）。prompt の MMQ に必要な tile がない層で `native_supported()` が偽なら、呼び出し側は fused 層を選ばず、FP16 経路へ fallback します（`engine/src/prefill/prefill.cpp:2062-2071`）。ソースコメントは fused と MMQ で出力が同一バイト列ではないと記しています（`engine/src/prefill/moe_fused_iq.cu:3562-3567`）。

## 値と判定

値は `std::getenv` で取得し、文字列全体の parse ではなく先頭文字だけを `\0`（文字 `'0'`）と比較します。大文字小文字、空白、数値としての妥当性は検査しません。空文字はポインターが非 null でも先頭文字が `'0'` ではないため、この変数単独の判定では既定を止めません（`engine/src/prefill/moe_fused_iq.cu:3389-3397`）。

| 条件 | 未設定 | 変数の値 | 判定 |
|---|---|---|---|
| HIP、Linux、gfx12、`STRATA_PF_FUSED` が未設定または空 | 既定 ON | `0`, `0anything`, `00` など | 先頭が `0` なら既定を OFF |
| 同上 | 既定 ON | 空文字、`1`, `true`, `false`, `anything`, ` 0` など | 先頭が `0` でなければ既定 ON |
| HIP、Windows gfx12 | 既定 OFF | どの値でも | この変数だけでは ON にならない。明示的な `STRATA_PF_FUSED=1` が fused 経路を opt-in する |
| CUDA | この変数による既定変更なし | どの値でも | 現行の `native_supported()` は CUDA の既定判定で先に return するか、明示 opt-in 経路に進むため、この個別判定に到達しない |

`STRATA_PF_FUSED` は別途 `native_supported()` で読み取られます。未設定または空文字なら既定判定に進みます。先頭が `1` でない非空値は fused native kernels を全体的に止め、先頭が `1` の値は明示 opt-in となります（`engine/src/prefill/moe_fused_iq.cu:3425-3432`）。明示 opt-in の `STRATA_PF_FUSED=1` では IQ2S 個別判定を通らないため、`STRATA_PF_FUSED_IQ2S=0` でもその opt-in は取り消されません。これは `native_supported()` の分岐順に基づく実装上の挙動です（同 `:3517-3533,3562-3587`）。

## 有効になる条件

- 既定動作を変えるのは HIP build の gfx12 device です。Linux では `kGfx12PromptDefaultsOn` が true、Windows では false です（`engine/src/prefill/moe_fused_iq.cu:3389-3397`; `engine/include/strata/core/gfx12_platform_defaults.hpp:10-16`）。
- `STRATA_PF_FUSED` が未設定または空であるときに、この変数の `0` 先頭判定が使われます。`STRATA_PF_FUSED=0` は先に native fused 経路を無効にします。`STRATA_PF_FUSED=1` は opt-in となり、この変数の判定を飛ばします（`engine/src/prefill/moe_fused_iq.cu:3425-3432,3562-3587`）。
- モデル層の gate/up type が IQ2_S または IQ4_XS であり、現在の device で native kernels と down type が対応している必要があります。通常の gfx12 対象 down type は Q2_0 / IQ4_NL です。gfx12 の Q8_0 down は別の `STRATA_PF_FUSED_Q8D=1` を含む対応条件を満たす必要があります（同 `:3562-3581`; `engine/src/prefill/moe_fused_iq.cu:3206-3216`）。
- `STRATA_PF_FUSED_NATIVE=0` または process 内の `pf_fused_override()==0` でも `native_supported()` は false になります（同 `:3416-3432`）。この変数には CLI 引数を直接読む処理はありません。
- CUDA ではこの個別スイッチの判定に到達しません。CUDA は unset/empty のとき CUDA 専用の `fused_tile::default_takes_env` を評価して return し、明示 opt-in の場合も後段の `env < 0` 条件を通らないためです（同 `:3517-3533,3562-3587`）。

## 実行時の詳細

`gfx12_iq2s_default()` 内の `static const bool on` 初期化で、対象変数と `STRATA_PF_FUSED` を最初にこの関数が呼ばれたとき一度だけ読みます。そのため、初回判定後にプロセス環境を変えても反映されません。親変数 `STRATA_PF_FUSED` 自体も `native_supported()` 内の `static const int env_set` で初回に cache されます（`engine/src/prefill/moe_fused_iq.cu:3389-3397,3425-3428`）。

この関数は prompt prefill の layer ごとの native fused 対応判定から呼ばれます。設定により IQ2_S / IQ4_XS 層が fused 対応と判定されない場合、MMQ がその層に使えなければ呼び出し側は FP16 GEMM fallback を選択します（`engine/src/prefill/prefill.cpp:2062-2071`）。サーバーモード専用の読み取りや子プロセスへの転送はありません。

## ログと測定値

この変数の値を表示する専用ログや警告はありません。ソースコメントには R9700、IQ3_S pack、`serve`、3 interleaved pairs での prompt 2K / 8K / 32K がそれぞれ +9.7% / +12.2% / +8.8%、MMQ を基準とした first-token KL が 1,025 token の 29 prompts で 0.017（top-1 は 29 中 28）と記録されています。これは実装コメントの記載値であり、この調査で再測定した値ではありません（`engine/src/prefill/moe_fused_iq.cu:3562-3565`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:3389-3398` — 変数の読み取り、先頭文字判定、既定値、static cache。
- `engine/include/strata/core/gfx12_platform_defaults.hpp:10-16` — Linux / Windows の gfx12 prompt default。
- `engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3533,3562-3587` — 親変数との優先関係、CUDA/HIP 分岐、device / layer 判定。
- `engine/src/prefill/moe_fused_iq.cu:3810-3827,3845-3849` — native gate/up・down kernel dispatch。
- `engine/src/prefill/prefill.cpp:2062-2071` — 非対応層の fallback 選択。
