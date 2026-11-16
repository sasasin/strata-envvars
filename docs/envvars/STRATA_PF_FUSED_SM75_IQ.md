# `STRATA_PF_FUSED_SM75_IQ`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA の sm_75 (Turing) で使う Strata の fused int8 prompt-expert kernels のうち、i-quant gate/up と IQ4_NL down の setup を抑止する診断スイッチです。`STRATA_PF_FUSED_SM75_IQ` が無効判定なら、この i-quant 群を `DevInfo::t75_set` に登録しません。既定では抑止されず、setup が成功した形式は `native_supported()` の対象になり得ます。Turing の Q2_0 / Q2_0 pair の setup はこの変数の対象外です。`src/prefill/moe_fused_iq.cu:119-127,2432-2444,2707-2711`。

この変数だけでは Turing kernels を有効にしません。CUDA の同じ device-info 判定で `STRATA_PF_FUSED_SM75=1` が必要で、さらに native pack の実行には `STRATA_PF_FUSED=1`（または small-card prompt path の fused-kernels-only override）が必要です。対応する i-quant pair が使えない場合、その層は native fused 経路を通らず MMQ（場合により FP16 path）側に残ります。`src/prefill/moe_fused_iq.cu:2428-2437,2891-2908,3034-3039`; `src/prefill/prefill.cpp:5406-5407,5436-5441`。

## 値と判定

CUDA 実装は `std::getenv` の戻り値が null でないことと、先頭文字が `'0'` かだけを調べます。文字列全体の比較、数値変換、大文字小文字の処理はありません。`src/prefill/moe_fused_iq.cu:2435-2437`。

| 条件 | unset | i-quant setup を実行する値 | setup を抑止する値 |
|---|---|---|---|
| CUDA で sm_75 と判定され、Turing 分岐に到達 | 抑止しない | 空文字、`1`、`true`、`false`、` 0` など、先頭が `0` 以外の文字列 | `0`、`0anything`、`00` など、先頭が `0` の文字列 |
| HIP build、CUDA の sm_75 opt-in 不成立、または sm_75 以外 | この変数を読み取らない／効果なし | 該当なし | 該当なし |

`false` や `0anything` も文字列全体として解釈せず、先頭文字だけで判定します。環境変数が空文字なら設定済みですが、空文字の先頭 `\0` は `'0'` ではないため抑止されません。`STRATA_PF_FUSED_SM75=1` 側は別判定で、先頭文字が `'1'` のときだけ Turing 経路を通します。`src/prefill/moe_fused_iq.cu:2428-2437`。

## 有効になる条件

- CUDA build であること。HIP 側は `dev_info()` の HIP 分岐から戻り、この変数の読み取り箇所（CUDA 側の `#else`）に進みません。`src/prefill/moe_fused_iq.cu:2390-2416,2417-2444`。
- 現在の device が compute capability 7.5 で、`STRATA_PF_FUSED_SM75` の先頭文字が `1` であること。満たさない場合 `dev_info()` は Turing の setup 前に戻ります。`src/prefill/moe_fused_iq.cu:2428-2434`。
- Q2_0 gate/up と down の `setup_one` が成功し、`d.ok` が true であること。失敗すると i-quant setup 群は実行されません。`src/prefill/moe_fused_iq.cu:2432-2438`。
- IQ が抑止されない場合でも、setup 対象は `kT75Formats` に定義された IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S / IQ4_XS の gate/up と IQ4_NL down に限られます。各 setup は WW=2 の kernel が使えることを必要とし、WW=4 は追加で使用可能な場合だけ登録されます。`src/prefill/moe_fused_iq.cu:119-127,2307-2317,2437-2441`。
- 実際の native pack 経路には、`STRATA_PF_FUSED=1` または fused-kernels-only override も必要です。`STRATA_PF_FUSED_NATIVE=0` は `native_supported()` を早期に false にします。`src/prefill/moe_fused_iq.cu:2891-2908,3034-3039`; `src/prefill/moe_fused.cu:723-729`。
- Qwen3.6 用にも同じ実装を shape override 付きで include しています。CUDA target は通常版と Qwen3.6 版の両方を `strata_pf_own` に含めます。したがって両方の native kernel copy で同じ環境変数判定が使われます。`src/prefill/moe_fused_iq_q36.cu:32-38`; `cmake/backends/cuda.cmake:114-118`。
- `STRATA_PF_FUSED_SM75_IQ` を読む CLI 引数、別名 helper、子プロセスへの転送は見つかりませんでした。完全一致検索で確認できた実装上の読み取りは `src/prefill/moe_fused_iq.cu:2436` のみです。

## 実行時の詳細

`dev_info()` は device ごとの `g_dev` に判定結果を保存し、`done` が立った後は同じ device について再評価しません。IQ 抑止値も関数内 `static const bool` で、CUDA の Turing 分岐が初めて実行されたときに評価され、そのコンパイル済み copy 内で以後キャッシュされます。したがってプロセス実行中に環境を変更しても、この判定結果は更新されません。Qwen3.6 copy は同じ `.cu` を include して別 namespace と shape でコンパイルされるため、そちらにも別の static 判定があります。`src/prefill/moe_fused_iq.cu:2379-2385,2432-2437`; `src/prefill/moe_fused_iq_q36.cu:32-38`。

抑止されていないとき、`t75_setup()` は各対応形式で WW=2 の setup が成功した場合に `t75_set` を立て、WW=4 も成功した場合は `t75_w4` に記録します。IQ が抑止されるとこれらの i-quant bit は立たず、`t75_pair_ok()` は i-quant pair を false とします。native dispatch は `native_supported()` で判断され、prefill 側では対応しない native pair は MMQ（IQ1_M など一部は FP16 path）に残ります。`src/prefill/moe_fused_iq.cu:2307-2317,2707-2718,3034-3039`; `src/prefill/prefill.cpp:5406-5407,5436-5441`。

他の環境変数との関係は次のとおりです。

- `STRATA_PF_FUSED_SM75=1` は Turing の device-info 分岐自体を許可します。未設定または先頭文字が `1` 以外なら、この変数の値にかかわらず sm_75 は早期 return します。`src/prefill/moe_fused_iq.cu:2428-2434`。
- `STRATA_PF_FUSED=1` は native pack kernels の利用要求です。unset はこの CUDA の `requested()` では要求扱いにならず、Turing の IQ kernels をこの変数だけで有効化しません。small-card override はこの条件を変え得ます。`src/prefill/moe_fused.cu:723-729`; `include/strata/prefill/pf_fused_override.hpp:21-24`; `src/prefill/moe_fused_iq.cu:2901-2908,3038-3039`。
- `STRATA_PF_FUSED_NATIVE=0` は native pack を `native_supported()` から除外するため、IQ setup が成功していても native pack の実行を止めます。`src/prefill/moe_fused_iq.cu:2891-2908`。

## ログと測定値

この変数を読んだこと、IQ setup を抑止したこと、setup 失敗の理由を出す専用ログはありません。setup API の失敗は false として扱われ、WW=2 が失敗した形式は `t75_set` に登録されず、通常の native eligibility 判定から外れます。Turing の `dev_info()` は最後に `cudaGetLastError()` を呼びますが、その戻り値をこの箇所では報告しません。`src/prefill/moe_fused_iq.cu:2289-2317,2437-2444`。

後続の kernel launch が CUDA error を返した場合は、`ck()` が `prefill fused experts (native): <処理名>: <CUDA error>` を stderr に出して終了コード 1 で終了します。これは起動時の IQ 抑止を示すログではありません。`src/prefill/moe_fused_iq.cu:60-65,3242`。この変数について条件付き測定値は確認できませんでした。`docs/DETAILS.md:1153-1163` は Turing kernels が opt-in であることを記載していますが、この変数自体の測定結果は載せていません。

## 根拠

- 直接の環境読み取りと i-quant setup 条件: `src/prefill/moe_fused_iq.cu:2432-2444`
- 対象形式と setup 成功条件: `src/prefill/moe_fused_iq.cu:119-127,2289-2317`
- Turing pair eligibility: `src/prefill/moe_fused_iq.cu:2707-2718,3034-3039`
- native pack の prompt 経路と fallback: `src/prefill/prefill.cpp:5401-5407,5436-5441`
- Qwen3.6 への include と CUDA library 登録: `src/prefill/moe_fused_iq_q36.cu:32-38`; `cmake/backends/cuda.cmake:114-118`
- Turing kernels の文書上の opt-in 注記: `docs/DETAILS.md:1153-1163`
