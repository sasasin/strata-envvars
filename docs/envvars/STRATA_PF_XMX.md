# `STRATA_PF_XMX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

SYCL の prompt prefill における MoE expert の gate/up・down 積和を、グループ化した XMX 行列演算で処理する経路を選びます。`1` は expert を FP16 に dequantize してから grouped XMX GEMM を実行し、`2` は IQ expert の decode と積和を融合した grouped XMX 経路を選びます。値 `2` の既定有効対象は Intel Alchemist です。decode 経路や CUDA/HIP/Metal の実装ではこの変数を読みません。

## 値と判定

`mode()` の初回呼び出し時に `std::getenv` で読み、設定値は `std::atoi` で整数化します。設定値の文字列全体の検証はありません。

| 環境値 | Alchemist | その他の GPU 世代 |
| --- | --- | --- |
| 未設定 | `2` | `0` |
| `0` に変換される値（`0`、空文字、非数値文字列など） | `0` | `0` |
| `1` に変換される値（例: `1`, `1tail`） | `1` | `1` |
| `2` に変換される値（例: `2`, `2tail`） | `2` | `2` |
| その他の整数値（負数を含む） | その整数値 | その整数値 |

`atoi` が先頭の空白・符号と数値 prefix を解釈するため、後続の文字は無視されます。空文字および数値 prefix のない文字列は `0` 相当です。範囲外整数の変換結果はこの実装で検査・制限していません。`mode()` は値を `0` と `1`/`2` で比較するため、それ以外の非ゼロ値は `1` または `2` の経路を有効にしません。`--` 引数や他の設定値でこの値を上書きする処理は見つかりません。

## 有効になる条件

- 変数を読むのは SYCL prefill 実装です。Alchemist では未設定時に mode 2、Battlemage や世代不明では未設定時に mode 0 です。明示値はこの既定値を置き換えます。
- `mode() != 0` でも、AOT build に `STRATA_NO_DG2_XMX` が定義されていると mode 0 に戻り、stderr に `STRATA_PF_XMX ignored: this build is AOT for a device without the sub-group 8 XMX kernels` と出します。
- `STRATA_XMX_SG16` のない build で実行 GPU が Battlemage の場合も mode 0 に戻り、stderr に `STRATA_PF_XMX ignored: this build has the sub-group 8 / 8x8x16 kernels (Arc A-series); Battlemage needs the AOT bmg build` と出します。AOT `bmg` / `lnl` build は sub-group 16 形状を選びます。
- mode 1 の prefill 経路は expert 単位の処理をまとめ、最大 16 expert の group を処理します。gate/up は group の平均 rows/expert が `STRATA_PF_XMX_GU_MAX` 未満の場合に grouped XMX を使い、既定は 250。しきい値以上なら gate/up は通常の FP16 GEMM に戻ります。down は grouped XMX を使います。
- mode 2 は `!use_mmq` かつ native pack で、gate/up と down の形式が対象形式（GYRO trellis の組、または IQ3_XXS / IQ3_S / IQ2_S / IQ4_XS と IQ4_NL / Q2_0 の組）に合う場合に fused XMX 候補になります。対象外なら通常経路へ進み、条件に合う group がない場合は `STRATA_PF_XMX=2 not taken at layer ...` の診断を一度 stderr に出します。別の fused int8 経路が選ばれた場合も XMX2 専用経路にはなりません。
- `grouped_f16()` のカーネルは XMX の sub-group 形状を前提とします。実行時に選ばれた GPU と AOT/JIT build の組み合わせがその形状をサポートすることが必要です。

## 実行時の詳細

値と GPU 世代判定は `mode()` 内の `static const int` に保存されます。したがってプロセス内で最初に呼ばれた後、環境値や選択 GPU が変わっても再評価されません。最初の評価は `stage_slots()` や `dq_slots()` から起き得るほか、expert 処理時にも呼ばれます。世代判定には `strata::q_of(nullptr)` の SYCL device を使います。

mode 1 は FP16 dequantize 後にグループを最大 16 expert まで蓄積し、最後に gate/up の grouped GEMM、SwiGLU、down の grouped GEMM を queue に投入します。平均 rows/expert によって gate/up のみ通常 GEMM に fallback します。mode 2 は対象形式の expert blob をグループ単位で保持し、fused XMX の group 処理後に staging ring slot を解放します。kernel 呼び出しは同期せず SYCL queue に投入されます。対応しない mode 整数値には専用の警告はありません。

`docs/INTEL.md` は Alchemist の既定を 2、Battlemage の既定を off と説明し、A750 での測定を記載しています。ただし同資料の測定条件は engine 0.1.45.3 であり、測定値は現行 HEAD で再測定された性能保証ではありません。

## 根拠

- 読み取り、`atoi`、GPU 世代による既定、AOT guard、警告: `sycl/src/prefill/xmx_moe.dp.cpp:149-175`。
- GPU 世代判定の architecture/name 判定: `sycl/include/strata/sycl_queue.hpp:120-157`。
- SG16 / no-DG2-XMX build macro の設定: `sycl/CMakeLists.txt:31-44`。
- mode 2 の staging slot 条件、mode 1 の dequantize slot 数: `sycl/src/prefill/prefill.cpp:289-297`。
- mode 2 の native format・MMQ 条件、診断: `sycl/src/prefill/prefill.cpp:4245-4277`。
- mode 2 の group 処理と mode 1 の経路・平均行しきい値: `sycl/src/prefill/prefill.cpp:4465-4536`。
- XMX grouped kernel の build guard と終了経路: `sycl/src/prefill/xmx_moe.dp.cpp:41-48,121-125`。
- XMX group のタイル形状、最大 16 expert、API: `sycl/src/prefill/xmx_moe.dp.cpp:19-24,128-135,182-198`; `include/strata/prefill/xmx_moe.hpp:5-19`。
- 資料との照合（Alchemist 既定と測定環境）: `docs/INTEL.md:259-270,378-390`。
