# `STRATA_PF_P1A`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP ビルドの gfx11 WMMA 対応 GPU で、条件を満たす native fused MoE の prompt 層を P1A の FP16 gate/up・down カーネルへ切り替える要求スイッチ。通常の fused native カーネルを常に置き換えるものではなく、対象の量子化型、FP16 入出力、バッファ容量などを満たした呼び出しだけが切り替わる。CUDA ビルドでは要求判定が常に false である。`p1a_wanted()` と `experts_native()` が判定・実行を担う（`engine/src/prefill/moe_fused_iq.cu:3612-3621, 3703-3715`、`engine/src/prefill/prefill.cpp:206-211`）。

## 値と判定

HIP では `p1a_wanted()` が `STRATA_PF_P1A` の文字列全体を `"1"` と比較し、加えて GPU が gfx11 WMMA 対応であることを要求する。数値変換はしない。unset、空文字、`0`、`true`、`01`、`1x`、` 1`、`1 ` はすべて要求 OFF。大文字小文字は関係しない（受理値が数字のみ）。ただし起動時にアーキテクチャ既定値が設定される構成では、unset から `"1"` になる場合がある。初回の `p1a_wanted()` 呼び出し時に `static const bool` へ保存されるため、その後の環境変更は反映されない（`engine/src/prefill/moe_fused_iq.cu:3612-3621`）。

| 条件（HIP ビルド） | unset の既定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| gfx1100/1101/1102 の discrete RDNA3。WMMA 既定値が有効 | 起動時に `"1"`。既定値設定前から環境変数が存在すればその値を保持 | `"1"` のみ | 例: `"0"`、空文字、`"1x"` |
| integrated gfx1151、Windows、全可視 GPU が integrated。iGPU prompt set が有効 | 起動時に `"1"`。既存値は保持 | `"1"` のみ | 例: `"0"`、空文字、`"1x"` |
| 上記以外（例: Linux gfx1151、gfx1150、gfx1103、gfx12、混在 GPU） | 既定値設定による変更なし。通常 unset は OFF | `"1"` のみ。GPU が gfx11 WMMA 対応でなければ OFF | `"0"`、空文字、`"true"` など |

既定値は `apply_arch_defaults()` が対象名の環境変数の存在を調べてから設定するため、値が空でも既存の値として優先される。discrete RDNA3 の既定値は `STRATA_GFX11_DEFAULTS=0` または `STRATA_GFX11_WMMA_DEFAULTS=0` で抑止される。Windows gfx1151 integrated の既定値は `STRATA_IGPU_DEFAULTS=0` または `STRATA_IGPU_PROMPT_SET=0` で抑止できる。後者の既定値は `STRATA_IGPU_PROMPT_SET=1` で有効化する規則に従う（`engine/include/strata/core/gfx11_extra.hpp:27-37, 90-109`、`engine/src/core/arch_defaults.cpp:124-138, 172-214, 302-345, 406-420`）。

関連する `STRATA_PF_P1A_L2` も HIP 内の static cache で読み、文字列全体が `"1"` の場合だけ追加の型ペアを許可する（空文字・`"1x"` は無効）。一方、`STRATA_PF_DM16` は `e[0] == '1'` で判定するため、先頭が `1` なら後続文字を問わず有効（例: `"1x"` も有効）。こちらも関数内 static に一度だけキャッシュされる（`engine/src/prefill/moe_fused_iq.cu:3623-3629`、`engine/src/prefill/prefill.cpp:980-984`）。

## 有効になる条件

- HIP ビルドであること。非 HIP 側の `p1a_wanted()` は常に false を返す（`engine/src/prefill/moe_fused_iq.cu:3612-3621`、`engine/src/prefill/prefill.cpp:206-211`）。
- GPU が `gfx_arch_is_gfx11_wmma()` の対象（gfx1100、gfx1101、gfx1102、gfx1103、gfx1150、gfx1151）であること。これは prefix 判定ではなく、arch 名または `:` で続く修飾子との一致（`engine/include/strata/kernels/gfx_arch.hpp:15-19, 28-32`）。
- prompt が native fused MoE 経路を通ること。入力 FP16 行は `fused_nat && !fp4_nat && !fp8_nat` のときだけ渡される（`engine/src/prefill/prefill.cpp:5774-5776`）。
- その層の gate/up と down の型が `Q4_K / Q5_1` であること。`STRATA_PF_P1A_L2` が別途厳密に `"1"` なら、`Q4_K` または `Q5_K` gate/up と `Q5_1` または `Q8_0` down も候補になる（`engine/src/prefill/moe_p1a.cu:509-512`）。
- `STRATA_PF_DM16` の値の先頭文字が `1` であり、CPU rows が 0、peer 経路でなく、`shared` と `bo` のアドレスが 16 byte 境界を満たすこと。そうでなければ `g_dm16_want` が false となり P1A 分岐を通らない（`engine/src/prefill/prefill.cpp:980-984, 5830-5832`、`engine/src/prefill/moe_fused_iq.cu:3707`）。
- down 回転が無効 (`!g_rot_on`)、タイル数が 65,535 以下、FP16 H の必要容量 `(size_t)n * kMoeFF * 2` が確保済み容量以下であること。条件不足の呼び出しは同じ `experts_native()` 内の既存カーネル経路へ進む（`engine/src/prefill/moe_fused_iq.cu:3705-3715`）。

## 実行時の詳細

`generate.cpp` は engine のスイッチを読む前に GPU 情報を使って `apply_arch_defaults()` を呼び出す。既定値候補は既存環境値がある場合は設定せず、ない場合だけプロセス環境へ追加する。discrete RDNA3 の WMMA 既定値テーブルと Windows gfx1151 integrated の prompt set に `STRATA_PF_P1A=1` が含まれる。後者は全可視 GPU が integrated である場合に限って `igpu_default_env()` が適用される（`engine/src/program/generate.cpp:4290-4315`、`engine/src/core/arch_defaults.cpp:302-345, 406-420`、`engine/include/strata/core/gfx11_extra.hpp:90-109`）。

`p1a_wanted()` の値は初回呼び出し時に static cache される。型ペアが合う native expert pack では `p1a_pack()` が H の領域を FP16 行用に拡張する。実行時に入力・FP16 down・回転・tile・容量の条件をすべて満たせば `p1a::gate_up()` と `p1a::down()` を実行し、`g_p1a_used` と `g_dm16_used` を true にしてその呼び出しを終える。満たさない場合はその層の既存 `experts_native` カーネルへ続く（`engine/src/prefill/prefill.cpp:2315-2328, 2341-2346, 5774-5776, 5830-5845`、`engine/src/prefill/moe_fused_iq.cu:3656-3668, 3686-3715`）。

## ログと測定値

- discrete RDNA3 で既定値を設定した場合、設定されたスイッチ名の列挙を含む `strata: gfx11 (RDNA3): %zu matrix-core prompt & MoE switches on by default ...` 行が stderr に出る（`engine/src/core/arch_defaults.cpp:334-344`）。
- Windows gfx1151 integrated で既定値が一つ以上設定された場合、`strata: integrated GPU (%s): the matrix-core prompt set is on ...` 行に設定名が列挙される（`engine/src/core/arch_defaults.cpp:406-420`）。
- P1A を実際に使った層がある場合、初回 fused prompt chunk のレイヤー走査後に stderr へ `strata: prompt experts P1A (STRATA_PF_P1A=1): gate/up + down on the P1A kernels in ...` の集計行を一度出す。P1A 層が 0 の場合はこの行を出さない（`engine/src/prefill/prefill.cpp:2273-2309, 5857-5861`）。
- P1A カーネル起動エラーは `ck(cudaGetLastError(), "experts_native (P1A)")` へ渡される（`engine/src/prefill/moe_fused_iq.cu:3709-3714`）。それ以外に、この変数自体の無効値を知らせる警告・エラーは確認できない。
- 性能測定値はここでは記載しない。対象変数の P1A 経路について、測定条件一式を伴う根拠を確認できなかった。

## 根拠

- 直接の値読み取り・cache・backend 判定: `engine/src/prefill/moe_fused_iq.cu:3612-3621`
- P1A 型ペア: `engine/src/prefill/moe_p1a.cu:509-512`
- アーキテクチャ判定: `engine/include/strata/kernels/gfx_arch.hpp:15-19, 28-32`
- 起動時既定値と適用条件: `engine/include/strata/core/gfx11_extra.hpp:27-37, 90-109`、`engine/src/core/arch_defaults.cpp:124-138, 172-214, 302-345, 406-420`、`engine/src/program/generate.cpp:4290-4315`
- prompt 経路・必要条件・fallback・ログ: `engine/src/prefill/prefill.cpp:2273-2309, 2315-2328, 2341-2346, 5774-5776, 5830-5861`、`engine/src/prefill/moe_fused_iq.cu:3656-3668, 3686-3715`
