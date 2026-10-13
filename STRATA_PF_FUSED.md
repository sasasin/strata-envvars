# `STRATA_PF_FUSED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt prefill の routed expert 計算で、対応する形式・GPU のときに Strata 独自の int8 fused kernel を選ぶスイッチです。CUDA/HIP の `moe_fused` 経路は Q2_0 pack、`moe_fused_iq` 経路は対応する native IQ pack を扱います。値を有効にしても、通常の decode ではなく、下記の長い chunk の prefill 経路で条件が揃った layer に限って使われます。

このカーネルは MMQ/FP16 の計算と丸めが異なる場合があります。出力の数値が常に同一とは限りません。

## 値と判定

判定は文字列全体や数値としての parse ではなく、主に `getenv()` 結果の有無と先頭文字で行います。`enabled()`、`requested()`、`native_supported()` 内の `static` 値は初回評価後にプロセス内で保持されるため、その後の環境変更は反映されません。

| 経路 | 未設定 | 空文字 | 設定値の判定 |
|---|---|---|---|
| CUDA の Q2_0 fused kernel | 有効要求（既定 ON） | 有効要求 | 先頭文字が `0` なら無効、それ以外は有効要求。`0tail` は無効、`false` や `2` は有効要求 |
| HIP の Q2_0 fused kernel | 無効 | 無効 | 先頭文字が `1` のときだけ有効要求。`10` は有効、`true` や `0` は無効 |
| native IQ fused kernel（通常の対応デバイス） | 無効 | 無効 | 先頭文字が `1` のとき要求。その他は無効 |
| native IQ fused kernel（gfx12 の既定経路） | IQ3_S / IQ3_XXS の対応 layer だけ既定有効 | 未設定と同じ扱い | 空でない値の先頭文字が `1` なら、対応する全形式を要求。`0` で始まる値などそれ以外は無効 |

CUDA の Q2_0 判定では空文字の先頭 `\0` は文字 `'0'` ではないため有効要求です。一方、native IQ 判定では未設定と空文字を同じ既定値として扱います。いずれの経路も末尾文字や数値の妥当性は検査しません。

native IQ には別スイッチ `STRATA_PF_FUSED_NATIVE` もあります。これが先頭文字 `0` で始まる場合、`STRATA_PF_FUSED=1` でも native IQ fused 経路を無効にします。空文字や `false` はこの抑止条件になりません。

根拠: `src/prefill/moe_fused.cu:656-673`, `sycl/src/prefill/moe_fused.dp.cpp:945-962`, `src/prefill/moe_fused_iq.cu:1118-1139`, `sycl/src/prefill/moe_fused_iq.dp.cpp:1361-1367`。

## 有効になる条件

値判定で要求が有効でも、次の実行条件と実装対応が必要です。

- prefill の MoE layer であり、その layer が MMQ 対応 (`use_mmq`) または計画上 fused 専用 (`fused_only`) である。
- 全 expert を決まった順で stage する `stream_all` 経路である。通常は chunk サイズが `STRATA_PREFILL_STREAM_MIN` 以上（既定 1024 token）、リングが通常 staging 用の 8 slot より大きく、source がある場合に成立する。小さい chunk は MMQ または既存の別経路を使う。
- `--peer-device` による peer 経路ではない。peer-device が有効なら fused 経路を使わず MMQ を使う。
- デバイスと形式が kernel 対応範囲内である。Q2_0 fused `available()` は対応デバイスであることを追加確認する。CUDA の Q2_0 kernel は sm_80 以上を必要とし、sm_75 以下や sm_80+ の code object を含まない build では利用できない。
- native IQ は gate/up と down の組み合わせが `gu_covered()` / `d_covered()` に含まれる必要がある。対象外形式や layer は MMQ（または pack によって FP16 経路）に残る。

gfx12 (RDNA4) の HIP build では Q2_0 用 `available()` が false のままですが、native IQ の特別扱いがあります。`STRATA_PF_FUSED` が未設定または空なら、デバイス確認後に IQ3_S / IQ3_XXS の gate/up を既定有効にします。明示的な先頭 `1` は対応する native IQ 形式の opt-in 要求となり、`STRATA_PF_FUSED_NATIVE=0` はそれを止めます。gfx12 以外の HIP では未設定時に既定有効とはならず、native IQ も明示 opt-in が必要です。

根拠: `src/prefill/prefill.cpp:2945-2961`, `sycl/src/prefill/prefill.cpp:3218-3234`, `src/prefill/moe_fused.cu:651-673`, `src/prefill/moe_fused_iq.cu:1123-1139`。ビルド上の CUDA/HIP kernel 組み込み箇所: `CMakeLists.txt:1361-1364,1428-1434`。

## 実行時の詳細

`moe_fused::enabled()` は Q2_0 経路の値判定後に `available()` を確認します。native IQ 経路は `native_supported()` でスイッチ、形式対応、デバイス情報を確認します。prefill loop は layer ごとに `fused_l` を決め、実行時には layer input を int8 化し、router の expert IDs を GPU 上で group 化し、stage ring 上の expert blob を使って gate/up、SwiGLU、down の処理を行います。fused path に入った最初の実行では stderr に次の行を一度出します。

```text
strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)
```

実装には CUDA と SYCL 用の同等の判定・dispatch があり、HIP build は fused source の HIP 分岐を使います。判定 static のため、変数はその判定関数が初めて呼ばれる時点で実質固定されます。子プロセスへの転送や上書きは、このスイッチについての該当処理を確認できませんでした。

根拠: `src/prefill/prefill.cpp:2952-2961,2987-2997`, `sycl/src/prefill/prefill.cpp:3225-3234,3250-3260`, `src/prefill/moe_fused.cu:656-673`。

## 文書との照合

`docs/DETAILS.md` は CUDA RTX 30 世代以降で Q2_0 fused kernel を説明し、`STRATA_PF_FUSED=0` で従来 prompt kernel を選び、`=1` で native IQ pack も opt-in できると記載しています（`docs/DETAILS.md:22-28`）。また gfx12 の native IQ3_S / IQ3_XXS は既定 ON、`=0` で無効と説明しています（`docs/DETAILS.md:1945`）。これは現行 native IQ 判定と一致します。

資料の測定例として、`docs/DETAILS.md:22-28` は同一 PC の Q2_0 prompt で 4K 1,294→1,570、32K 2,170→2,653 tokens/s 等を報告しています。gfx12 の測定は同ファイル 1945 行に R9700 での prompt 4K +15.7%、16K +13..+17%、32K +19..+20% とあります。いずれも各資料記載の条件での値で、他デバイスの結果を保証するものではありません。

一方、`docs/STRIX_HALO.md:108-125` は gfx1151 の native fused kernels を opt-in と説明し、chunk の既定下限 1,024 と K-quant 用 `STRATA_PF_FUSED_KQ` 条件を記載しています。これらはコード上の dispatch 条件と整合します。`docs/AMD_HIP.md:349-361` は現行 gfx12 の扱いと opt-in の数値差も説明しています。古い版または周辺コメントの「HIP は MMQ」の記述だけでは現行挙動を表さず、本調査では分岐を含む実装を根拠にしました。

## 根拠

- 判定と device availability: `src/prefill/moe_fused.cu:651-673`, `sycl/src/prefill/moe_fused.dp.cpp:940-962`。
- native IQ の対象形式と gfx12 既定: `src/prefill/moe_fused_iq.cu:1076-1089,1118-1139`; SYCL の通常 opt-in 判定: `sycl/src/prefill/moe_fused_iq.dp.cpp:1361-1367`。
- dispatch と fused 計算の呼び出し: `src/prefill/prefill.cpp:2952-2961,2987-2997`; SYCL: `sycl/src/prefill/prefill.cpp:3225-3234,3250-3260`。
- stream-all の token 下限（通常 1024）: `src/prefill/prefill.cpp:141-151`; SYCL: `sycl/src/prefill/prefill.cpp:116-121`。
- 関連資料: `docs/DETAILS.md:22-28,1945`, `docs/STRIX_HALO.md:100-125`, `docs/AMD_HIP.md:349-361`。
