# `STRATA_KQ_GU_LANES`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL ポートの native grouped expert 計算で、K-quant および Q5_1 / Q8_0 の gate/up 行を処理する lane 数を選びます。`STRATA_GU_LANES` が gate/up の共通値で、この変数を設定すると該当形式だけを上書きできます。down 行には適用されず、down 側は `STRATA_DOWN_LANES` を使います。

この分岐は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` に一箇所あります。対象形式は `KqSplit<TG>::has` が真になる Q4_K、Q5_K、Q6_K、Q5_1、Q8_0 です。

## 値と判定

値は `std::atoi` で整数に変換し、変換後の値が `4`、`8`、`16`、`32` のいずれかなら採用します。それ以外はコンパイル時既定の `STRATA_EXPERT_LANES` に戻ります（このファイル内で未定義時は `8`）。文字列全体の妥当性は検証しないため、たとえば `16junk` や `16.5` は `16` として採用されます。空文字、数値に変換できない文字列、許可リスト外の数値は既定値になります。

| 設定状態 | lane 数の選択 |
|---|---|
| `STRATA_KQ_GU_LANES` 未設定 | `STRATA_GU_LANES` を同じ変換規則で評価した値 |
| 設定値が `4` / `8` / `16` / `32` に変換される | その値 |
| 設定値が空、無効、または許可リスト外 | `STRATA_EXPERT_LANES`（未定義時 `8`）。`STRATA_GU_LANES` には戻らない |

`STRATA_GU_LANES` も許可値以外なら `STRATA_EXPERT_LANES` に戻ります。既定の compile-time 値自体を変更するビルド設定がある場合は、その値が fallback になります。

## 有効になる条件

- `native_expert_grouped()` が SYCL ポートの lane kernels を実行する経路であること。対象の gate/up 型が KqSplit 対象型ならこの環境変数を参照します。i-quant の multi kernel を選ぶ別経路では lane 値自体が使われません。
- gate/up 側の行処理に限ります。型に `KqSplit<TG>::has` がない場合は `STRATA_GU_LANES` を使います。down 側は別に `STRATA_DOWN_LANES` を選びます。
- `STRATA_KQ_SPLIT=0` または `native_expert_set_kq_split(false)` は K-quant の複数 entry 処理方式を切り替えますが、lane 数の選択は `KqSplit<TG>::has` に基づくため、この変数の対象型判定とは別です。

## 実行時の詳細

選んだ値は `launch_gu_lanes()` の switch で `native_gu_kernel` のテンプレート lane 数 `4` / `8` / `16` / `32` に結び付けられます。work-group は 256 work-item なので、行数は `256 / lanes` です。lane 数が変わると行への lane 配分と reduction の分割が変わります。

値は関数内の `static const int` に保存され、最初に `kq_gu_lanes()` が呼ばれた時点で評価されます。その後にプロセス環境を書き換えても再評価されません。unset の場合は `gu_lanes()` も static cache されます。Strata がこの変数について出すログや警告は見つかりません。

実装コメントは、B70 の4-token window で16 lane の Q4_K / Q5_1 が8 lane より高い帯域値を記録した一方、reduction 順序が異なるため opt-in にしたと記しています。このコメントは個別測定の報告であり、別条件での性能や数値結果を保証するものではありません。`docs/INTEL.md` は `STRATA_GU_LANES` / `STRATA_DOWN_LANES` の説明を載せていますが、この個別上書き変数は記載していません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:794-801` — compile-time 既定 lane 数と fallback（未定義時8）。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:1754-1762,1792-1794,1826-1828,1854-1856,1892-1894` — KqSplit 対象形式。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4301-4314` — `lanes_env` の変換、共通 gate/up 値、個別値の読み取りと cache、実装コメント。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4331-4349` — KqSplit 対象型の lane 選択と kernel dispatch。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4402-4419,5282-5309,5360-5365` — grouped expert の gate/up dispatch 経路。
- `docs/INTEL.md:533-545` — lane 関連の共通設定と expert kernel の説明。`STRATA_KQ_GU_LANES` の記述はない。
