# `STRATA_NO_NVFP4_256`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

CPU の native expert 経路で、NVFP4 expert の gate/up 行および down 行に使う AVX2 実装を選ばないための診断・切り替え用環境変数です。設定すると、該当する行計算は `ggml-cpu` の `vec_dot` ループへ進みます。GPU 側の NVFP4 decode kernel や prompt 経路を切り替える変数ではありません。

## 値と判定

値の内容は parse されず、`std::getenv()` で設定の有無だけを調べます。

| 環境変数 | AVX2 NVFP4 実装の選択 |
|---|---|
| 未設定 | CPU が `cpu_avx2_ok()` を満たし、NVFP4 の対象次元が実装範囲内なら選択可能 |
| 空文字を含む何らかの値を設定 | 選択しない。値が `0`、`1`、`false` などのどれかは関係しない |

## 有効になる条件

この分岐に到達するには、native expert の CPU 行計算が使われる必要があります。native pack の実行は `--native` と `--spec` を使う経路として説明されており、ビルドに `STRATA_NATIVE_EXPERTS` がない場合は native pack を読み込めません。CPU pool は native 行計算から gate/up と down の関数を呼びます (`src/program/generate.cpp:2803-2806`, `src/kernels/cpu/expert_layout.cpp:376-400`, `src/kernels/cpu/pool.cpp:685-718`, `docs/NVFP4.md:166-172`)。

実装は gate/up と down でそれぞれ次の条件を確認します。

- gate/up: expert の `gu_type` が NVFP4、AVX2 機能が利用可能、`n_embd` が64要素ブロックの倍数で、ブロック数が64以下。
- down: `d_type` が NVFP4、同じ AVX2 条件、`n_ff` が64要素ブロックの倍数で、ブロック数が64以下。
- この専用関数へ進まない場合でも、AVX-512 NVFP4 分岐が先に成立すれば AVX-512 実装が選ばれます。`STRATA_NO_NVFP4_256` は AVX-512 分岐を無効にしません。

## 実行時の詳細

`native_gu_rows()` はまず AVX-512 NVFP4 行カーネルを試し、その条件が成立しない場合に AVX2 NVFP4 行カーネルを試します。AVX2 分岐に入ると gate と up を各行・各 token について計算し、scale を適用して SwiGLU 結果を `ff` に書きます。`native_down_rows()` も AVX-512 の後に同じ環境変数で AVX2 分岐を判断し、down の内積と scale 適用を行います。AVX2 条件が不成立または本変数が設定済みなら、両関数とも `ggml-cpu` の型別 `vec_dot` と行/token のループに進みます (`src/kernels/cpu/native_expert.cpp:194-229,257-278`)。

環境変数判定は両関数内の別々の `static const bool` です。したがって gate/up と down は各関数で初めて判定された時点の設定有無をキャッシュし、それ以後のプロセス内変更はその関数の判定に反映されません。Strata 側にこの変数についてのログやエラー出力はありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:204-218,257-270` — AVX-512からAVX2、さらに`ggml-cpu`へ進む選択順、設定有無による判定、対象投影。
- `src/kernels/cpu/nvfp4_avx2.cpp:76-79,161-195` — AVX2 実装の最大64ブロック（4096要素）、最大8 token の処理範囲と行関数。
- `src/kernels/cpu/pool.cpp:685-718` — native expert CPU pool から gate/up と down の行関数を呼ぶ箇所。
- `src/kernels/cpu/expert_layout.cpp:376-400` — `STRATA_NATIVE_EXPERTS` なしのビルドでは native expert 利用不可。
- `docs/NVFP4.md:166-172` — CPU expert の NVFP4 行経路と AVX-512 の説明。AVX2 固有の性能値はこの資料にはなく、本書では性能向上を断定しない。
