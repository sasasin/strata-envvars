# `strata-hy4-sycl --gx-min-t`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--gx-min-t` |
| 別名 | なし |
| 値 | 整数。入力トークン数・処理 chunk の GPU expert 実行閾値。parser は `atoi` で変換する。既定値は `32`。 |

## 役割

単発の prefill 実行で、GPU expert cache の初期化を試みるために必要な入力長と、各 chunk を GPU expert 経路に回す最小 token 数を指定する。GPU expert cache 自体は `--gpu-experts` が正のときだけ対象になる。

## 使い方

```sh
# 入力 token が 64 個以上のとき GPU expert cache の初期化を試み、64 token 以上の chunk で使う
strata-hy4-sycl --model model.strata --tokens ids.txt --gx-min-t 64
```

## 値と既定値

- 値は `atoi` に渡され、初期値は `32`。専用の範囲検査や値のエラー処理はありません（`engine/src/hy4flash/sycl/sy_main.cpp:104,163`）。
- オプション値が欠けると parser の `nxt()` が標準出力へ `ERR --gx-min-t needs a value` を出し、終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 複数回指定した場合、引数を左から読むたびに同じ変数へ代入するため、最後の指定値が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:107-115,163`）。
- 負数や `0` を拒否する検査はありません。閾値判定は `>=` なので、単発実行では `--gx-min-t 0` などは正の入力長・chunk に対して閾値を満たします（`engine/src/hy4flash/sycl/sy_main.cpp:301,324`、`engine/src/hy4flash/sycl/sy_graph.h:1238`）。

## 実行時の動作

単発実行では、入力 token ファイルを読み `T0` を token 数として求めた後、`--gpu-experts` の容量 `gx_mb` が正で、かつ `T0 >= gx_min_t` のときに GPU expert cache の初期化を試みます。初期化に成功すると `Runner` に cache を設定し、`gx_min_T` にこの値を設定します。その後、各 MoE layer で `T >= gx_min_T` の chunk のみ GPU expert を使い、それ未満はこの GPU expert 経路を使いません（`engine/src/hy4flash/sycl/sy_main.cpp:266-276,301-304,323-330`、`engine/src/hy4flash/sycl/sy_graph.h:1231-1243`）。

`--gpu-experts` を省略した場合の容量は `256` MiB です。同オプションが `0` 以下なら `gx_mb > 0` 条件が偽になり、GPU expert cache の初期化および閾値の効果はありません（`engine/src/hy4flash/sycl/sy_main.cpp:104,162-163,301,324`）。

`--load-only` では token ファイルを読み込まず、`want_gx` の予約条件は `load_only` により閾値と無関係に成立します。ただし cache 初期化箇所より前に `load_only` で戻るため、`--gx-min-t` による GPU expert cache の初期化は行われません（`engine/src/hy4flash/sycl/sy_main.cpp:266-267,301-304,318-327`）。

## 適用条件と副作用

- この文書の対象は SYCL CLI です。CUDA/HIP・Metal 版とは別 parser です。SYCL parser の位置は索引にも `engine/src/hy4flash/sycl/sy_main.cpp` として登録されています（`docs/cli/README.md:1452-1474`、`docs/cli/000_cli_tools.md:11`）。
- `--serve` 経路では parser は値を受け取りますが、`ServeOpts` へコピーされません。serve 側は `Runner::gx_min_T` を `32` に設定するため、`--gx-min-t` の指定値は serve の chunk 閾値に反映されません（`engine/src/hy4flash/sycl/sy_main.cpp:226-248`、`engine/src/hy4flash/sycl/sy_serve.h:289-296`）。
- 条件を満たすと `GpuExperts::init_unified` が呼ばれ、モデルの expert directory を読み、GPU 用メモリ等を初期化します。初期化に失敗した場合は cache を使わず、stderr に `[gpu-experts] disabled: ...` を出します。SYCL exception も同様に disabled として stderr に出力します（`engine/src/hy4flash/sycl/sy_main.cpp:323-336`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:698-731`）。
- token 数が閾値未満なら単発実行で cache 初期化を試みません。閾値以上でも初期化成功は保証されず、失敗時の詳細な原因は `init_unified` が返すエラーまたは SYCL exception に依存します。

## 出力とエラー

cache 初期化に成功すると stderr に `[gpu-experts] on for chunks >= <閾値> tokens: ...` と出し、失敗時は前節の disabled 診断を出します（`engine/src/hy4flash/sycl/sy_main.cpp:327-336`）。`--gx-min-t` 固有の範囲エラーや警告は実装されていません。値欠落時の stdout と終了コードは「値と既定値」を参照してください。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104,163` — 閾値変数の既定値と parser 登録。
- `engine/src/hy4flash/sycl/sy_main.cpp:109-115` — 値の消費、値欠落時のメッセージと終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:301-304,323-336` — 単発実行での初期化条件、閾値の設定、診断出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:226-248`、`engine/src/hy4flash/sycl/sy_serve.h:289-296` — serve への値未転送と固定閾値。
- `engine/src/hy4flash/sycl/sy_graph.h:1231-1243` — chunk ごとの閾値判定と GPU expert 経路への引き渡し。
- `engine/src/hy4flash/sycl/sy_gpuexp.cpp:698-731` — GPU expert cache 初期化処理。
