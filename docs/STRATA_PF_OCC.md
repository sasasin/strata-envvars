# `STRATA_PF_OCC`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリやGPUドライバーが読む環境変数の動作は含めない。

## 役割

HIP版の融合prefill expertカーネルで、WGP（gfx11では2 CUをまとめた単位）あたりの永続グリッドのブロック数を上書きする実験用設定です。対象カーネルは複数のwork itemをグリッド内の各ブロックが繰り返し処理するため、ここで指定する数は処理タイル数そのものではなく、同時に用意するブロック数の上限です。

この変数は `STRATA_PF_FUSED` などにより融合prefill経路が選ばれた後のグリッド計算に関与します。CUDAビルドでは読み取られません。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果が正の場合に限り指定値を使います。文字列全体の妥当性検査や範囲 clamp はありません。

| 値 | ブロック数/WGP |
|---|---|
| 未設定 | occupancy query の値を使い、`2 * max(occ, 1)` |
| 正の整数に変換される文字列 | 変換された整数 |
| 空文字、非数値、ゼロ、負数 | 既定計算 `2 * max(occ, 1)` |

`atoi` のため、たとえば `3tail` は `3`、`tail3` は `0` として扱われます。先頭の空白と符号は `atoi` の整数変換規則に従います。大きすぎて `int` に収まらない値の結果は移植可能な動作として保証されないため、利用可能な上限値とはみなしません。

指定値はグリッド上限の計算に使われ、各launchの実際のgridは `min(タイル数に基づく上限, multiprocessor数 × 指定ブロック数)` です。したがって小さいworkloadでは指定値までブロックが作られないことがあります。

## 有効になる条件

- `__HIPCC__` でコンパイルされた経路であること。CUDA側の occupancy grid は `d.sms * d.occ_*` で計算され、`STRATA_PF_OCC` の参照はありません。
- 対象の融合expertカーネルが実行されること。HIP側の `moe_fused` はgfx11 WMMA経路であり、IQの融合経路も対応するgfx11/gfx12 native kernel等が利用可能であることを確認してから呼ばれます。
- IQ native経路では、型によって `occ_gu` / `occ_d` が真になる場合、グリッド上限は `STRATA_PF_OCC` ではなく `occ_blocks(...)` の値で決まります。現在のコードではgate/upのIQ2・IQ3・IQ4_XSと、downのQ2_0・Q8_0・IQ4_NLが該当し、`STRATA_PF_OCC_W` の正値による上書きがなければ、通常は4、gfx12のgate/up IQ2_S・IQ2_XSは3です。`STRATA_W_NO_OCC` ビルドではこれらの専用variantを無効にするため、`wgp_blocks()` 側の設定が使われます。
- `STRATA_PF_FUSED` 等によって該当形式とデバイスで融合prefill自体が有効にならなければ、この値は実行結果に影響しません。通常のMMQなど別経路のgrid設定には使われません。

## 実行時の詳細

各ファイルの `wgp_blocks()` 内で関数ローカル `static const` として最初の呼び出し時に一度読みます。そのプロセスで初回評価した後に環境を書き換えても再評価されません。値はexpert計算のgate/upとdownのgrid計算に渡されます。CPU側のgrouping gridや活性値のquantize gridには使われません。

通常の融合経路ではoccupancy queryが返すactive block数を2倍してWGPあたりの上限にします。ソースコメントは、このqueryがgfx11のWGPをmultiprocessorとして数えた際に、実際に並行実行できる2ブロックに対して1と報告する問題への補正と説明しています。コメント記載のgfx1151実験（20 WGP、8192 tokens、top 10、IQ3_S / IQ4_NL、1 layer）では、1/2/3/4 blocks per WGP の時間がそれぞれ60.7/44.7/49.9/45.2 msで、work itemと演算は同じと記録されています。これはソースコメント中の特定実験記録であり、他のGPUやモデルでの速度を示すものではありません。

設定値による診断ログはありません。カーネル起動エラーがあれば各実装の通常のCUDA/HIPエラーチェック経路で扱われます。

## 根拠

- `src/prefill/moe_fused.cu:581-594` — HIP限定の環境読み取り、正値の採用、既定値、gfx1151実験コメント。
- `src/prefill/moe_fused.cu:606-622,652-673,705-725` — HIPデバイスのgfx11 WMMA適格性確認、融合経路の選択条件、WGP単位のgrid上限計算。CUDA側は別のgrid計算。
- `src/prefill/moe_fused_iq.cu:988-1015` — IQ用 `wgp_blocks()` と、occupancy variant用の別設定 `STRATA_PF_OCC_W`。
- `src/prefill/moe_fused_iq.cu:1027-1050,1067-1139,1148-1200` — HIP native kernelの適格性確認、融合経路の条件、型によるoccupancy variant選択とgrid計算。
- `docs/DETAILS.md`、`docs/AMD_HIP.md`、`docs/STRIX_HALO.md` — `STRATA_PF_OCC` の値規則や独立した利用者向け説明は確認できなかった。性能値の記載には上記ソースコメントのgfx1151実験記録だけを用いた。
