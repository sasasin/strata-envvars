# `STRATA_PF_FUSED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Strata の prompt prefill で、対象の MoE expert 計算を fused int8 系カーネルへ振り分ける大域スイッチです。モデルの expert 形式・gate/up と down の組合せ、GPU、build、追加の `STRATA_PF_FUSED_*` 変数により、実際に fused 経路へ入る layer は異なります。未対応 layer は既存の MMQ または FP16 経路に残ります。CUDA の Q2_0 pack と native pack では判定関数・既定値が別です。native pack の fused 判定は `native_supported()`、Q2_0 pack は `fused::enabled()` / `requested()` を通ります（`engine/src/prefill/moe_fused.cu:707-730`, `engine/src/prefill/moe_fused_iq.cu:3415-3432`, `engine/src/prefill/prefill.cpp:5663-5771`）。

## 値と判定

値は整数として parse されず、各経路が `getenv` の返す文字列の先頭文字を検査します。`true` / `false`、大文字小文字、数値としての妥当性、後続文字は検証しません。したがって `1abc` は先頭が `1` の経路で有効、`0anything` は先頭が `0` の経路で無効です。同じ変数でも経路により空文字の意味が異なります。

| 経路 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA native pack（通常の `native_supported`） | 既定ルールを使用 | `1`, `1abc`（カバーされる native fused layer を opt-in） | `0`, `0abc`, `true`, `2`, 空文字以外の `x`（native fused 判定を停止） |
| HIP native pack | gfx12 の形式別既定値などを使用。gfx11 WMMA の一般経路は opt-in | `1`, `1abc`（対応 layer を opt-in） | `0`, `0abc`, `true`, `2`, `x`（native fused 判定を停止） |
| Qwen 3.6 engine (`strata` / `strata-q36`) | CUDA はカード既定ルール。HIP は通常 fused なし | `1`, `1abc`（kernel 対応 layer） | `0`, `0abc`, `true`, `2`, `x` |
| CUDA Q2_0 pack (`fused::enabled`) | ON | `1`, `1abc`, 空文字、`true`, `2`, `x`。ただし先頭 `0` は除く | `0`, `0abc` |
| HIP Q2_0 pack (`fused::enabled`) | OFF | `1`, `1abc` | unset、空文字、`0`, `0abc`, `true`, `2`, `x` |
| staged group entry | CUDA は既定 ON、HIP は既定 OFF | 非空で先頭 `1` のとき ON | 非空で先頭が `1` 以外なら OFF |

native pack の共通 parse は null または空文字を unset (`-1`)、先頭 `1` を opt-in (`1`)、それ以外を off (`0`) とします。Qwen 3.6 も同じ parse を使います。staged group entry は別実装で、空文字を CUDA/HIP の build 既定に委ねます（`engine/src/prefill/moe_fused_iq.cu:3425-3428`, `engine/include/strata/prefill/fused_tile_rule.hpp:173-190`, `engine/src/prefill/prefill.cpp:328-337`, `engine/include/strata/prefill/staged_group_rule.hpp:12-15`）。

CUDA native pack で unset/空文字の場合、既定はカード・kernel 対応状況にも依存します。IQ 形式の default gate/up は sm_86 class（compute capability 8.0/8.6/8.9）と 80+ SM の sm_120、さらに条件を満たす 40–79 SM の staged launch で既定 ON。それ以外のカード・launch は opt-in です。native Q2_0 gate/up はこの既定リストに含まれず、`STRATA_PF_FUSED_Q2N=1` が別途必要です（`engine/include/strata/prefill/fused_tile_rule.hpp:156-170`, `engine/src/prefill/moe_fused_iq.cu:3508-3531`）。CUDA の K-quant は別の card rule または `STRATA_PF_FUSED_KQ=1` によります（`engine/src/core/nv_defaults.cpp:276-281`, `engine/src/prefill/moe_fused_iq.cu:3028-3048`）。

## 有効になる条件

- **Build なし MMQ:** `STRATA_PREFILL_FUSED` が定義され、`STRATA_PREFILL_MMQ` が未定義の build では、startup initializer が `STRATA_PF_FUSED` を含む default switch 群を `1` に設定します。環境に既に名前があれば値を問わず保持するため、事前の `=0` は尊重されます。この初期化は `main()` より前です（`engine/src/prefill/prefill.cpp:223-255`, `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-56`）。
- **CUDA DGX Spark / sm_121:** server の GPU default 適用時、`STRATA_DEFAULTS=026` でなく `STRATA_SM121_PERF=0` でもない場合、`nv_default_env()` は `STRATA_PF_FUSED=1` を既定値に含めます。既に環境変数があれば値を問わず上書きしません。適用は同一 compute capability の CUDA GPU 構成で行われます（`engine/src/core/nv_defaults.cpp:176-192,222-234`, `engine/src/program/generate.cpp:4430-4449`）。
- **Linux integrated gfx11:** `arch_defaults` が integrated gfx1103/gfx1150/gfx1151 で unset の場合に `1` を設定します。明示的な空文字も「設定済み」として setter を抑止します。Windows はこの既定の対象外です（`engine/src/core/arch_defaults.cpp:167-170,423-432`）。
- **CUDA native pack:** `STRATA_PF_FUSED=1` は対応済み形式の opt-in。ただし `STRATA_PF_FUSED_NATIVE=0`、override、GPU capability/kernel setup、gate/up と down の形式条件などで無効または未対応になり得ます。unset/空文字では前節の card default を使います。例えば 40–79 SM の既定 fused は staged gate/up と IQ4_NL/Q2_0 down の組合せに限定され、Q2_0/Q2_0 は別スイッチです（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3533`）。
- **HIP native pack:** gfx12 の IQ2_S など一部は形式別既定で ON ですが、グローバル値の先頭が `0` なら停止します。Windows gfx12 の IQ2_XS/XXS は `STRATA_PF_FUSED=1` が opt-in 条件です。gfx12 の fused kernels は native pack 用で、Q2_0 pack の CUDA fused kernel は移植されていません（`engine/src/prefill/moe_fused_iq.cu:3389-3411,3420-3432`; `engine/src/prefill/moe_fused_iq.cu:2660-2668`）。
- **Q2_0 pack:** CUDA では unset 既定 ON、先頭 `0` で MMQ に戻ります。HIP のこの `fused::enabled()` 経路は先頭 `1` が必要です。カーネル自体の availability も必要です（`engine/src/prefill/moe_fused.cu:707-729`）。
- **Qwen 3.6:** `native_layer_ext()` は対応済み layer に対して CUDA では `1` なら全対応カード、unset/空文字なら通常の card default、先頭 `0` なら無効。HIP は gfx12 かつ有効値 `1` の場合に限り使用します。standalone `strata-q36` は MMQ なし build で unset/空文字を `1` に設定し、MMQ あり build では設定を維持します（`engine/src/prefill/moe_fused_iq_q36.cu:128-142`, `engine/src/qwen35/q36_engine.cu:5441-5454`, `engine/include/strata/prefill/fused_tile_rule.hpp:187-192`）。
- **小容量 cache の serve 経路:** auto chunk が 8,192 未満、単一 CUDA GPU、native pack、複数 stage なし、`STRATA_DEFAULTS=026` 相当の既定ではない場合、ユーザーが `STRATA_PF_FUSED` を非空で指定していなければ small-card rule が fused off / layer-major walk を選ぶことがあります。`STRATA_PF_SMALL=0` は判定自体を抑止します。MMQ なし build が自分で追加した `1` はユーザー指定と見なされず、このルールを抑止しません（`engine/src/program/generate.cpp:12562-12583`, `engine/include/strata/core/sm120_series.hpp:202-218`, `engine/include/strata/prefill/own_only_switches.hpp:59-73`）。
- **他の制御との関係:** `STRATA_PF_FUSED=0` は fused native の形式別既定も含め全 fused 判定を止めます。一方、`STRATA_PF_FUSED_KQ`, `_Q2N`, `_TQ`, `_Q8D`, `_Q8GU`, `_Q6K` など各形式スイッチは、対応形式・GPU で追加条件になります。`STRATA_PF_SMALL_FUSED=0` は small-card walk 内の fused kernel も無効化します（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3533`, `engine/src/program/generate.cpp:12581-12583`, `engine/include/strata/prefill/pf_fused_override.hpp:26-29`）。
- **変換 expert slot との競合:** `STRATA_EXPERT_NIBBLE` の検査経路は、値が非空で先頭 `1` の `STRATA_PF_FUSED` を競合として扱います（`engine/include/strata/core/expert_nibble.hpp:272-299`）。

## 実行時の詳細

主要な kernel 判定は関数内 `static` に保存され、初回の該当関数呼び出しで環境を読みます。Q2_0 pack の `enabled()` / `requested()`、native pack の `native_supported()`、Qwen 3.6 copy の `native_layer_ext()`、staged group entry はそれぞれ static cache を持ちます。起動後にプロセス環境を書き換えても、すでに初期化された各 cache の判定は変わりません（`engine/src/prefill/moe_fused.cu:712-729`, `engine/src/prefill/moe_fused_iq.cu:3415-3432`, `engine/src/prefill/moe_fused_iq_q36.cu:130-142`, `engine/src/prefill/prefill.cpp:328-337`）。

serve の small-card 判定は expert cache のサイズと既定 chunk が決まった後に行い、環境を読む static cache とは別の process-wide atomic override を設定します。未設定変数をこの override が fused-on として扱う場合もあります。`STRATA_PF_FUSED` をユーザーが非空で指定したと認識した場合は small-card rule が step aside します（`engine/src/program/generate.cpp:12562-12612`, `engine/include/strata/prefill/pf_fused_override.hpp:15-29`）。

## ログと測定値

fused int8 の prompt 経路に入ると stderr に次の行を一度出します（`engine/src/prefill/prefill.cpp:5758-5762`）。

```text
strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)
```

small-card rule が適用されると、既定 chunk と選択後 chunk を含む `strata serve: small expert cache: ...` の行を出します。再計画した unfused layout が収まらず元の経路へ戻す場合の行は `strata serve: small expert cache: the unfused prompt path does not fit here; the default path stays (chunk %lld tokens)` です（`engine/src/program/generate.cpp:12595-12612`）。この調査では測定を実施していません。

## 根拠

- build なし MMQ の初期値: `engine/src/prefill/prefill.cpp:223-255`, `engine/include/strata/prefill/own_only_switches.hpp:18-24,48-73`
- backend / card ごとの判定: `engine/src/prefill/moe_fused.cu:707-730`, `engine/src/prefill/moe_fused_iq.cu:3415-3432,3508-3533`, `engine/include/strata/prefill/fused_tile_rule.hpp:156-190`
- Qwen 3.6 と staged group: `engine/src/prefill/moe_fused_iq_q36.cu:128-142`, `engine/src/qwen35/q36_engine.cu:5441-5454`, `engine/src/prefill/prefill.cpp:326-337`
- integrated GPU default と小容量 cache: `engine/src/core/arch_defaults.cpp:167-170,423-432`, `engine/src/program/generate.cpp:12562-12612`, `engine/include/strata/core/sm120_series.hpp:202-218`
