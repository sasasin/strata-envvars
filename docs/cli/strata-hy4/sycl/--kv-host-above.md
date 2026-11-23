# `--kv-host-above`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（通常実行、および `--serve` 実行） |
| オプション | `--kv-host-above` |
| 別名 | なし |
| 値 | 整数。コンテキスト長がこの値を超えた場合、sparse 層の KV cache を pinned host memory に置く閾値 |

## 役割

KV cache の配置を切り替えるコンテキスト長の閾値を指定する。現在のコンテキスト長 `max_ctx` が閾値より大きいとき、sliding-window attention（SWA）ではない層の KV cache を GPU device memory ではなく pinned host memory に確保する。SWA 層の配置にはこの閾値は使われない。

## 使い方

```sh
# 通常実行で閾値を 32,000 にする
strata-hy4-sycl --model model.strata --tokens ids.txt --kv-host-above 32000

# server 実行でも同じ閾値を指定する
strata-hy4-sycl --serve --native model.strata --kv-host-above 32000
```

## 値と既定値

- parser は次の argv 要素を `atoi` で整数化する。明示値の非負整数はそのまま閾値になる。`max_ctx > kv_host_above` の厳密な比較なので、コンテキスト長が閾値と等しい場合は host 側への切替は起きない（`engine/src/hy4flash/sycl/sy_main.cpp:104,164`、`engine/src/hy4flash/sycl/sy_graph.h:543-550`）。
- オプション省略時、または負数指定時は GPU の `global_mem` に応じて既定値を選ぶ。24 GiB 以上なら `131072`、未満なら `24000`。この分岐は通常実行と server 実行の両方にある（`engine/src/hy4flash/sycl/sy_main.cpp:234,293`）。
- 整数としての範囲検査や変換エラー検査はない。`atoi` が数値に変換できない値（例: `abc` や空文字列）は 0 になり、0 の閾値として扱われる。負数は拒否されず、既定値選択へ戻る。値を省略した場合は `ERR --kv-host-above needs a value` を stdout に出して終了コード 2 で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,164`）。
- 同じオプションを複数回指定すると、parser が順に代入するため最後の値が使われる（`engine/src/hy4flash/sycl/sy_main.cpp:107-115,164`）。

## 実行時の動作

通常実行では、`--ctx` / `--max-context` などから決まる `max_ctx` とこの閾値を比較し、`Runner` に閾値を渡す。`max_ctx` 自体を省略した場合は、入力 token 数と生成数から求めた値と `131072` の大きい方になる（`engine/src/hy4flash/sycl/sy_main.cpp:131,157,277,293`）。

`--serve` 実行では、正の `--max-context` 値がなければ server のコンテキスト長は `131072` となり、この閾値は `ServeOpts` 経由で `Runner` に渡る（`engine/src/hy4flash/sycl/sy_main.cpp:215-234,248`、`engine/src/hy4flash/sycl/sy_serve.h:28-35,258-267`）。

`Runner::init` は各層について cache の必要量を計算し、SWA でない層かつ `max_ctx > kv_host_above` の場合は `halloc`、それ以外は `dalloc` を使う。どちらの場合も cache をゼロ初期化する。したがってこのオプションは cache の配置先を切り替えるもので、cache 容量やコンテキスト長そのものを変更しない（`engine/src/hy4flash/sycl/sy_graph.h:535-553`）。

## 適用条件と副作用

- 対象は SYCL 版 `strata-hy4-sycl` の通常実行および server 実行。索引上の parser 所在は `engine/src/hy4flash/sycl/sy_main.cpp`（`docs/cli/README.md:1452-1478`）。
- 比較対象の単位は `max_ctx` と同じコンテキスト長の整数値で、バイト数や GiB ではない。
- host 側に移るのは sparse 層（`!c.is_swa[il]`）だけ。SWA 層は閾値にかかわらず device memory に確保される（`engine/src/hy4flash/sycl/sy_graph.h:540-552`）。
- pinned host memory の確保に失敗すると `halloc` が stderr に `halloc: out of host memory (...)` を出し、プロセスを終了コード 3 で終了する（`engine/src/hy4flash/sycl/sy_common.h:272-278`）。device memory 側の確保失敗も `dalloc` が stderr にエラーを出して終了コード 3 となる（同 `:263-270`）。
- `--kv-host-above` による性能上の効果や、各 SYCL backend / GPU での host memory アクセス性能は、このソース調査からは判断できない。

## 出力とエラー

本オプションの値を受理したときの専用メッセージはない。値が欠けた場合の parser エラーは「値と既定値」を参照。KV cache の host/device 確保失敗はそれぞれ `halloc` / `dalloc` のメッセージと終了コード 3 になる。通常実行中に捕捉された SYCL exception は stderr に `SYCL exception: ...` を出し、終了コード 4 となる（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104,107-115,164` — 値の初期状態、parser、`atoi` 変換、値不足時の出力と終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,277-294` — server / 通常実行での既定コンテキスト長、GPU memory に応じた既定閾値、Runner への設定。
- `engine/src/hy4flash/sycl/sy_serve.h:28-35,258-269` — server 設定での閾値保持と Runner への転送。
- `engine/src/hy4flash/sycl/sy_graph.h:535-553` — KV cache のサイズ計算、SWA 層の判定、閾値比較と host/device 配置。
- `engine/src/hy4flash/sycl/sy_common.h:262-278` — device / pinned host memory の確保失敗時の出力と終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:612-615` — 通常実行の SYCL exception 出力と終了コード。
