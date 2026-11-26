# `STRATA_PF_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の gfx11 系 native MoE prompt kernels で、対象レイヤーを int8 系カーネルから FP16 行列コア系カーネルへ切り替えるスイッチです。値の先頭が `1` または `2` なら共有判定 `f16::requested()` が true になり、対応する i-quant と K-quant の処理が FP16 カーネル候補になります。さらに先頭が `2` の場合、gfx11 WMMA が使えるデバイスでは 128-token pair の `native_h11p_kernel` も候補になります。したがって `2` はこの経路を含みますが、単独で fused native prompt path を有効にするものではありません。`engine/src/prefill/moe_f16_common.cuh:55-62`、`engine/src/prefill/moe_fused_iq.cu:3631-3640,3716-3752,3781-3808`。

## 値と判定

値を解釈する二つの箇所はいずれも環境文字列全体を数値変換せず、先頭文字だけを調べます。空文字、未設定、先頭が `0`、`true`、空白始まりは無効です。大文字小文字や数値の妥当性検査はなく、後続文字は無視されます。`1` は共有 FP16 経路だけ、`2` は共有経路と gfx11 WMMA の h11p 判定を有効にします。例: `1anything` は共有経路で有効、`2anything` は両方で有効、`0anything` はどちらでも無効、`3` は無効です。`h11p_wanted()` は先頭が `2` かも確認しますが、終端文字は確認しません。`apply_arch_defaults()` にある動的名の `getenv(kv.first.c_str())` は、既定値を注入してよいか環境変数の設定有無だけを確認し、値の parse ではありません。`engine/src/prefill/moe_f16_common.cuh:56-61`、`engine/src/prefill/moe_fused_iq.cu:3631-3637`、`engine/src/core/arch_defaults.cpp:302-309,334-338,406-410`。

| 条件 | unset（明示的な既定設定がなければ） | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP gfx11 の共有 FP16 判定 | 無効 | `1...`、`2...`（先頭がその数字） | 空文字、`0...`、`3...`、`true`、先頭空白 |
| HIP gfx11 WMMA h11p 判定 | 無効 | `2...`（かつ `g11_wmma`、非 gfx12） | 上記以外、またはデバイス条件を満たさない場合 |
| CUDA / HIP gfx12 の h11p 判定 | h11p は無効 | h11p には有効値なし | `h11p_wanted()` が HIP 以外で常に false、gfx12 は `!w12` 条件を満たさない |

## 有効になる条件

- 該当する読み取り・カーネル分岐は HIP ビルドに属します。CUDA では `h11p_wanted()` が常に false です。`engine/src/prefill/moe_fused_iq.cu:3631-3640`。
- 共有 FP16 カーネルは gfx11 向けで、gfx12 (`w12`) では使いません。形式も限定され、gate/up は IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、IQ4_XS、down は Q2_0、IQ4_NL、Q8_0、Q5_0（ほか K-quant は別の `f16kq` 条件）です。`engine/src/prefill/moe_fused_iq.cu:3050-3054,3781-3808`。
- 値 `2` の h11p はさらに `dev_info().g11_wmma && !dev_info().w12` を要求します。gate/up と down の形式ペアが `h11p_takes_pair()` の許可リストに入り、FP16 入力行が渡され、Hadamard 回転中でなく、`n * kMoeFF * 2 <= g_p1a_h_bytes` である必要があります。満たさないレイヤーはこの h11p 分岐を通りません。`engine/src/prefill/moe_fused_iq.cu:3631-3654,3716-3725`。
- これらの native kernels に到達するには、native expert layout と対応形式のほか、prefill 側の fused 条件（MMQ または fused-only layer、`stream_all`、peer path でないこと、回転レイヤーなら対応形式であること）が必要です。レイヤー形式のカバレッジ判定は `native_supported()` が行います。`engine/src/prefill/prefill.cpp:5692-5704`。
- HIP の native 形式対応判定は `STRATA_PF_FUSED=1` も要求し、`STRATA_PF_FUSED_NATIVE` の先頭が `0` なら native 形式を無効にします。`STRATA_PF_FUSED` が未設定のときは HIP 経路では通常無効ですが、gfx11 discrete RDNA3 の default table、および Windows gfx1151 integrated の既定セットでは `1` が注入されます。小型 GPU 用の内部 override が off の場合も対象外です。`engine/src/prefill/moe_fused_iq.cu:3415-3432`、`engine/src/core/arch_defaults.cpp:90-109,193-213,429-432`。
- h11p に必要な FP16 入力行は `p1a_input()` 経由で渡されます。通常の fused native レイヤーでは `m.mixed_h`、staged 経路では `m.mixed_h` または `lb.mixed_h` が渡されます。`engine/src/prefill/prefill.cpp:5774-5776,5857-5860,7213-7219,8932-8936`。
- 自動既定値の対象は限定されています。非 integrated の discrete RDNA3 gfx1100/gfx1101/gfx1102 では `gfx11_discrete_wmma_env()` が既定値 `2` を返しますが、`STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0`、または `STRATA_DEFAULTS=026` により抑止されます。Windows の gfx1151 integrated GPU では、全可視 GPU が integrated であり、`igpu_prompt_set_enabled()` が許可すると設定されます。Linux gfx1151 integrated の既定セットはこの `2` を含みません。`engine/include/strata/core/gfx11_extra.hpp:87-110`、`engine/src/core/arch_defaults.cpp:172-215`。
- 自動既定値は `apply_arch_defaults()` が環境変数未設定時だけ注入します。明示的に空文字を設定した場合も「設定済み」として保持され、無効値になります。Linux の `setenv(..., 0)` も既存値を上書きしません。`engine/src/core/arch_defaults.cpp:218-224,302-309,334-344,406-420`。

## 実行時の詳細

`apply_arch_defaults()` は GPU 情報を調べた後、生成処理から呼び出されます。対象 GPU の default table が `STRATA_PF_F16=2` を返し、かつ環境に同名の値がまだなければ、そのプロセスの環境へ設定します。外部から設定された値（空文字を含む）が優先され、CLI 引数による個別上書き箇所は確認できません。`engine/src/program/generate.cpp:4295-4320`、`engine/src/core/arch_defaults.cpp:302-309,334-344,406-420`。

カーネル側では `f16::requested()` と `h11p_wanted()` がそれぞれ関数内 `static` に最初の評価結果を保存します。従って、その最初の呼び出し後に環境文字列を変更しても判定は更新されません。アーキテクチャ既定値の注入は engine のスイッチ読み取り前に行う設計です。`engine/src/prefill/moe_f16_common.cuh:56-62`、`engine/src/prefill/moe_fused_iq.cu:3631-3640`、`engine/include/strata/core/arch_defaults.hpp:157-162`。

共有判定が有効でも、実際に変わるのは対象レイヤーの MoE gate/up・down 計算カーネルと、down 出力を FP16 にする別スイッチ `STRATA_PF_DM16` が有効な場合の出力形式です。h11p は `native_h11p_kernel` を起動し、`STRATA_PF_DM16` が要求される場合は down 出力も FP16 にします。変数単独で生成 token やルーティングを変更する処理は見当たりません。`engine/src/prefill/moe_fused_iq.cu:3716-3752,3781-3797`。

## ログと測定値

gfx11 の matrix-core default table から一つ以上の値が新規注入された場合、stderr に `strata: gfx11 (RDNA3): ... matrix-core prompt & MoE switches on by default ...` の行が出て、適用した変数名の一覧に `STRATA_PF_F16` が含まれます。値を事前設定していた場合はその変数は一覧に含まれません。`engine/src/core/arch_defaults.cpp:334-344`。

fused native 経路に入ると、初回に限り stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` が出ます。この文言は FP16 カーネル選択を個別には示しません。h11p 固有の有効ログや、このスイッチによる失敗用メッセージは確認できませんでした。`engine/src/prefill/prefill.cpp:5758-5762`。

native expert 実装に未対応の形式が渡された場合は stderr に `prefill fused experts (native): types %d / %d are not covered here` を出して `exit(1)` します。通常は呼び出し前の `native_supported()` と対応形式チェックで候補から外れるため、この環境変数だけでこの終了経路になるとは言えません。`engine/src/prefill/moe_fused_iq.cu:3697-3700`。

測定値は記載しません。リポジトリ文書の測定値は複数設定・GPU・モデル・測定条件に依存し、このスイッチ単体の一般的な値としては扱えません。

## 根拠

- `engine/src/prefill/moe_f16_common.cuh:55-62` — 共有 FP16 判定。
- `engine/src/prefill/moe_fused_iq.cu:3631-3654,3716-3752,3781-3808` — h11p 判定、形式ペア、実カーネル選択。
- `engine/include/strata/core/gfx11_extra.hpp:87-110`、`engine/src/core/arch_defaults.cpp:172-215,218-224,302-344,406-420` — 自動既定値と上書き規則。
- `engine/src/program/generate.cpp:4295-4320` — GPU 判定および既定値適用の呼び出し。
- `engine/src/prefill/prefill.cpp:5692-5704,5774-5776,5857-5860,7213-7219,8932-8936` — fused 条件と FP16 入力の引き渡し。
