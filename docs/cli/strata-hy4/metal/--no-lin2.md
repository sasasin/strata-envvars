# `strata-hy4-metal --no-lin2`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--no-lin2` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

Metal runner が条件付きで使う row-blocked decode GEMV（`linear_skr`）を無効にし、対象となる小さい行数の線形演算を通常の `linear_sk` kernel に切り替える。ソースコメント上は A/B 比較用のフラグで、モデル読み込みや Metal library のコンパイルそのものを止めるものではない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:325,1492,1731`）。

## 使い方

```sh
# モデルと token ID ファイルを指定して、row-blocked GEMV を使わずに実行する
./strata-hy4-metal --model ./model.strata --tokens ./tokens.txt --gen 16 --no-lin2
```

`--no-lin2` は値を取りません。フラグを複数回指定しても同じ boolean が true のままです。

## 値と既定値

- parser は `--no-lin2` を認識すると `no_lin2 = true` にします。既定値は `false` なので、通常は `lin2` が有効です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491-1492,1549`）。
- 数値や文字列の値は受け取りません。別の文字列を `--no-lin2=...` のように付けた形式はフラグとして一致せず、未知引数経路になります（同ファイル `:1549,1604-1608`）。
- 明示的な範囲検証はありません。フラグの反復は boolean を再度 true にするだけです（同ファイル `:1549`）。

## 実行時の動作

parser の値は `Runner::lin` が見る `r.lin2` に `!no_lin2` として渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1731`）。`Runner::lin` は線形演算ごとに次の順で kernel を選ぶため、`--no-lin2` の影響は条件付きです（同ファイル `:482-510`）。

1. MPP 条件を満たす場合、または `--mm-min` の閾値以上の行数では GEMM kernel が選ばれ、このフラグは使われません。
2. `F_Q8ROW` 形式の重みは専用 kernel に分岐するため、このフラグは使われません。
3. `--sm-verify` が有効で、行数が 1〜8、重み形式が 4 / 5 / 6 / 8 の場合は `linear_sm` が優先され、このフラグは使われません。
4. 上記に該当せず、行数が 1〜8、重み形式が 4 / 5 / 6 / 8 の場合、既定では `linear_skr_<形式>_<行数>_<R>` を選びます。`--no-lin2` を指定するとこの分岐を飛ばし、`linear_sk_<形式>_1`（行数1）または `linear_sk_<形式>_8`（それ以外）へ進みます。

このため `--mm-min` を小さくして GEMM 側へ移った演算、`--sm-verify` が選ばれる演算、上記以外の重み形式・行数では効果がありません。`--lin2-r` は row-blocked kernel の R 値を指定する関連フラグですが、`--no-lin2` と同時なら row-blocked 分岐自体が選ばれず、値は dispatch に反映されません（同ファイル `:502-509,1731,1737`）。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal runner です。CUDA/HIP・SYCL runner の同名フラグへの効果は、この文書の対象外です。
- row-blocked kernel のソース `hy4_lin2.metal` は Metal library の基本ソース一覧に含まれ、MPP の有無にかかわらずコンパイル対象です。したがって、このオプションはコンパイルや GPU 使用を抑止するものではなく、演算ごとの kernel 選択を変えます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:526-555`）。
- 選択対象となる重み形式と行数は dispatch 条件に限られます。性能や出力値がどう変わるかは、実機・モデルごとの測定が必要であり、この調査では確認していません。

## 出力とエラー

- `--no-lin2` 自体に専用の標準出力・標準エラー出力はありません。
- 未知の引数は `ERR unknown flag <引数>` を標準出力へ、`unknown arg <引数>` を標準エラー出力へ出し、終了コード 2 で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608`）。
- `--lin2-r` に未対応の R 値を渡す場合、このオプションを併用して row-blocked 分岐を避けない限り、未定義 kernel 名の照会に進む可能性があります。生成可能な R は 1 / 2 / 4 に限られます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:507-508`、`engine/src/hy4flash/metal/hy4_lin2.metal:125-130`）。kernel が見つからない場合の `mtl: no function ...` と終了コード 3 は Metal runtime 実装の経路です（`engine/metal/src/mtl_rt.mm:229-255`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491-1492,1549` — Metal parser の既定値とフラグ受理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:482-510,1731,1737` — `Runner::lin` の条件分岐と設定値の受け渡し。適用条件、優先関係、fallback の根拠。
- `engine/src/hy4flash/metal/hy4_lin2.metal:5-54,125-130` — row-blocked kernel と、形式・行数・R の template instantiation。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:526-555` — `hy4_lin2.metal` が基本コンパイル対象である根拠。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608`、`engine/metal/src/mtl_rt.mm:229-255` — 未知引数と kernel 関数不在時の出力・終了経路。
