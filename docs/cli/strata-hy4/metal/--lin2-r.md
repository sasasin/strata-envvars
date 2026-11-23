# `--lin2-r`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--lin2-r` |
| 別名 | なし |
| 値 | 整数。row-blocked decode GEMV の行ブロック幅 `R` を指定する |

## 役割

Metal runner が小さい M の decode / verify で使う row-blocked GEMV kernel の `R` を選びます。主に kernel の比較・調整用の指定です。通常の推論で必ず使われるわけではなく、入力形状・量子化形式・他の設定によって別の kernel が選ばれます。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens tokens.txt --lin2-r 2
```

## 値と既定値

parser は値を `atoi` で整数化します。明示的な範囲検証はありません。未指定時は `0` で、kernel 選択時には `R=1` が使われます。正の `3` も `R=1` に置き換えられます。`hy4_lin2.metal` がこの runner 用に定義する `linear_skr` の `R` は `1`, `2`, `4` です。そのため、これら以外の正の値は対応する kernel 特殊化がありません。parser は値の有無を事前確認せず、次の argv 要素を読み取ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1555`）。

## 実行時の動作

parser は `--lin2-r` の次の引数を `lin2_r_arg` に読み込み、Runner の `lin2_r` に渡します。対象の線形演算が `M >= mm_min` なら GEMM が先に選ばれ、`--sm-verify` が有効で対象条件に合う場合も `linear_sm` が優先されます。それ以外で `lin2` が有効、`1 <= M <= 8`、かつ重み形式が `4`, `5`, `6`, `8` のときに限り `linear_skr` の選択に使われます。`--no-lin2` を指定した場合や条件外では `--lin2-r` は kernel 選択に影響しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:499-509`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1549-1555`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1731-1737`）。

対象条件を満たす場合、kernel 名は `linear_skr_<形式>_<M>_<R>` になります。指定値が正なら `R` に使われますが、`3` は `1` に変換されます。未指定、0、負数は初期値の `R=1` のままです。Metal kernel は `R` 行ずつ処理し、コンパイル時の特殊化は形式 `4/5/6/8`、`M=1..8`、`R=1/2/4` に限定されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:504-509`, `engine/src/hy4flash/metal/hy4_lin2.metal:5-10`, `engine/src/hy4flash/metal/hy4_lin2.metal:125-130`）。

## 適用条件と副作用

このオプションは Metal runner 固有です。値によって選ばれるのは GPU 上で実行する Metal kernel の特殊化で、ファイルや設定値を書き換える処理は確認できません。範囲外の正の値には対応する kernel 名が生成されますが、その名前を解決する Metal runtime の失敗動作は、この runner のソースだけでは確認できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:425-428`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:504-509`）。

## 出力とエラー

このオプション自体について、値を検証して出す専用の警告・エラーや標準出力はありません。未知のフラグは `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出して終了コード `2` になりますが、`--lin2-r` は既知のフラグです（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1555`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608`）。範囲外の正数が対応 kernel の解決時にどう報告されるかは、Metal runtime の実装に依存するため未確認です。
