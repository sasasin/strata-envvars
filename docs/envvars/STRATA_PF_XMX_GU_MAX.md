# `STRATA_PF_XMX_GU_MAX`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL の MoE prefill で `STRATA_PF_XMX=1` の grouped XMX 経路を使うとき、gate/up 計算を grouped XMX GEMM にするか、expert ごとの oneMKL FP16 GEMM にするかを選ぶ平均行数のしきい値です。この変数自体は XMX 経路を有効化しません。

しきい値との比較は `nr / ng < gu_max_mean()` です。`nr` はグループに入った expert の行数合計、`ng` はグループ内の expert 数です。条件を満たすと gate/up は grouped XMX、満たさないと oneMKL を expert ごとに実行します。down 計算はこの判定の外にあり、常に grouped XMX を呼びます。

## 値と判定

`std::getenv()` の値を `std::atoi()` で整数に変換します。変換後の値に範囲検査や clamp はありません。

| 設定 | 判定値 |
|---|---:|
| unset | `250` |
| 空文字 | `0` |
| 数字で始まる文字列 | `atoi` が読み取る先頭の整数。後続文字は判定に使わない（例: `300tail` は `300`） |
| 数字に変換できない文字列 | `0` |
| 負の整数 | 負の値をそのまま使用 |

比較は整数除算による平均値に対して厳密な `<` です。既定値 `250` では `nr / ng` が `250` のグループは gate/up の XMX 判定を通らず、oneMKL 側に進みます。値を `0` 以下にすると、通常の非負の行数では gate/up の比較が成立しません。

値は `gu_max_mean()` 内の `static const int` に初回呼び出し時に保存されます。その後プロセスの環境を変更しても再読込されません。初回呼び出しは mode 1 の経路で gate/up のグループ判定を行うときです。

## 有効になる条件

- この実装は SYCL prefill にあります。SYCL ビルドでは `sycl/src/prefill/xmx_moe.dp.cpp` が `strata_prefill` に組み込まれます。
- しきい値が参照されるのは、`strata::prefill::xmx::mode() == 1` の grouped FP16 経路だけです。`STRATA_PF_XMX` が unset または `0` なら通常の per-expert GEMM に進み、この変数は使われません。`STRATA_PF_XMX=2` の fused decode 経路もこのしきい値を参照しません。
- `use_mmq` の分岐に入った expert は別の MMQ 計算経路へ進むため、この grouped FP16/XMX 判定には到達しません。
- ビルドが対応する joint-matrix XMX kernel を含む必要があります。`STRATA_NO_DG2_XMX` ビルドでは `STRATA_PF_XMX` 自体が無視され、通常の MoE 計算に戻ります。SG16 でないビルドが Battlemage 上で動く場合も、`STRATA_PF_XMX` は警告付きで無視されます。これらの場合、このしきい値は実効性を持ちません。

## 実行時の詳細

`mode()` は別環境変数 `STRATA_PF_XMX` を `atoi` で読み、unset なら `0`、設定値が数値変換後 `0` なら無効、それ以外ならその整数を返します。対応ビルド・デバイス条件に合わない場合は XMX を無効にして stderr に `STRATA_PF_XMX ignored: ...` を出します。`mode()` の結果も関数内 static に保存されます。

mode 1 では、expert blob を FP16 に dequantize した後、最大 `kMaxGroup`（16）expert をまとめます。グループの平均行数がこの変数の値未満なら gate/up を grouped XMX で計算し、そうでなければ同じ FP16 重みを使って gate/up を expert ごとに `m.gemm.f16()` で計算します。続く SwiGLU の後、down は grouped XMX GEMM で計算します。実際にこの経路が使われると stderr に `strata: prompt experts on the grouped XMX GEMM (STRATA_PF_XMX=1)` を一度出します。

`docs/DETAILS.md` と `docs/INTEL.md` を確認しましたが、このしきい値の値判定や既定値を説明する記述は見つかりませんでした。実装コメントは既定値 `250` を示し、XMX と oneMKL の切替判断は呼び出し側で行われています。コメントにある単独 kernel の測定値は Strata の実行経路全体に対する測定ではないため、ここでは性能保証として扱いません。

## 根拠

- 変数の読み取り、`atoi`、既定値、static cache: `sycl/src/prefill/xmx_moe.dp.cpp:172-175`。
- XMX mode の読み取り・対応ビルド／デバイス条件と警告: `sycl/src/prefill/xmx_moe.dp.cpp:148-170`。
- SYCL prefill への XMX 実装の組み込み: `sycl/CMakeLists.txt:232-239`。
- expert グループ化、平均行数比較、gate/up の XMX／oneMKL 分岐、down の grouped XMX 呼び出し: `sycl/src/prefill/prefill.cpp:4084-4142`。
- `kMaxGroup` と変数の意図の宣言: `include/strata/prefill/xmx_moe.hpp:5-14`。
- `STRATA_NO_DG2_XMX` / SG16 を選ぶ AOT 条件: `sycl/CMakeLists.txt:39-44`。
