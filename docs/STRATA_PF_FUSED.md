# `STRATA_PF_FUSED`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの動作は対象外。

## 役割

prompt の MoE expert 計算に、Strata の fused int8 カーネルを使うか選びます。Q2_0 pack の経路と native GGUF IQ pack の経路は同じ環境変数を参照しますが、既定値と GPU 条件が異なります。カーネルを選ぶと、router の expert ID の GPU grouping、token 単位の activation quantize、expert blob の batch 処理を行います。該当しない layer や条件では既存の MMQ（または pack によって FP16）経路に進みます。

## 値と判定

文字列全体や数値としての parse はせず、各読み取り箇所で先頭文字を比較します。空文字は `getenv()` 上は設定済みですが、`v[0]` は `\0` です。

| 経路 | unset | 空文字 | 先頭文字 `0` | 先頭文字 `1` | その他の先頭文字 |
|---|---|---|---|---|---|
| Q2_0 `enabled()`（CUDA / SYCL） | 有効要求 | 有効要求 | 無効 | 有効要求 | 有効要求 |
| Q2_0 `enabled()`（HIP） | 無効 | 無効 | 無効 | 有効要求 | 無効 |
| native pack `native_supported()`（CUDA、HIP gfx11、SYCL） | 無効 | 無効 | 無効 | 有効要求 | 無効 |
| native pack `native_supported()`（HIP gfx12） | IQ3_S / IQ3_XXS の既定対象 | IQ3_S / IQ3_XXS の既定対象 | 無効 | 明示 opt-in | 無効 |

「有効要求」は、その後の `available()` / `dev_info()`、format 対応、prompt 条件も満たす必要があります。Q2_0 と native pack の各判定は関数内の `static` に保存されるため、その判定を最初に実行した後でプロセス環境を変えても再評価されません。HIP gfx12 の native 判定では unset と空文字を同じ既定扱いにしますが、先頭が `0` の値は明示的な無効です。

## 有効になる条件

- **Q2_0 pack:** `fused::enabled()` が真で、device の `available()` 判定を通ること。CUDA 実装は compute capability major が 8 未満なら利用不可とし、カーネル属性・occupancy の検査も行います。HIP 実装は gfx11 WMMA kernel の利用可否を検査します。SYCL 実装にも `enabled()` と同様の値判定と device 可用性検査があります。
- **native pack:** gate/up と down の format の組がカーネルの対応範囲内で、device probe を通ること。基本対応は gate/up の IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S / IQ4_XS と down の Q2_0 / IQ4_NL です。HIP gfx11 では `STRATA_PF_FUSED_KQ=1` のとき gate/up Q4_K / Q5_K と down Q5_1 / Q8_0 も対応します。`STRATA_PF_FUSED_NATIVE=0` は CUDA / HIP / SYCL の native 実装で native 経路を無効にします。
- **prompt 経路:** expert source があり、ring が staging 数 8 より大きく、chunk が `stream_all_min()` 以上で全 expert の streaming を行うこと。既定の閾値は 1024 tokens です（`STRATA_PREFILL_STREAM_MIN` で変更可能。CUDA の CPU-share 経路では別の閾値が設定される場合があります）。multi-GPU peer 経路は fused path を使いません。
- Q2_0 は MMQ plan の該当 layer である必要があります。native pack は MMQ layer または `fused_only` layer で、native format が対応している必要があります。対応しない native layer は MMQ（IQ1_M 等は FP16 path）に残ります。

したがって、変数を有効値にしても短い chunk、expert source がない構成、小さい ring、peer-device を使う構成、device / format が未対応の場合には fused kernels は実行されません。

## 実行時の詳細

Q2_0 の `enabled()` は CUDA / SYCL では unset を既定有効とし、値の先頭が `0` の場合だけ無効にします。HIP では先頭が `1` の場合だけ有効です。native pack の `requested()` は全体比較ではなく先頭が `1` かを調べます。HIP gfx12 の `native_supported()` には例外があり、`STRATA_PF_FUSED` が unset または空文字なら、対応 device で IQ3_S / IQ3_XXS の gate/up に限り既定で native kernels を許可します。他の native format は明示的な先頭 `1` が必要です。gfx12 は Q2_0 側の fused kernel がないため、Q2_0 pack がこの例外で有効になるわけではありません。SYCL の native 判定は `requested()` を要求し、gfx12 用の自動既定分岐はありません。

実行時に fused path を選んだ layer では、一度だけ stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を出します。router の ID を GPU 上で grouping し、activation を int8 化してから expert を処理します。したがって host grouping の同期を避ける経路ですが、MMQ と同じ計算ビット列になる保証はありません。資料は native fused path の丸めが MMQ と異なることを明記しています。ログが出ない場合も、環境変数の値だけでなく prompt chunk / streaming / device / format 条件によって経路が選ばれていない可能性があります。

`docs/DETAILS.md` は gfx12（RDNA4）で IQ3_S / IQ3_XXS に限り既定有効と記載し、R9700 で測った prompt の向上値を報告しています。これは同資料の記載条件での測定であり、他 GPU や設定での性能を示すものではありません。一般の native pack について同資料は `=1` を opt-in と説明しており、gfx12 の既定は例外です。`docs/AMD_HIP.md:357-369` には gfx12 の opt-in とする説明も残っていますが、この HEAD の分岐と `DETAILS.md:2028` の記述には一致しません。ここでは現行ソースの判定を記載しました。

## 根拠

- `src/prefill/moe_fused.cu:651-673`, `sycl/src/prefill/moe_fused.dp.cpp:940-962`: Q2_0 経路の `built` / `available` / `enabled` / `requested` と環境値判定。
- `src/prefill/moe_fused_iq.cu:1023-1063,1118-1139`, `sycl/src/prefill/moe_fused_iq.dp.cpp:1174-1212,1361-1367`: device probe、native format 判定、HIP gfx12 の既定条件、SYCL の native opt-in 判定。
- `src/prefill/moe_fused_iq.cu:1067-1089`, `sycl/src/prefill/moe_fused_iq.dp.cpp:1214-1235`: native kernels の対応 format と `STRATA_PF_FUSED_KQ` による HIP の追加 format。
- `src/prefill/prefill.cpp:158-168,2341,3030-3039,3065-3075`, `sycl/src/prefill/prefill.cpp:117-123,2462,3223-3232,3248-3258`: stream 閾値、peer / MMQ / format 条件、fused path の起動・ログ。
- `docs/DETAILS.md:22-28,2028`: Q2_0 の既定、native pack の opt-in 説明、および gfx12 の IQ3_S / IQ3_XXS 既定と R9700 測定の記載。
- `docs/AMD_HIP.md:357-369`: HIP native kernels と `STRATA_PF_FUSED_NATIVE=0`、測定条件に関する記載。
