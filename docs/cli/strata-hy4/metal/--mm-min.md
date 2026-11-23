# `strata-hy4-metal --mm-min`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--mm-min` |
| 別名 | なし |
| 値 | 整数（トークン行数のしきい値） |

## 役割

Metal runner の線形層で、通常の S_K 量子化重みを使う場合に、simdgroup GEMM の `linear_mm_*` を選ぶ最小トークン行数を指定します。値未満の小さい行数では、通常は `linear_sk_*` の GEMV 系カーネルが選ばれます。しきい値は runner の `lin` で各層の行数 `M` と比較されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:481-510`）。

## 使い方

```sh
# 線形層で GEMM を選び始める行数を 32 に設定して実行する
strata-hy4-metal --model SQ64.strata --tokens ids.txt --mm-min 32
```

`--model` と `--tokens` は runner の通常の入力指定例です。上記は実在するモデルや入力ファイルを示すものではありません（usage の引数形式: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1613`）。

## 値と既定値

- 値は `atoi` で `int` に変換されます。省略時は `16` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1528`）。
- parser に範囲検証や数値変換エラーの確認はありません。数値として解釈できない文字列は `atoi` により `0` になり、正数以外を拒否する処理も見当たりません。したがって `0` や負数を指定すると、正の `M` は `M >= mm_min` を満たします（同: `1528`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:501`）。
- 同じ引数を複数回指定すると、引数を左から走査するたびに同じ変数へ代入するため、最後に指定した値が残ります（同: `1504-1506,1528`）。

## 実行時の動作

parser が値を `mm_min_arg` に格納し、runner 構築後に `r.mm_min` へ渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1528,1715,1730`）。線形演算 `lin` は層の重み形式と実行条件を見て、次の順でカーネルを選びます（同: `482-510`）。

1. MPP が有効で、`M >= mpp_min`、重みが Q8ROW ではなく、重みサイズが scratch 上限内なら MPP の GEMM を先に選びます。この経路では `--mm-min` は判定に使われません（同: `487-495`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:327-333,557-558`）。
2. それ以外で Q8ROW 形式なら、固定しきい値 `M >= 16` で `linear_mm_100` と Q8ROW 用 GEMV を切り替えます。ここでも `--mm-min` は使われません（同: `496-498`）。
3. 上記以外の S_K 形式では `M >= mm_min` なら `linear_mm_<format>`、そうでなければ次の小行数向け分岐に進みます（同: `499-510`）。

`linear_mm` は量子化重みを fp32 で復号して fp16 に丸め、simdgroup matrix で積和します（`engine/src/hy4flash/metal/hy4.metal:714-750,757-770`）。小行数向け `linear_sk` は重みを float で復号し、float の積和を行います（同: `607-640`）。ただし `M < mm_min` でも、`M` が 1〜8 で対応形式なら `--sm-verify` による `linear_sm_*` が優先され、その後 `--no-lin2` が無効であれば row-blocked `linear_skr_*` が選ばれます。いずれにも該当しない場合は `linear_sk_*` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:499-510,1528,1543,1549`）。

## 適用条件と副作用

- この文書の対象は Metal runner だけです。`--mm-min` の条件分岐は S_K 重み形式の `lin` にあり、Q8ROW と MPP 優先経路には適用されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:482-510`）。
- MPP の利用可否は Metal 4 カーネル群のコンパイル結果で決まり、利用できない場合は通常カーネルへフォールバックします。`--no-mpp` を指定すると MPP の試行を止めるため、他の条件が同じなら `--mm-min` の判定に進む場合があります（同: `1527,1729`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:522-558`）。MPP 選択の行数条件は別の `--mpp-min` が担います（同: `332,487`）。
- `--sm-verify` と `--no-lin2` は `M < mm_min` の小行数経路に影響します（同: `1528,1543,1549`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:502-509`）。`--moe-mm-min` は別の MoE grouped GEMM 判定に使われ、このオプションとは独立しています（同: `337,1546`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1182`）。
- オプション自体はカーネル選択しきい値を変えます。ファイル操作などの副作用はこの値の処理からは確認できません。実行経路では選ばれた Metal カーネルが GPU 上で実行されます（同: `501-510`, `engine/src/hy4flash/metal/hy4.metal:607-640,714-770`）。

## 出力とエラー

`--mm-min` の値に対する専用の警告、エラー、出力はありません。数値変換後に値をそのまま設定へ渡し、しきい値として比較します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1528,1730,501`）。Metal 4 MPP カーネルを利用できない場合は runner 初期化時に stderr へフォールバック理由を出力しますが、これは `--mm-min` 固有の失敗ではありません（同: `533-556`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1528,1730` — 既定値、parser 登録、runner への引き渡し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:482-510` — `M` と各形式・MPP・小行数カーネルの選択条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:522-558` — MPP カーネルのコンパイル試行とフォールバック。
- `engine/src/hy4flash/metal/hy4.metal:607-640,714-770` — GEMV 系と GEMM カーネルの計算処理。
