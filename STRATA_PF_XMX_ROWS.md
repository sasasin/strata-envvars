# `STRATA_PF_XMX_ROWS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL の prompt prefill で `STRATA_PF_XMX=2` の fused grouped XMX 経路を使うか、各 expert の重みを FP16 に dequantize して oneMKL GEMM を実行するかを切り替える、平均 routed rows のしきい値です。グループ内 expert あたりの平均 rows がこの値より小さいと fused grouped XMX を使います。等しい場合は FP16 dequant + GEMM 側です。

この変数単独では XMX を有効にしません。対象の grouped 経路には `STRATA_PF_XMX=2` が必要です。

## 値と判定

値は C/C++ の `std::atoi` で整数化され、文字列全体の検証はありません。未設定時は `200` です。空文字や数値に変換できない文字列は `atoi` の結果が `0` になり、先頭の空白や符号、数値の後ろの文字は `atoi` の変換規則に従います（例: `" 200rows"` は `200`、`"-1"` は `-1`）。

| 設定例 | しきい値 | 効果（`STRATA_PF_XMX=2` の対象経路） |
|---|---:|---|
| unset | 200 | 平均 rows が200未満なら fused grouped XMX |
| `200` | 200 | 同上 |
| `0`、空文字、`abc` | 0 | routed rows が非負の通常ケースでは条件を満たさず、FP16 dequant + oneMKL GEMM |
| `-1` | -1 | 同上 |
| `300junk` | 300 | 平均 rows が300未満なら fused grouped XMX |

比較は `nr / xg_n < xg_max` です。`nr` は現在のグループの routed rows 合計、`xg_n` はそのグループの expert 数で、整数除算です。そのため端数は切り捨てられます。しきい値と同じ平均値は fused 経路になりません。グループは最大サイズに達した時、またはその layer の expert 順が終わった時に処理されます。

## 有効になる条件

- SYCL の prompt prefill が `STRATA_PF_XMX=2` を選んでいること。
- MMQ を使っていないこと（`!use_mmq`）。
- layer が native pack であり、gate/up 型が `18, 21, 22, 23` のいずれか、down 型が `20, 42` のいずれかであること。

条件を満たさない layer では `STRATA_PF_XMX_ROWS` は参照されず、このしきい値による切替はありません。`STRATA_PF_XMX=2` が設定されていて対象外なら、プロセス内の最初の該当時に stderr へ `strata: STRATA_PF_XMX=2 not taken at layer ...` と理由の値が出ます。

ビルドにも XMX kernel の制約があります。`STRATA_NO_DG2_XMX` が定義されたビルドでは `STRATA_PF_XMX` 自体が無視されます。AOT Battlemage を sub-group 8 でビルドした場合も `STRATA_PF_XMX` は無視され、Battlemage 用 AOT build が必要です（`STRATA_XMX_SG16`）。これらは `STRATA_PF_XMX_ROWS` の独立した条件ではなく、親の XMX mode が有効になる前提です。

## 実行時の詳細

`xflush` が最初に呼ばれた時に `STRATA_PF_XMX_ROWS` を読み、その結果を関数内 `static const int` に保存します。したがって、プロセス実行中に環境変数を変えても再評価されません。環境変数が読まれるのは `STRATA_PF_XMX=2` かつ上記 layer 条件に合うグループが実際に flush される場合です。

平均 rows がしきい値未満の場合、gate/up と down の積をそれぞれ `iq_xmx_grouped` で処理し、間に SwiGLU を実行します。しきい値以上では、各 expert の gate/up と down の量子化重みを FP16 に dequantize し、oneMKL の FP16 GEMM を expert ごとに実行します。どちらの分岐も同じ prefill の中間出力 `GU` / `Dm` を作る経路です。XMX 経路が選ばれると、最初の flush で stderr に `strata: prompt experts on the fused grouped XMX (STRATA_PF_XMX=2)` が出ます。しきい値自体や選択結果ごとの追加ログはありません。

## 根拠

- `sycl/src/prefill/prefill.cpp:3945-3959`: native pack と量子化型、MMQ 条件、mode 2 の対象外ログ。
- `sycl/src/prefill/prefill.cpp:3968-4014`: グループの routed rows 集計、既定値200、厳密な比較、二つの計算経路、最初の有効ログ。
- `sycl/src/prefill/xmx_moe.dp.cpp:148-170`: `STRATA_PF_XMX` の parse、ビルド/device による拒否。
- `include/strata/prefill/xmx_moe.hpp:8-14`: XMX mode 1/2 の概要。
- `sycl/CMakeLists.txt:39-44`: AOT device による XMX sub-group 定義。
- `docs/INTEL.md:831-833`: Battlemage で grouped XMX mode 1/2 を試した記載はあるが、`STRATA_PF_XMX_ROWS` の値ごとの測定結果や意味は記載されていない。コメントの測定説明（`sycl/src/prefill/prefill.cpp:3977-3978`）も 16 experts の比較についての注記であり、一般的な性能保証ではない。
