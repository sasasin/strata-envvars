# `--threads`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（通常実行、または `--serve`） |
| オプション | `--threads` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 |

## 役割

CPU 上で動く Hy4 expert 処理の OpenMP thread 数を指定する。通常実行と engine line protocol の `--serve` の双方で CPU expert pool に渡され、GPU expert staging が有効な経路ではホスト側の expert copy に使う thread 数にも渡される。SYCL GPU kernel の work-group 幅を指定するオプションではない。

## 使い方

```sh
# 通常の prefill 実行で CPU expert pool を 8 thread にする
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt --threads 8

# engine line protocol の server でも同じ thread 数を指定する
strata-hy4-sycl --serve --native SQ.strata --engram Engram-Q8.strata --threads 8
```

## 値と既定値

- 値を省略すると、初期値は `max(2, hardware_concurrency() / 2)`（整数除算）となる。ハードウェア並列数を取得できない場合も下限は 2。
- 指定値は `atoi` で整数化される。明示値に対する範囲検証や変換エラー検査はないため、数値でない文字列は `atoi` の結果として 0 になり、整数の後ろに解釈されない文字列がある場合も入力全体の検証は行われない。
- 同じオプションを複数回指定した場合は parser が逐次代入するため、最後の指定値が残る。
- 値を付けずに終わると `ERR --threads needs a value` を stdout に出し、終了コード 2 で終了する。
- CPU expert pool と GPU expert staging の初期化側は thread 数を最低 1 に補正する。このため `0` や負数はその後の初期化で 1 thread として扱われ、parser 段階では拒否されない。

## 実行時の動作

通常実行では parser の値が `setup_experts_unified` に渡され、同関数から `CpuExperts::init` に渡される。CPU expert pool は受け取った数を最低 1 に補正して `nth_` とし、expert 計算の OpenMP parallel region をこの数で実行する。通常実行では `--load-only` でなく、`--gpu-experts` が正数かつ token 数が `--gx-min-t` 以上の場合に GPU expert staging を初期化し、同じ値を copy thread 数として渡す。初期化時にも最低 1 に補正され、GPU staging の OpenMP copy loop で使われる。`--load-only` は VRAM 予約サイズの計算条件には関係するが、staging の初期化より前に処理を終了する。

`--serve` 経路では parser 値を `ServeOpts::threads` にコピーし、server 初期化時に同じ CPU expert pool と GPU staging に渡す。server 側の GPU staging は `gx_mb > 0` の場合に初期化される。通常実行の `--gpu-experts` / `--gx-min-t` と、server の staging 条件は別の分岐である。

他オプションとの主な関係は、通常実行の `--gpu-experts`、`--gx-min-t`、`--load-only` が GPU staging の初期化や VRAM 予約の条件を変えること。`--threads` 自体は GPU staging の有効・無効を切り替えない。

## 適用条件と副作用

SYCL の `strata-hy4-sycl` が対象で、同じ `--threads` 指定は通常実行と `--serve` のどちらにも適用される。値が影響するのは CPU expert 処理と、条件付きのホスト側 GPU expert copy である。値に応じて CPU 並列実行 thread 数が変わり、GPU staging が有効なら OpenMP copy thread 数も変わる。ソースからは性能上の推奨値や最適値は確認できない。

## 出力とエラー

- 値なしは stdout に `ERR --threads needs a value` を出して終了コード 2。
- 未知の引数は stderr に `unknown arg ...` を出して終了コード 2（`--serve` 時には追加で stdout に `ERR unknown flag ...`）。
- `--threads` の負数や変換不能文字列を理由とする parser エラーは実装されていない。初期化に失敗した場合のエラーは通常実行では stderr の `experts: ...`、server では protocol 出力の `ERR experts: ...` を経由する。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104-115` — 既定値と、値がない場合の stdout エラー・終了コード。
- `engine/src/hy4flash/sycl/sy_main.cpp:159` — `--threads` の parser 定義。`atoi` で代入し範囲検証を行わない。
- `engine/src/hy4flash/sycl/sy_main.cpp:190-197` — 未知引数の失敗経路。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — `--serve` 経路での必須 model 検査と `ServeOpts::threads` への転送。
- `engine/src/hy4flash/sycl/sy_main.cpp:301-307`、`324-332` — 通常実行の CPU expert pool 初期化と、条件付き GPU expert staging 初期化への thread 数の転送。
- `engine/src/hy4flash/sycl/sy_graph.h:123-126`、`214-215` — 共通 expert setup から CPU expert pool への引き渡し。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:333-337`、`708-719` — CPU expert pool の最低 1 thread 補正と OpenMP 実行。
- `engine/src/hy4flash/sycl/sy_serve.h:28-44`、`280-300` — server 設定の thread 項目と CPU pool / GPU staging への引き渡し。
- `engine/src/hy4flash/sycl/sy_gpuexp.cpp:600-605`、`698-710`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:939` — GPU expert staging の copy thread 数の最低 1 補正と OpenMP copy loop。
- `docs/cli/README.md:1452-1500` — 索引上の tool ID・SYCL command scope・`--threads` のリンク。
