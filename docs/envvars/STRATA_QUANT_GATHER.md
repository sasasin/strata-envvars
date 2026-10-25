# `STRATA_QUANT_GATHER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソースで、外部依存ライブラリの内部動作は説明対象外。

## 役割

MoE prefill の MMQ 経路で、入力 activation を量子化して expert row 順に配置する方法を切り替えます。既定経路は量子化と scatter を一つの `quantize_scatter_mmq_q8_1_cuda()` 呼び出しで行います。この変数を有効にすると、`src` に沿って行を gather しながら `quantize()` する経路に戻ります。実装コメントと `docs/DETAILS.md` は、量子化結果は同じ bytes で、測定上の差は確認されなかったと記しています。

## 値と判定

環境値は `quantize_scatter()` 内の関数ローカル `static const bool` として初回にだけ評価されます。判定は `getenv()` が値を返し、かつ `std::atoi(value) != 0` であれば有効です。文字列全体の一致ではなく `atoi` の整数変換です。

| 値 | 判定 |
|---|---|
| 未設定、空文字、整数変換結果が `0` の文字列 | 無効。fused quantize-scatter 経路 |
| `1` など整数変換結果が非ゼロの文字列 | 有効。`src` に沿った `quantize()` 経路 |
| `-1` など負の非ゼロ整数 | 有効 |
| `1tail` や先頭空白付きの ` 1` | `atoi` が先頭の整数部分を `1` と読むため有効 |
| `tail` など先頭に整数がない文字列 | `atoi` の結果が `0` のため無効 |

`atoi` は先頭の空白と符号を受け付け、最初の整数として読める部分までを変換します。したがって `0tail` は無効、`2tail` は有効です。コードは変換エラーを別扱いせず、値域の clamp も行いません。

## 有効になる条件

この分岐が実行されるには、実行ファイルに GGML MMQ prefill がビルドされ、prefill の対象 layer が `mmq_plan()` により MMQ 対象として選ばれる必要があります。`mmq_plan()` は `mmq::built()` が真で、かつ `STRATA_PREFILL_MMQ` が未設定または `atoi` 結果非ゼロのとき MMQ を候補にします。形式ごとの対応可否も確認され、対応しない layer は別経路になります。

NVFP4 W4A4 activation が選ばれた場合、呼び出し元は `quantize_scatter()` ではなく `quantize()` を直接呼ぶため、この環境変数はその処理に影響しません。MMQ prefill を使わない実行ファイルや、MMQ に選ばれない layer でも影響しません。

## 実行時の詳細

prefill の対象 layer で MMQ が選ばれ、NVFP4 W4A4 の直接量子化経路でない場合、`prefill.cpp` は `quantize_scatter()` に token 数 `T` と各 token の expert 使用数 `K` を渡します。関数は `tokens <= 0` または `k_used <= 0` なら何もせず戻ります。その後で環境値を初回評価し、評価結果をプロセス内で cache します。最初の有効な呼び出し後に環境を変更しても、この分岐の選択は変わりません。

- 無効時: `quantize_scatter_mmq_q8_1_cuda()` を呼び、activation の量子化と expert row 配置をまとめて行います。
- 有効時: `quantize(x, src, ...)` を `tokens * k_used` 行で呼びます。各出力 row は `src` が示す入力 row に対応し、quantize 側で gather しながら量子化します。

この変数専用のログや警告はありません。Strata の `docs/DETAILS.md` の一覧は `STRATA_QUANT_GATHER=1` を「once-per-token」から「per-row gather」へ戻す switch として記載し、RTX 3060 / A4000 欄は「no difference measured」としています。これは同資料に書かれた測定結果であり、他の条件での性能を保証するものではありません。

## 根拠

- `src/prefill/moe_mmq.cu:384-394`: `atoi` による値判定、static cache、二つの実装経路。
- `src/prefill/moe_mmq.cu:366-382`: `quantize()` が `ids` に従って q8_1 row を作る処理。
- `include/strata/prefill/moe_mmq.hpp:33-36,49-54`: `quantize()` の row 対応と scatter/gather 経路の配置説明。
- `src/prefill/prefill.cpp:1129-1149,3374-3375,3805-3812`: MMQ 候補の条件、対象 layer の選択、NVFP4 W4A4 の bypass と呼び出し。
- `CMakeLists.txt:71-79,1690-1695,1737-1782`: HIP MMQ build option と、CUDA/HIP の MMQ prefill target への compile definition。
- `docs/DETAILS.md:2237`: switch の要約と、RTX 3060 / A4000 の測定欄。
