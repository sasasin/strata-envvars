# `STRATA_HC_UPMIX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプト prefill の hyper-connection read で、`up` projection と `gr_mix_r` を `gr_upmix` の単一カーネルにまとめる opt-in スイッチ。対象の layer/half で成立すると、従来の `bf16_proj(..., su, ...)` と後段の `gr_mix_r` を省く。down projection、inject projection、decode 経路を切り替える変数ではない。CUDA/HIP 実装は `engine/src/prefill/prefill.cpp`、SYCL 実装は `engine/sycl/src/prefill/prefill.cpp` にある。`engine/sycl/src/prefill/kernels.dp.cpp` の `gr_upmix` は HIP ビルド時だけカーネルを起動する。

## 値と判定

両 prefill 実装の `hc_upmix()` は、初回評価時に `std::getenv` の返す文字列の先頭が文字 `'1'` かを調べ、その真偽値を関数内 `static` に保存する。文字列全体の parse・数値検証・trim・大小文字変換はしない。従って unset、空文字、`0`、`true`、` 1` は無効で、`1`、`1anything`、`10` は有効。その他の数字や文字列も先頭が `1` でなければ無効。CUDA 側は後述の 33 token 下限も加わる。根拠: `engine/src/prefill/prefill.cpp:985-987,991-996`; `engine/sycl/src/prefill/prefill.cpp:377-379`。

| 経路 | unset（GPU 既定値適用後） | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA prefill | 通常 OFF。対象 NVIDIA GPU 世代の既定値表に該当すれば `1` が注入される | 先頭文字が `1` で、他の実行条件も満たす | 空文字、`0`、`true`、` 1` など先頭が `1` でない値 |
| HIP prefill（CUDA/HIP 共用 `prefill.cpp`） | 通常 OFF。RDNA3 discrete / 対象の integrated AMD GPU の既定値表に該当すれば `1` が注入される | 先頭文字が `1` で、gfx11 の `gr_upmix` が利用可能 | 空文字、`0`、`true`、` 1` など先頭が `1` でない値 |
| SYCL prefill | 直接の既定値注入はこの判定箇所にないため unset は OFF | 先頭文字が `1` で、実行時 `gr_upmix` が利用可能 | 空文字、`0`、`true`、` 1` など先頭が `1` でない値 |

環境変数が存在するだけで既定値が上書きされる。たとえば空文字や `0` も「ユーザーが設定済み」と扱われ、Strata の自動注入は行われず、機能は OFF になる。CUDA の既定値表は sm_86、sm_89、sm_120、sm_121 にあり、HIP の既定値表には gfx1100/1101/1102、gfx1151 Windows、および対象 integrated GPU がある。根拠: `engine/src/core/nv_defaults.cpp:59-70,83-92,104-112,193-198`; `engine/include/strata/core/gfx11_extra.hpp:90-108`; `engine/src/core/arch_defaults.cpp:172-189,193-200,218-223,302-309,334-343,406-416`。

## 有効になる条件

- 対象はプロンプト prefill の hyper-connection read。各 layer の attention/FFN half で up weights が使われる経路で判定される。decode ではこの prefill loop の分岐を通らない。根拠: `engine/src/prefill/prefill.cpp:5074-5089,5127-5130`; `engine/sycl/src/prefill/prefill.cpp:3420-3435,3460-3463`。
- CUDA では chunk の `T >= max(STRATA_PF_SWITCH_MIN_T, 33)` が必要。`STRATA_PF_SWITCH_MIN_T` は unset なら 0 で、設定時は `atoll` で関数内 static に一度変換される。33 未満は既定の projection/mix に戻る。根拠: `engine/src/prefill/prefill.cpp:975-978,989-996,5129-5130`。
- HIP と SYCL の prefill 判定では `T >= STRATA_PF_SWITCH_MIN_T` が必要（同変数 unset の下限は 0）。`gr_upmix` の実装は HIP build かつ gfx11 WMMA 対応 device でのみ起動し、それ以外は `false` を返す。根拠: `engine/sycl/src/prefill/prefill.cpp:372-379,3462-3463`; `engine/sycl/src/prefill/kernels.dp.cpp:2454-2472`。
- CUDA `gr_upmix` は CUDA device compute capability major 8 以上でのみ起動する。sm_80 未満、device query 失敗、または `T <= 0` の場合は `false` を返し、呼び出し元が従来の up projection に戻る。CUDA 側の既定値注入があることだけでは、sm_80 未満でカーネルが有効にならない。根拠: `engine/src/prefill/kernels.cu:2985-3016`。
- `STRATA_GR_UNFUSED=1`、`m.lo16_lo` または `m.mixed_bf_lo` の存在時は fused 条件を満たさない。さらに `wu->q8_scale` が null、up weight が `Bf16InF32`、weight data が存在し、寸法が `LR x D` であることが必要。条件不成立時は通常 projection と mix に進む。根拠: `engine/src/prefill/prefill.cpp:5129-5130,5155,5159-5164`; `engine/sycl/src/prefill/prefill.cpp:3462-3463,3502-3509`。
- CUDA の sm_86 / sm_89 / sm_120 / sm_121 および HIP の列挙された RDNA3 / integrated GPU では Strata が unset の変数を `1` に設定する既定値経路がある。先にユーザーが何らかの値を設定していればその値を保つ。AMD integrated GPU の既定値セットは `STRATA_IGPU_PROMPT_SET` が有効な場合に限られる。NVIDIA の該当世代の表は `STRATA_SM86_PERF` / `STRATA_SM89_PERF` / `STRATA_SM120_PERF` / `STRATA_SM121_PERF` 및 `STRATA_DEFAULTS=026` の選択で外れる。根拠: `engine/src/core/nv_defaults.cpp:59-70,81-92,104-112,190-198`; `engine/src/core/arch_defaults.cpp:172-180,302-309,334-343,406-416`。

## 実行時の詳細

`hc_upmix()` の static cache はプロセス内で初めて該当 helper が呼ばれたときに確定し、その後の環境変更は反映されない。GPU 既定値注入が行われる経路では、`apply_nv_defaults` または `apply_arch_defaults` が unset のキーに限って `setenv(..., 0)` / `_putenv_s` 相当で値を設定するため、その後 prefill helper が読む値は注入後の環境値になる。CLI 引数による同変数の上書き箇所は確認できない。根拠: `engine/src/prefill/prefill.cpp:985-987`; `engine/sycl/src/prefill/prefill.cpp:377-379`; `engine/src/core/nv_defaults.cpp:222-234`; `engine/src/core/arch_defaults.cpp:218-223,302-309,406-410`。

upmix 条件を満たした後も `gr_upmix` が device 対応判定により `false` を返せば、呼び出し元は標準の `bf16_proj` と `gr_mix_r` に戻る。成功時は fused kernel が `mixed` を生成し、その half では後段の `gr_mix_r` を呼ばない。`STRATA_HC_UPMIX_CHECK` が正数なら各 backend の最初の N 回の対象 read で標準 projection/mix も先に実行し、比較値を得てから upmix を実行する。カウンターも static に初期化され、値は `atoi` 変換。根拠: `engine/src/prefill/prefill.cpp:5131-5155,5159-5164`; `engine/sycl/src/prefill/prefill.cpp:3464-3509`; `engine/src/prefill/kernels.cu:2991-3015`; `engine/sycl/src/prefill/kernels.dp.cpp:2456-2472`。

## ログと測定値

この変数単独の有効/無効を示すログは確認できない。GPU 既定値注入時は一般的な既定値ログに名前が含まれる。AMD integrated GPU では `strata: integrated GPU (%s): the matrix-core prompt set is on ...` の行に注入された switch 名が出力され、`NAME=0` で一つを切れる旨も表示される。NVIDIA の既定値では `strata: sm_...: ... speed switches on by default ...` の行に設定名が出る。根拠: `engine/src/core/arch_defaults.cpp:397-420`; `engine/src/core/nv_defaults.cpp:240-255`。

`STRATA_HC_UPMIX_CHECK` による比較時は stderr に `strata: STRATA_HC_UPMIX_CHECK layer ... half ... T ...: mixed rel RMS ..., max |diff| ... (upmix|upmix refused)` を出す。値が正数であり、upmix の前提条件を通った対象 read に限る。通常の実行でこの診断を有効にする変数は `STRATA_HC_UPMIX_CHECK` であり、測定ログを性能値とは解釈しない。根拠: `engine/src/prefill/prefill.cpp:5131-5149`; `engine/sycl/src/prefill/prefill.cpp:3464-3496`。

## 根拠

- 値の cache と token 下限: `engine/src/prefill/prefill.cpp:975-996`; `engine/sycl/src/prefill/prefill.cpp:372-379`。
- CUDA の実動作、fallback、mix の省略: `engine/src/prefill/prefill.cpp:5127-5164`; `engine/src/prefill/kernels.cu:2985-3016`。
- SYCL の実動作と HIP/gfx11 runtime gate: `engine/sycl/src/prefill/prefill.cpp:3460-3509`; `engine/sycl/src/prefill/kernels.dp.cpp:2454-2472`。
- GPU 既定値注入、設定済み値の保持、ログ: `engine/src/core/nv_defaults.cpp:59-70,81-92,104-112,190-198,222-255`; `engine/include/strata/core/gfx11_extra.hpp:90-108`; `engine/src/core/arch_defaults.cpp:172-189,193-200,218-223,302-309,334-343,406-420`。
