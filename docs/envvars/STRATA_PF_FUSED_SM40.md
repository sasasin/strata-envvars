# `STRATA_PF_FUSED_SM40`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA の fused prompt-expert kernels について、対応する compute capability 8.0 / 8.6 / 8.9 または 12.0 のカードで SM 数が 40〜79 の場合に、既定で一部の層を fused 経路へ回すかを制御するスイッチです。unset と先頭文字が `0` でない値はこの 40〜79 SM ルールを有効にし、先頭文字 `0` は無効にします。したがって `STRATA_PF_FUSED_SM40=0` は既定選択を MMQ 側へ戻す診断用の設定です。80 SM 以上の既定ルールや明示 opt-in の判定は変えません（`include/strata/prefill/fused_tile_rule.hpp:139-166,198-202`）。

Flash-Next 系 CUDA kernels では、既定の K-quant fused kernels のセットアップ条件と、IQ 系の既定層選択に使われます（`src/prefill/moe_fused_iq.cu:2461-2475,2975-2990`）。Qwen 3.6 の CUDA 用コピーも同じ 40〜79 SM の staged 条件を使います（`src/prefill/moe_fused_iq_q36.cu:126-140`）。これはカーネル実装を有効にするための十分条件ではなく、GPU の対応状況、カーネルのセットアップ、層の形式、他の fused スイッチも判定されます。

## 値と判定

`fused_tile::sm40_env_of` は `getenv` の結果を文字列全体として parse せず、ポインターが null か、先頭 1 文字が `0` かだけを見ます。`sm40_on` は判定結果が 0 でない限り有効とします（`include/strata/prefill/fused_tile_rule.hpp:162-166,176-177`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA の既定 fused 判定 | 有効（helper は `-1`、`sm40_on(-1)` は true） | 空文字、`1`、`true`、`false`、` 0`、`0anything` 以外の任意の文字列 | `0`、`00`、`0anything`（先頭が `0` の文字列すべて） |
| HIP の fused 判定 | 効果なし | 効果なし | 効果なし |

空文字は「未設定」ではありませんが、非 null かつ `v[0] != '0'` なので有効扱いです。数値変換、全体一致、大文字小文字、空白除去、範囲検査はありません。負値を含め、先頭が `0` でない文字列はすべて同じ有効扱いです（`include/strata/prefill/fused_tile_rule.hpp:164-177`）。

## 有効になる条件

- **カード条件:** 40〜79 SM ルールは `c.s86 || c.s120` が必要です。`s86` は compute capability 8.0 / 8.6 / 8.9 で、`STRATA_PF_FUSED_SM86=0` ならこのクラスから除外されます。`s120` は compute capability 12.0 かつ `STRATA_SM120_PERF` による既定が有効なカードです。判定境界は 40 SM を含み、80 SM はこの変数に依存しません（`include/strata/prefill/fused_tile_rule.hpp:29-33,139-143`; `include/strata/core/sm120_series.hpp:30-40,58-59`; `src/prefill/moe_fused_iq.cu:2417-2427`）。
- **Flash-Next の K-quant:** `STRATA_PF_FUSED_KQ` が unset のとき、この変数が 40〜79 SM の既定 K-quant kernels の選択に使われます。`STRATA_PF_FUSED_KQ=0` は K-quant kernels のセットアップを止め、`STRATA_PF_FUSED_KQ=1` はこの 40〜79 SM 判定を迂回して対応する CUDA カードでセットアップを要求します。後段で `STRATA_PF_FUSED=0` なら fused 層選択は止まります（`include/strata/prefill/fused_tile_rule.hpp:190-202`; `src/prefill/moe_fused_iq.cu:2461-2475,2891-2914,2954-2957`）。
- **Flash-Next の IQ 系:** `STRATA_PF_FUSED` が未設定であることが既定ルールの条件です。40〜79 SM では、gate/up が weight-staging 対応形式（IQ3_XXS / IQ3_S / IQ4_XS）で、down が IQ4_NL または Q2_0 の層だけがこのルールの対象です。未設定の `STRATA_PF_FUSED_SM40` はその対象層を既定で選びます。`STRATA_PF_FUSED=0` は止め、`STRATA_PF_FUSED=1` は既定ルールとは別の opt-in 経路です（`include/strata/prefill/fused_tile_rule.hpp:130-166`; `src/prefill/moe_fused_iq.cu:2975-2990`）。
- **Qwen 3.6 CUDA:** `STRATA_PF_FUSED` が unset のときだけ既定ルールがこの変数を使います。40〜79 SM の場合は staged gate/up と許可された down の組み合わせに限られます。`STRATA_PF_FUSED=1` は対応層を明示選択し、`=0` は選択しません（`src/prefill/moe_fused_iq_q36.cu:126-140`; `include/strata/prefill/fused_tile_rule.hpp:169-182`）。
- **MMQ を含まない build:** Strata は fused の opt-in スイッチ群（`STRATA_PF_FUSED` と `STRATA_PF_FUSED_KQ` を含む）を、利用者が設定していない場合に起動前に `1` にします。この場合、IQ の `STRATA_PF_FUSED` 既定判定は opt-in 分岐になり、K-quant の `STRATA_PF_FUSED_KQ` も明示 opt-in 扱いになるため、この変数による 40〜79 SM の既定切替は適用されません（`include/strata/prefill/own_only_switches.hpp:18-25`; `src/prefill/prefill.cpp:205-232`; `src/prefill/moe_fused_iq.cu:2891-2909,2467-2470`）。`strata-q36` も MMQ がない build では unset の `STRATA_PF_FUSED` を `1` に設定します。その場合は Qwen 3.6 の既定判定を通らず、この変数は fused 層選択に影響しません（`src/qwen35/q36_engine.cu:3960-3972`; `src/prefill/moe_fused_iq_q36.cu:128-140`）。
- **HIP:** `moe_fused_iq_q36.cu` はこの値を static 変数へ読みますが、HIP 分岐では `(void) sm40_env` として捨て、gfx12 判定には `STRATA_PF_FUSED` とカーネル対応状況だけを使います。元の `moe_fused_iq.cu` でも `sw_on` は HIP で常に false、CUDA の SM40 判定ブロックは `#if !defined(__HIPCC__)` 内です。したがって HIP の結果はこの値で変わりません（`src/prefill/moe_fused_iq_q36.cu:128-140`; `src/prefill/moe_fused_iq.cu:163-172,2416-2417,2984-2990`）。
- 40 未満のカード、80 SM 以上のカード、sm_121、sm_86 クラス外のカードでは、SM40 の切り替えは既定選択を変えません。K-quant の明示 opt-in など、別のルートは個別の条件に従います（`include/strata/prefill/fused_tile_rule.hpp:139-143,198-202`）。

## 実行時の詳細

Flash-Next CUDA の `dev_info()` はデバイスごとに `done` を立てて初回だけセットアップを行います。その CUDA ブロックで `STRATA_PF_FUSED_SM40` を static local に読み、`kq_takes` の結果に従って K-quant kernels を setup します。したがって、その初回 `dev_info()` 評価後にプロセス環境を変更しても、そのデバイスの `d.kq` セットアップ結果は更新されません（`src/prefill/moe_fused_iq.cu:2379-2385,2416-2427,2461-2475`）。

IQ 系の既定層判定は `native_supported` 内の既定分岐で static local に値を読み、`default_takes_env` に渡します。Qwen 3.6 コピーも `native_layer_ext` の static local に値を読みます。いずれも初回評価後にプロセス環境だけを変更してもキャッシュは更新されません（`src/prefill/moe_fused_iq.cu:2975-2990`; `src/prefill/moe_fused_iq_q36.cu:128-140`）。

`src/core/nv_defaults.cpp:nv_kq_fused_here` は別の状態表示用判定として、この値を関数呼び出しごとに読みます。NVIDIA の起動時 GPU 判定から呼ばれ、K-quant MMQ の既定が追加された場合、ロード済みモデルに K-quant expert があれば fused kernels か MMQ かを説明する行を stderr に出します。この行は通常、モデルの expert layout を読んだ後に出されます（`src/core/nv_defaults.cpp:142-147,178-191`; `src/program/generate.cpp:4232-4242,5064-5070`）。この表示用読み取りと、カーネル側の static cache は別です。

この変数自体を理由とする警告、エラー、終了処理は見つかりません。K-quant の起動案内行は、K-quant MMQ 既定の適用とモデル内の K-quant expert の存在を条件に出力されます。表示文字列は fused 判定時に `strata: a model with K-quant experts (Unsloth UD-Q4/Q5/Q6_K_XL) reads its prompt on Strata's own kernels where they cover the layer (Q4_K and Q5_K gate/up with a Q5_1 or Q8_0 down) and on llama.cpp's MMQ kernels for the rest (STRATA_PF_FUSED_KQ=0 gives all of them back to MMQ)`、非 fused 判定時に `strata: a model with K-quant experts (Unsloth UD-Q4/Q5/Q6_K_XL) reads its prompt on llama.cpp's MMQ kernels (STRATA_MMQ_KQ=0 or STRATA_NV_KQ_DEFAULT=0 turns it off)` です（`src/core/nv_defaults.cpp:153-165`; `src/program/generate.cpp:5064-5070`）。この案内は SM40 の値専用ログではありません。

## ログと測定値

`fused_tile_rule.hpp` のコメントには、対象ルールを有効にする RTX A4000（compute capability 8.6、48 SMs）の一層実測として、IQ3_XXS モデルで staged pair 19 層を fused、29 層を MMQ にした end-to-end 比較が記載されています。MMQ / fused の prompt time は 2K / 4K / 8K / 20K token で `1.000 / 1.003 / 1.028 / 1.012`、forced-token KL は FP16 prompt path 比で 2,048 ids が `0.930 [0.881, 0.988]`、8,192 ids が `0.973 [0.898, 1.057]` とされています。コメント記載の条件は expert が PCIe 経由で stream される RTX A4000 の構成です。これはソースコメントに記録された測定値であり、本調査で再測定した値ではありません（`include/strata/prefill/fused_tile_rule.hpp:130-138`）。

同ファイルの K-quant 40〜79 SM の例は RTX A4000（48 SMs、CUDA 12.9、128-row tile、一層、1 回の反復）です。300 / 1,000 / 2,048 / 4,096 / 8,192 / 20,000 tokens 順の MMQ time / fused time 比は、Q4_K / Q5_1 が `1.67 / 1.44 / 1.49 / 1.35 / 1.05 / 0.97`、Q4_K / Q8_0 が `1.79 / 1.61 / 1.67 / 1.46 / 1.08 / 0.98`、Q5_K / Q8_0 が `1.72 / 1.59 / 1.60 / 1.45 / 1.05 / 0.99` です。ソースコメントは 8,192 token までは fused が先行し、20,000 では 1〜3% 遅れると記しています。一層の結果で、同 SM 数クラスでの一般的な性能を示すものではありません（`include/strata/prefill/fused_tile_rule.hpp:190-197`）。

## 根拠

- `include/strata/prefill/fused_tile_rule.hpp:139-166,176-202` — SM40 の既定ルール、値の変換、K-quant 判定。
- `src/prefill/moe_fused_iq.cu:163-172,2379-2385,2416-2427,2461-2475,2891-2914,2975-2990` — weight-staging 対応形式、CUDA のセットアップと層選択、static cache。
- `src/prefill/moe_fused_iq_q36.cu:126-140` — Qwen 3.6 コピーの CUDA/HIP 分岐。
- `src/core/nv_defaults.cpp:142-165,178-191`; `src/program/generate.cpp:4232-4242,5064-5070` — NVIDIA の起動案内用判定と表示。
- `include/strata/core/sm120_series.hpp:30-40,58-59` — compute capability 12.0 のカード条件。
