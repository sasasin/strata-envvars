# `STRATA_PF_XMX`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリや GPU ドライバーが独自に読む環境変数は対象外。

## 役割

SYCL の prompt prefill における MoE expert GEMM で、XMX（Intel GPU matrix engine）を使う grouped GEMM の経路を選びます。`0` は無効、`1` は expert 重みを FP16 に dequantize してから grouped XMX GEMM を使い、`2` は対応する native 量子化形式について重みの IQ decode もまとめた fused grouped XMX GEMM を使います。これは SYCL prefill 専用の選択で、CUDA/HIP や decode の XMX 選択ではありません。

## 値と判定

`sycl/src/prefill/xmx_moe.dp.cpp` の `mode()` が `std::getenv` で一度読み、`atoi` で整数に変換します。結果は関数内の `static const int` に保存されるため、最初の呼び出し後にプロセスの環境を変えても再評価されません。

| 環境値 | `atoi` の結果と処理 |
|---|---|
| 未設定 | `0`。XMX grouped 経路を選ばない。 |
| 空文字、数値に変換できない文字列（例 `true`） | `0`。無効。 |
| 数値の先頭部分が `1`（例 `1`, `01`, `1abc`） | `1`。dequantize 後の grouped XMX 経路。 |
| 数値の先頭部分が `2`（例 `2`, `2abc`） | `2`。条件を満たす native 形式の fused grouped XMX 経路。 |
| それ以外の非ゼロ整数（例 `3`, `-1`） | 値自体は保持されるが、prefill 側の `== 1` / `== 2` 判定に一致せず、これらの grouped XMX 経路には入らない。 |

`atoi` のため文字列全体の妥当性は検証しません。空白や符号を含む入力は `atoi` の整数変換規則に従います。値域エラーの警告や clamp はありません。

## 有効になる条件

- SYCL prefill の expert 計算で MMQ 経路が選ばれていないこと。両モードとも expert 計算の MMQ 分岐からは先に戻るため、その経路では使われません。
- モード `1` は通常の FP16 expert 計算経路で、expert 重みを FP16 に dequantize した後に使われます。grouped XMX に渡す expert 数は最大16です。gate/up の平均 row 数 `nr / ng` が `STRATA_PF_XMX_GU_MAX` 未満の場合に gate/up の grouped XMX GEMM を実行し、閾値以上では gate/up を expert ごとの通常 FP16 GEMM にします。どちらの場合も、この分岐では down projection に grouped XMX GEMM を使います。
- モード `2` は `!use_mmq` に加えて `lay.native` であること、gate/up type が `18, 21, 22, 23` のいずれか、down type が `20, 42` のいずれかを要します。条件を満たさない layer は従来の計算経路です。モード `2` の判定には `stream_all` 条件は直接含まれていません。
- カーネルはビルド時の XMX subgroup 形状に依存します。通常の subgroup-8 build は Battlemage を実行時に検出すると無効化され、AOT subgroup-16 build は `STRATA_SYCL_AOT` が `bmg` または `lnl` で始まる場合に CMake が `STRATA_XMX_SG16` を定義します。`STRATA_NO_DG2_XMX` が定義された build では無効です（CMake は `pvc` AOT build でこの macro を定義）。

## 実行時の詳細

モード `1` では、expert ごとに gate/up と down の量子化重みを FP16 に dequantize し、最大16 expert をまとめます。grouped XMX kernel は平均 row 数が96未満なら小さい tile、そうでなければ大きい tile を使います。gate/up のみ `STRATA_PF_XMX_GU_MAX` で grouped 実行を選別します。down projection は `grouped_f16` を呼び出します。最初にこの経路を通ったとき、stderr に `strata: prompt experts on the grouped XMX GEMM (STRATA_PF_XMX=1)` を出します。

モード `2` では、対応する native expert blob を最大16個保持してまとめ、grouped kernel 内で IQ 重みを decode します。各 group の gate/up row 平均が `STRATA_PF_XMX_ROWS` 未満なら fused grouped XMX kernel、そうでなければ expert ごとの dequantize と FP16 GEMM を使います。後者では gate/up と down の両方を expert ごとに処理します。非対応 layer では最初の該当時に `strata: STRATA_PF_XMX=2 not taken at layer ...` の診断を stderr に一度出し、対応 layer では `strata: prompt experts on the fused grouped XMX (STRATA_PF_XMX=2)` を一度出します。

通常 build で Battlemage を検出した場合は、非ゼロ要求に対し `STRATA_PF_XMX ignored: this build has the sub-group 8 / 8x8x16 kernels (Arc A-series); Battlemage needs the AOT bmg build` と stderr に出してモードを0にします。`STRATA_NO_DG2_XMX` build では `STRATA_PF_XMX ignored: this build is AOT for a device without the sub-group 8 XMX kernels` と出して0にします。いずれも `mode()` の static 初期化時に判定されます。

## 根拠

- 環境変数の読み取り、`atoi`、default、build/device guard、static cache: `sycl/src/prefill/xmx_moe.dp.cpp:148-175`。
- build 時の subgroup macro とAOT対象: `sycl/CMakeLists.txt:31-50`。
- grouped XMX の expert 上限および各モードの説明: `include/strata/prefill/xmx_moe.hpp:5-19`。
- staging/dequant ring の拡張、mode 2 のformat条件、行数閾値、ログ、実際の計算分岐: `sycl/src/prefill/prefill.cpp:229-234,3945-4014,4072-4141`。
- docs との照合: `docs/INTEL.md:831-833` は Battlemage で `STRATA_PF_XMX=1/2` を試し、同資料のカードでは通常より11–15%遅かったと記載しています。これはそのカードでの記録であり、他のGPUや条件に一般化できる性能値ではありません。
