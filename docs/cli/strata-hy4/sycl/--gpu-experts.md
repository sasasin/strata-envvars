# `--gpu-experts`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--gpu-experts` |
| 別名 | なし |
| 値 | 整数（MiB 単位の容量）。parser は `atoi` で変換する。既定値は `256`。 |

## 役割

SYCL エンジンで MoE の routed expert を GPU 上で計算する経路（GPU expert staging）を有効にし、その staging ring の容量を MiB で指定する。正の値を指定すると、条件を満たす chunk の expert 計算が CPU expert pool ではなく GPU 側の実装に委譲される。

## 使い方

```sh
# 入力 token が 32 個以上ある単発実行で、512 MiB の staging ring を確保する
strata-hy4-sycl --model model.strata --engram Engram-Q8.strata --tokens ids.txt --gpu-experts 512

# serve では入力 token 数の条件なしに初期化を試みる
strata-hy4-sycl --serve --native model.strata --engram Engram-Q8.strata --gpu-experts 384
```

## 値と既定値

- 値は `atoi` に渡され、変数の初期値は `256`（MiB）。同じ引数を複数回指定すると最後の値が残る（`engine/src/hy4flash/sycl/sy_main.cpp:104,107-115,162`）。
- 値が欠けると parser の `nxt()` が標準出力へ `ERR --gpu-experts needs a value` を出し、終了コード `2` で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- `0`、負数、数値として解釈できない文字列（`atoi` が `0` を返す）はエラーにならず、単に無効扱いになる。判定はすべて `gx_mb > 0` である（`engine/src/hy4flash/sycl/sy_main.cpp:162,301,324`）。
- 正値でも実効下限は `24`（MiB）。ring slot は `(gx_mb<<20)/3` を 4 KiB 境界へ切り下げた値で、これが 8 MiB 未満だと `init_unified` が `stage_bytes too small` で失敗する（`engine/src/hy4flash/sycl/sy_gpuexp.cpp:605-609`）。上限の検査はない。

## 実行時の動作

単発実行では、モデルと入力 token を読み `T0` を求めた後、`gx_mb > 0` かつ `T0 >= gx_min_t`（既定 `32`）のときに `GpuExperts::init_unified` を呼ぶ。成功すると `Runner::gx` と `gx_min_T` を設定し、各 MoE layer で `T >= gx_min_T` の chunk だけが GPU expert 経路に回る（`engine/src/hy4flash/sycl/sy_main.cpp:301,323-331`、`engine/src/hy4flash/sycl/sy_graph.h:1238-1242`）。初期化前に確保するメモリは、`slot_bytes` の pinned host slot 3 個と device slot 2 個に加え、chunk 長（`--chunk` か既定値）に比例する token 作業領域である（`engine/src/hy4flash/sycl/sy_gpuexp.cpp:600-645`、`engine/src/hy4flash/sycl/sy_main.cpp:276-278,327`）。

容量は他の expert tier の自動サイズにも影響する。単発実行で GPU expert 経路が対象になるとき（`--load-only` を含む）、`(gx_mb*2/3 + 220)` MiB を VRAM reserve として渡すため、`--vram-experts-gb` も `HY4S_VRAM_EXPERTS_GB` も無い場合の VRAM expert cache 自動確保量がその分減る。さらに host overhead に `gx_mb` MiB が加わり、`HY4S_RAM_BUDGET_GB` も `--ram-experts-gb` も無い場合の RAM expert pool 自動予算が減る。明示値を渡した場合はこれらの予算計算に reserve は使われない（`engine/src/hy4flash/sycl/sy_main.cpp:301-304`、`engine/src/hy4flash/sycl/sy_graph.h:123-151`）。

`--threads` の値は GPU staging の copy thread 数として `init_unified` に渡る（`engine/src/hy4flash/sycl/sy_main.cpp:304,327`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:604`）。

`--serve` では parser の値がそのまま `ServeOpts::gx_mb` に入り、`gx_mb > 0` なら token 数に関係なく初期化を試みる。既定値は `ServeOpts` の宣言値 `384` ではなく parser の `256` が使われる。serve 側の chunk 閾値は `32` 固定で、`--gx-min-t` は反映されない（`engine/src/hy4flash/sycl/sy_main.cpp:104,233`、`engine/src/hy4flash/sycl/sy_serve.h:34,290-296`）。

`--load-only` では token を読まずに戻るため、予約計算は成立するが `init_unified` は呼ばれない（`engine/src/hy4flash/sycl/sy_main.cpp:266-267,301-304,319`）。

## 適用条件と副作用

- 対象は SYCL 版の parser のみで、CUDA/HIP・Metal 版とは別実装である（`docs/cli/README.md:1452,1471`）。
- 有効な chunk では routed expert の計算が `GpuExperts::run` に委譲され、CPU expert pool・VRAM expert cache・peer GPU の decode 分岐はその chunk では実行されない。peer GPU を併用している場合は non-peer mask を渡して分担する（`engine/src/hy4flash/sycl/sy_graph.h:1120-1145`）。
- この委譲は `HY4S_SKIP_EXPERTS` の判定より前に return するため、GPU expert 経路が使われる chunk では同環境変数による expert 出力のゼロ化は起きない（`engine/src/hy4flash/sycl/sy_graph.h:1134-1150`、[`HY4S_SKIP_EXPERTS`](../../../envvars/HY4S_SKIP_EXPERTS.md)）。
- 単発実行の初期化可否は入力全体の `T0` で決まるのに対し、実際に GPU 経路へ回るかは chunk ごとの `T` で決まる。`T0 >= gx_min_t` でも `--chunk` が閾値未満なら初期化だけ行われて経路は使われない（`engine/src/hy4flash/sycl/sy_main.cpp:301,324`、`engine/src/hy4flash/sycl/sy_graph.h:1238`）。
- 無効化は `--gpu-experts 0` を使う。`engine/src/hy4flash/sycl/sy_graph.h:1170` のコメントは `--no-gpu-experts` に触れるが、現行 parser にそのオプションはない（`engine/src/hy4flash/sycl/sy_main.cpp:162`）。
- 初期化に失敗しても致命的ではなく、そのまま CPU 経路で実行が続く。

## 出力とエラー

- 単発実行で初期化に成功すると stderr に `[gpu-experts] on for chunks >= <閾値> tokens: ...` を出す（`engine/src/hy4flash/sycl/sy_main.cpp:330`）。serve 経路は成功時の専用行を持たず、`[load] total ...` 行の確保量に GPU expert 分が加算される（`engine/src/hy4flash/sycl/sy_serve.h:297-315`）。
- 初期化失敗時は stderr に `[gpu-experts] disabled: <理由>` を出して CPU 経路へ戻る。SYCL exception も同じ形式で出る（`engine/src/hy4flash/sycl/sy_main.cpp:331-336`、`engine/src/hy4flash/sycl/sy_serve.h:297-301`）。理由には `stage_bytes too small`、`expert code not supported by GPU path (expected 0..7)`、`expert body larger than ring slot` などがある（`engine/src/hy4flash/sycl/sy_gpuexp.cpp:606-609,713-720`）。
- device メモリ確保に失敗した場合は例外ではなく stderr に `gpuexp: out of device memory (...)` を出して終了コード `3` でプロセスが終了する（`engine/src/hy4flash/sycl/sy_gpuexp.cpp:590-596`）。
- 単発実行の usage 文言に `--gpu-experts` は含まれていない（`engine/src/hy4flash/sycl/sy_main.cpp:252`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104,162` — 既定値と parser 登録。
- `engine/src/hy4flash/sycl/sy_main.cpp:301-304,319,323-336` — 予約計算、初期化条件、閾値設定、診断出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:233`、`engine/src/hy4flash/sycl/sy_serve.h:34,290-301` — serve への値の受け渡しと固定閾値。
- `engine/src/hy4flash/sycl/sy_graph.h:1120-1145,1238-1242` — GPU expert 経路への分岐と呼び出し。
- `engine/src/hy4flash/sycl/sy_graph.h:123-151` — reserve と host overhead が他 tier の自動予算に効く箇所。
- `engine/src/hy4flash/sycl/sy_gpuexp.cpp:590-645,698-731` — slot サイズ算出、メモリ確保、初期化と失敗理由。
