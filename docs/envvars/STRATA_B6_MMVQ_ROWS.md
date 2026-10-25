# `STRATA_B6_MMVQ_ROWS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の量子化行列ベクトル積（MMVQ）の複数列経路で、重みの複数行を処理する B6 kernel を選びます。この kernel は、各重み block に対する各 activation 列の fragment を一度読み込み、block 内の複数行で再利用します。対象は Q4_K、Q5_K、Q6_K、IQ4_XS です。対応外の形式ではこの変数が有効でも既定 kernel を使います。

## 値と判定

CUDA 実装の翻訳単位初期化時に `getenv()` で一度読み、設定値を `std::atoi` で整数化します。未設定なら `0` です。空文字や整数に変換できない文字列も `atoi` の結果が `0` となり無効です。整数の後ろにある文字は `atoi` が数値として読まないため、たとえば `2xyz` は `2` として扱われます。先頭空白や符号も `atoi` の規則で処理されます。

| 整数化した値 | B6 の設定 | 起動する行数（block あたり） |
|---:|---|---:|
| 未設定、または `<= 0` | 無効 | 既定 kernel |
| `1` | 有効 | 2 |
| `2` | 有効 | 2 |
| `8` | 有効 | 8 |
| その他の正数（例: `3`, `4`, `9`） | 有効 | 4 |

値 `1` は実装上 2 行を選びます。値 `2` も 2 行です。API コメントでは `1 = 2 rows per block, 2 / 4 / 8 = that many rows` と記載されていますが、実装は `2` を明示的に 2 行として扱い、それ以外の正数（`4` を含む）は 4 行へ fallback します。

## 有効になる条件

値が正でも、実行時に次を満たさない場合は B6 kernel を使いません。

- CUDA の `native_mmvq.cu` にある複数列 MMVQ 経路を通ること。単一列の呼び出しでは対象になりません。
- 形式が Q4_K、Q5_K、Q6_K、IQ4_XS のいずれかであること。これら以外は `B6X<F>::ok` が false です。
- `native_mmvq_set_multi_exact()` が有効にした既定の exact 配置であること。generic multi-column 配置に切り替わっている場合は無効です。
- `STRATA_TSUM` により TSUM 経路が有効でないこと。
- 入力形状に対して `n_in / F::DIV >= 1` であること。

いずれかの条件を満たさないとき、呼び出しは次の MMVQ kernel 選択へ進みます。実装には、この環境変数専用の警告や状態ログはありません。

## 実行時の詳細

`g_b6_rows` は CUDA 翻訳単位のグローバル変数で、環境変数を初期化時に読み取ります。そのため通常はプロセス起動後に環境を書き換えても反映されません。`native_mmvq_set_b6_rows(int)` API は値を上書きできますが、調査した HEAD での呼び出し箇所は B6 benchmark (`src/kernels/b6_mmvq_bench.cpp`) だけでした。通常の kernel 呼び出しでは `b6_launch()` が設定値と上記条件を見て kernel を選びます。

この選択は計算結果を既定 exact layout と bitwise 同じに保つ設計です。`docs/DETAILS.md` は 0.1.45 時点の RTX 3060 と RTX A4000（sm_86）の測定表に、`=1` でそれぞれ `+0.2..1%` / `+0.5..2%` と記載しています。これは同資料に記された IQ3_XXS、5 組の interleaved whole-engine run など当時の条件に限る値であり、他の GPU や設定での性能を示すものではありません。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:1157-1159` — `g_b6_rows` の既定値と `getenv` / `atoi` の読み取り。
- `src/kernels/cuda/native_mmvq.cu:1309-1314,1315-1317,1352-1377,1378-1404` — B6 の役割、bitwise 一致の実装意図、対応形式。
- `src/kernels/cuda/native_mmvq.cu:1452-1468` — 有効条件、行数選択、kernel launch。
- `src/kernels/cuda/native_mmvq.cu:1472-1477` — 複数列 launch 経路から B6 選択を行う箇所。
- `src/kernels/cuda/native_mmvq.cu:2346-2349` — 設定 API。
- `include/strata/kernels/native_mmvq.hpp:34-39` — 公開 API の説明と対応形式。
- `src/kernels/b6_mmvq_bench.cpp:187-194` — 調査対象 HEAD における設定 API の benchmark 呼び出し。
- `docs/DETAILS.md:2220-2233` — 0.1.45 時点の測定条件と結果。
