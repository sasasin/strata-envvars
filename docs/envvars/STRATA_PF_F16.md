# `STRATA_PF_F16`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の gfx11 向け fused prefill expert 経路で、対応する expert の計算を int8 kernel から F16 重み・F16 matrix core kernel に切り替えます。これは prompt の routed expert 計算に対する選択で、decode や全 prefill kernel を切り替える設定ではありません。F16 kernel は対応する重みを F16 に変換して積和するため、int8 kernel と丸め結果が異なります。

## 値と判定

`moe_f16_common.cuh` の `requested()` が `std::getenv("STRATA_PF_F16")` を読み、値の先頭文字が `'1'` かだけを判定します。文字列全体の parse、大文字小文字変換、数値検査はありません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効（先頭文字は `\0`） |
| `1`、`10`、`1anything` | 有効 |
| `0`、`true`、空白始まりの値など、先頭文字が `1` 以外 | 無効 |

判定結果は関数内の `static const bool` に初回評価時に保存されます。同一プロセスでその後に環境を書き換えても再評価されません。環境変数自身について専用のログ出力は見つかりませんでした。

## 有効になる条件

- fused native expert の prefill 経路に到達する必要があります。呼び出し元では `stream_all`、peer device を使わないこと、native expert layout、および対象 layer の形式が native fused 対応であることを確認します。expert の fused 経路は、全 expert の配置が routing 前に分かる streamed walk で使われ、より短い chunk は通常 MMQ 経路になります（`src/prefill/prefill.cpp:3366-3382`）。
- gfx11 の HIP build と、その build が対象 gfx11 device 向けの実 kernel を含むことが必要です。device 判定は gfx11/gfx12 WMMA arch と kernel body を確認し、gfx906 はこの native kernel 経路から外します（`src/prefill/moe_fused_iq.cu:1251-1286`）。F16 kernel の本体も `__HIPCC__` と gfx1100/1101/1102/1150/1151 の場合だけ有効です（`src/prefill/moe_f16_common.cuh:38-43,79-85`）。
- gfx11 で native fused 経路を有効にするには、通常 `STRATA_PF_FUSED=1` も必要です。`native_supported()` は `STRATA_PF_FUSED` が明示的に `1` でなければ gfx11 では false を返し、`STRATA_PF_FUSED_NATIVE=0` は native fused path を止めます（`src/prefill/moe_fused_iq.cu:1386-1408`; `src/prefill/moe_fused.cu:679-695`）。
- gfx12 では `STRATA_PF_FUSED` の既定 native 対応が IQ3_S / IQ3_XXS gate/up に限られ、`native_supported()` が F16 要求なしで true になり得ます。ただし `experts_native()` は gfx12 (`d.w12`) では F16 分岐を選ばず、int8 native kernel を使います（`src/prefill/moe_fused_iq.cu:1391-1408,1454-1457`）。

形式の対応範囲は gate/up と down で別です。

| 対象 | gfx11 の対応形式 |
|---|---|
| gate/up | IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、IQ4_XS |
| gate/up（`STRATA_PF_FUSED_KQ=1` も必要） | Q4_K、Q5_K |
| down | Q2_0、IQ4_NL、Q8_0 |
| down（`STRATA_PF_FUSED_KQ=1` も必要） | Q5_1 |

Q8_0 down は gfx11 で `STRATA_PF_F16=1` のとき native F16 coverage に含まれます。Q4_K/Q5_K gate/up と Q5_1 down は `STRATA_PF_FUSED_KQ=1` も必要です（`src/prefill/moe_fused_iq.cu:1316-1353,1463-1497`）。対応形式の一方が欠ける場合、その形式については通常の native int8 kernel 側へ進みます。

## 実行時の詳細

fused native 経路の `experts_native()` は gfx11 で `f16::requested()` を見て F16 分岐を選びます。対応 gate/up 形式なら `native_f16_kernel` または K-quant 専用の `f16kq::gate_up()`、対応 down 形式なら `native_f16_kernel` または `f16kq::down()` を起動し、それ以外は既存の `native_w11_kernel` を起動します。F16 kernel の work item 幅は既定で expert あたりの平均行数に応じて 64 行または 128 行を選びます（`src/prefill/moe_f16_common.cuh:62-74`; `src/prefill/moe_fused_iq.cu:1451-1499`）。

`STRIX_HALO.md` は、この切り替えが int8 kernel と異なる丸めになると説明しています。同資料では Ryzen AI Max+ 395 / gfx1151、16,384 token の記載値として、Q4_K / Q5_1 の1 layerが 85.3→53.5 ms、IQ3_S / IQ4_NL の gate/up が 11.65→9.87 ms、down が 6.11→4.71 ms と報告されています。これらは資料に記載された特定構成の測定値で、一般的な性能保証ではありません（`docs/STRIX_HALO.md:128-134`）。

## 根拠

- `src/prefill/moe_f16_common.cuh:38-59` — 対応 device guard と環境変数の parse / static cache。
- `src/prefill/moe_fused_iq.cu:1323-1353,1386-1408` — 対応形式、K-quant 条件、native fused 経路の gate。
- `src/prefill/moe_fused_iq.cu:1451-1501` — 実際の F16 kernel 選択と int8 fallback。
- `src/prefill/prefill.cpp:3366-3382` — streamed prefill と peer device に関する fused 経路の条件。
- `docs/STRIX_HALO.md:128-134` — 設計資料の説明と条件付き測定値。
