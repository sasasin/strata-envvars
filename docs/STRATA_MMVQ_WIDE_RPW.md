# `STRATA_MMVQ_WIDE_RPW`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL の Q6_K MMVQ wide kernel で、各 warp が一度に処理する出力行数（rows per warp, RPW）を選びます。既定値は 1 行です。2 または 4 を指定すると、該当するテンプレート実装を選び、warp あたりの出力行数に合わせて work-group 数も計算します。kernel 内では、複数行で入力 activation のロードを共有します。

この変数は wide kernel が選択されたときだけ参照されます。通常の CUDA/HIP 実装を制御する変数ではなく、該当コードは `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあります。

## 値と判定

値は `std::atoi` で変換されます。文字列全体の厳密な数値検証はなく、数値の先頭部分を変換し、変換できない文字列は 0 になります。

| 環境変数の状態・変換結果 | 選択される RPW |
|---|---:|
| 未設定 | 1（既定値） |
| 設定値が `atoi` で 2 に変換される | 2 |
| 設定値が `atoi` で 4 に変換される | 4 |
| 空文字、非数値、0、負数、または 1・2・4 以外の値 | 1 |

たとえば `2tail` は 2、`4.5` は 4、`true` と空文字は 0 に変換され、その後いずれも上表の規則で扱われます。大文字小文字の比較はありません。

## 有効になる条件

この設定がカーネル選択に影響するには、まず `native_q6_k_mmvq()` が packed Q6_K 経路で処理を終えず、wide 経路の条件を満たす必要があります。wide 経路は `STRATA_MMVQ_WIDE` によって有効で、`ncols` が 1 以上かつ `STRATA_MMVQ_WIDE_MAXC` 以下、`n_in` が 256 の倍数、`n_out` が `STRATA_MMVQ_WIDE_MIN` 以上の場合に選択されます。既定の `WIDE_MIN` / `WIDE_MAXC` は `STRATA_MMVQ_A2` が有効ならそれぞれ 0 / 8、無効なら 4096 / 4 です。これらの条件に合わない呼び出しでは、本変数は wide kernel の選択を変えません。

さらに、同じ wide launcher で `STRATA_MMVQ_PF` が 2・3・4・6 のいずれかなら、prefetch 付き kernel が先に選ばれて戻るため、本変数が選んだ RPW は使われません。prefetch 値が正でもその4値以外なら RPW 分岐へ進みます。RPW が 1 の場合は、`STRATA_MMVQ_A2` の aligned-load 経路、または `mmvq_sg16(false, n_out)` が選ぶ subgroup 16 経路が先に使われることがあります。RPW が 2 または 4 の場合はそれらの RPW=1 専用分岐を通らず、対応する RPW wide kernel に進みます。

## 実行時の詳細

環境変数の値は `q6k_wide_rpw()` の関数ローカル `static const` に保存され、プロセス内で最初に wide launcher がこの関数を呼んだときに読み取られます。その後にプロセス環境を変更しても再評価されません。読み取り値が 1・2・4 のいずれかなら対応する kernel を起動し、それ以外なら RPW=1 の kernel を起動します。RPW=1 では、前述の A2 / subgroup 16 の特殊経路も選択候補になります。

各行で Q6_K の重みと Q8_1 activation から積和を計算し、RPW 行分を処理する wide kernel では activation をその行間で共有します。ソースには、この変数の値に応じた専用ログやエラー出力はありません。確認した `docs/INTEL.md` の Q6_K wide kernel の記述には性能測定がありますが、RPW の各設定値を比較する測定条件・結果は記載されていないため、本書では性能差を断定しません。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1693-1695` — `getenv`、既定値 1、`atoi` による読み取りと関数内キャッシュ。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1544-1573,1590-1605` — RPW が行の割当てと kernel 内の複数行処理に使われ、activation を列ごとにロードして RPW 行で共有する処理。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1698-1741` — prefetch 経路の優先、A2 / subgroup 16 の RPW=1 経路、RPW 1・2・4 の分岐と範囲外値の RPW=1 fallback。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3426-3457` — packed 経路の先行判定、wide 経路の適用条件、`WIDE_MIN` / `WIDE_MAXC` の既定値、後続 kernel への fallback。
- `docs/INTEL.md:448-456` — Q6_K wide kernel に関する資料上の説明。RPW 別測定の根拠には使用していません。
