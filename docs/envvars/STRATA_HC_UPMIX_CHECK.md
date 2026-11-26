# `STRATA_HC_UPMIX_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

hyper-connection の up projection と mix をまとめる `gr_upmix` がすでに選ばれたとき、最初の N 回だけ従来の projection + `gr_mix_r` も実行し、`mixed` の差を stderr に出す比較用スイッチです。この変数だけでは `gr_upmix` を有効にしません。別の `STRATA_HC_UPMIX` が有効でない、または backend・chunk・weight・buffer 条件を満たさない場合、この変数は読み取られず比較も行われません（CUDA/HIP: `engine/src/prefill/prefill.cpp:5127-5155`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3460-3502`）。

## 値と判定

両 backend とも、比較経路に初めて入ったとき `std::getenv` の結果を関数内 `static int` に保存し、設定されていれば `std::atoi` で整数化します。未設定は `0`、空文字も `atoi("") == 0` です。整数化した値が正の場合にだけ比較し、比較 1 回ごとにカウンターを 1 減らします。全体文字列の妥当性検査や clamp はありません。したがって `1abc` は `1`、`2tail` は `2` として扱われ、`0`、負数、`true`、`false`、数値に変換できない文字列は比較を有効にしません。先頭の空白や符号は `atoi` の規則で解釈されます。`atoi` で `int` の範囲を超える値の結果は保証されません（CUDA/HIP: `engine/src/prefill/prefill.cpp:5131-5133`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3464-3466`）。

| backend の呼び出し経路 | unset / 空文字 | 比較が行われる値の例 | 比較されない値の例 |
|---|---|---|---|
| CUDA/HIP | `0` | `1`, `2`, `+3`, `2tail` | `0`, `-1`, `true`, `abc`, 空文字 |
| SYCL | `0` | `1`, `2`, `+3`, `2tail` | `0`, `-1`, `true`, `abc`, 空文字 |

## 有効になる条件

- 比較処理の前提として `STRATA_HC_UPMIX` が `1` である必要があります。コードはその変数の最初の文字が `'1'` かを検査し、全体一致ではありません（CUDA/HIP: `engine/src/prefill/prefill.cpp:985-987`; SYCL: `engine/sycl/src/prefill/prefill.cpp:377-379`）。Strata のアーキテクチャ既定値処理は、対象となる一部の AMD RDNA3 / 統合 gfx11 構成で同変数を `1` に設定する経路も持ちます（`engine/include/strata/core/gfx11_extra.hpp:90-101`、`engine/src/core/arch_defaults.cpp:172-199`）。この既定値設定は `_CHECK` の値を変更しません。
- CUDA/HIP の prefill 経路は、`T >= max(STRATA_PF_SWITCH_MIN_T, hc_upmix_min_t())`、fused でないこと、low-part buffer がないこと、BF16-in-F32 の up weight であることを要求します。`STRATA_PF_SWITCH_MIN_T` の既定値は 0、CUDA の `hc_upmix_min_t()` は 33、HIP は 0 です。さらに CUDA/HIP 経路では `wu->q8_scale == nullptr` が必要です（`engine/src/prefill/prefill.cpp:975-996,5129-5130`）。
- CUDA の `gr_upmix` 実装は device compute capability major が 8 以上の場合に実行し、それ未満や判定失敗では `false` を返します。HIP 実装は gfx11 WMMA device 以外や `T <= 0` では `false` を返します（`engine/src/prefill/kernels.cu:2985-3016`）。
- SYCL prefill 側は `T >= STRATA_PF_SWITCH_MIN_T`（既定 0）、fused でないこと、low-part buffer がないこと、BF16-in-F32 の up weight であることを条件にします。CUDA/HIP 側の条件にある `wu->q8_scale == nullptr` と 33-token 下限はこの箇所にはありません（`engine/sycl/src/prefill/prefill.cpp:372-379,3462-3464`）。SYCL の `gr_upmix` 実装は `__HIPCC__` が定義された分岐で gfx11 device かつ `T > 0` の場合に kernel を起動し、それ以外の分岐は `false` を返します（`engine/sycl/src/prefill/kernels.dp.cpp:2454-2472`）。
- 値が正でも、これらの条件が満たされなければ診断カウンターは初期化されず、ログも出ません。CLI 引数による `_CHECK` の上書き・優先順位はこれらの読み取り箇所にはありません。

## 実行時の詳細

`std::getenv` と `atoi` は `STRATA_HC_UPMIX` が有効で、upmix の呼び出し条件を満たす分岐に初回到達した時に一度だけ評価されます。関数内 `static` のため、その後の環境変更はキャッシュに反映されません。正数 N なら eligible な layer / half の upmix 呼び出しのうち最初の N 回で、まず従来の BF16 projection と `gr_mix_r` を実行して `mixed` を参照値として作り、その後 `gr_upmix` の結果を同じ出力に書きます。比較用の GPU 出力を host にコピーして同期し、相対 RMS 差と最大絶対差を計算します（CUDA/HIP: `engine/src/prefill/prefill.cpp:5131-5149`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3464-3496`）。

比較した呼び出しの後も `gr_upmix` が成功すれば fused 結果を使います。失敗して `false` を返す場合、通常の up projection と mix に戻ります（CUDA/HIP: `engine/src/prefill/prefill.cpp:5150-5165`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3497-3509`）。N 回を使い切った後も `_CHECK` による比較だけが止まり、upmix 自体の選択条件は変わりません。

## ログと測定値

比較が実行された各回に stderr へ次の形式で出力します（実装: CUDA/HIP `engine/src/prefill/prefill.cpp:5147-5149`、SYCL `engine/sycl/src/prefill/prefill.cpp:3494-3496`）。

```text
strata: STRATA_HC_UPMIX_CHECK layer <layer> half <half> T <tokens>: mixed rel RMS <value>, max |diff| <value> (<upmix|upmix refused>)
```

`rel RMS` は `sqrt(sum((got-ref)^2) / max(sum(ref^2), 1e-30))`、`max |diff|` は最大要素絶対差です。N が 0 以下、未設定、または eligible な呼び出しがない場合、この比較ログは出ません。`docs/DETAILS.md:1288-1302` は `STRATA_HC_UPMIX=1` を CUDA sm_80+ の fused kernel として記載していますが、`STRATA_HC_UPMIX_CHECK` の測定結果や実行保証は記載していません。この調査では build・GPU 実行・性能測定を行っていません。

## 根拠

- 候補名の実参照は CUDA/HIP と SYCL の `std::getenv` 2 箇所で、いずれも `std::atoi` を使う: `engine/src/prefill/prefill.cpp:5131`、`engine/sycl/src/prefill/prefill.cpp:3464`。
- 有効化ゲートと CUDA/HIP・SYCL それぞれの条件: `engine/src/prefill/prefill.cpp:985-996,5127-5155`、`engine/sycl/src/prefill/prefill.cpp:372-379,3460-3509`。
- device に応じた実装可否と fallback 用 `false`: `engine/src/prefill/kernels.cu:2985-3016`、`engine/sycl/src/prefill/kernels.dp.cpp:2454-2472`。
- 機能説明との照合: `docs/DETAILS.md:1288-1302`。
