# `HY4_CUBLAS_SCRATCH_MB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 版 `strata-hy4` が共有 cuBLAS prefill 状態で確保する GPU scratch 領域のサイズを MiB 単位で指定する。既定は 64 MiB、指定値は最低 16 MiB に丸められる。この領域は量子化 S_K 重みの FP16 へのタイル単位 dequant と GEMM、および MLA の cuBLAS prefill 経路で共有される。scratch サイズだけを変え、cuBLAS 経路自体を有効化する設定ではない。読み取り・確保は `CublasPfState::ensure`、利用先は線形演算と MLA の CUDA 経路である（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:24-35,37-91`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2127,2130-2160`）。

## 値と判定

`getenv` が null かどうかで未設定を判定し、設定時は `atoi` で整数化した後 `std::max(16, ...)` を適用して MiB をバイトへ変換する。文字列全体の検証はなく、`atoi` が読む十進整数の先頭部分だけが使われる。空白と符号は `atoi` の規則で扱われ、数値の後ろの文字列は無視される。数値として読めない文字列は `atoi` が 0 を返すため 16 MiB になる。空文字も「設定あり」だが同様に 16 MiB になる（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:55`）。

| 条件 | unset | 有効になる値（例） | 判定・境界の例 |
|---|---|---|---|
| `HY4_CUDA` の CUDA ビルドで scratch 確保に進む場合 | 64 MiB | `1` → 16 MiB、`16` → 16 MiB、`64` → 64 MiB、`128` → 128 MiB | `0`、`0anything`、負値、`15`、空文字、`true`、`false`、`abc` は 16 MiB。`16anything` は 16 MiB、`64anything` は 64 MiB。大文字小文字は数値変換に関係しない。 |

上限値の検査はありません。`atoi` の結果が `int` で表現できない文字列について、コードは独自のエラー処理をしていません。CUDA の確保に失敗しても、この変数に対する値の警告は出しません（同ファイル `:55,66-80`）。

## 有効になる条件

- `HY4_CUDA` が有効な CUDA ビルドであること。CUDA 以外の HIP ビルドでは `sk_cublas_ctx.hip.h` の実装全体が `#if HY4_CUDA` の外となり、この変数は読まれない（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:6-7,107`、`engine/src/hy4flash/run/hy4_gpu.h:17-23,324-327`）。
- 共有 cuBLAS 状態の `ensure` が実行され、`HY4_CUBLAS_PF` の `atoi` 結果が 1 以上であること。`HY4_CUBLAS_PF` は未設定なら 1。設定時は `atoi` で判定するため `0`・空文字・非数値は無効、`1` は有効（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-17,37-38`）。
- 統合 UMA GPU では、`HY4_CUBLAS_PF` が未設定だと自動的に無効となり scratch サイズも読み取られない。明示的に設定して UMA 判定を越えるには、`HY4_CUBLAS_PF` が非ゼロと parse される必要がある（同ファイル `:50-55`）。
- 線形層の cuBLAS 利用には `HY4_MMA` の CUDA 分岐、`HY4_CUBLAS_PF` 有効、`HY4_CUBLAS_MIN_M` 以上のバッチ M、`lin_int8_mma()` が無効であることが必要。形式が `FMT_Q8ROW` または K が 256 の倍数でない場合も cuBLAS 関数は失敗を返して既存経路に戻る（`engine/src/hy4flash/run/skhy4.hip.h:59-80`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-54`）。
- MLA の Q prep / V up 経路では `HY4_CUBLAS_MLA` がそれぞれ 2 以上 / 1 以上、M が `HY4_CUBLAS_MIN_M` 以上で、`g_mla_force_simple` が無効であることが必要。共有状態の `ensure` による `HY4_CUBLAS_PF` 判定も通る必要がある。失敗時は各関数の標準 CUDA/HIP kernel 経路へ続く（`engine/src/hy4flash/run/mla_attn.hip.cpp:2164-2175,2256-2273`）。
- `ensure` は capture 中の stream、初回確保後の別 GPU、または空き VRAM 不足などでは false を返す。非 UMA GPU で当初の要求サイズに対して空き VRAM が 96 MiB の余裕を満たさない場合、要求を 32 MiB に縮小し、なお空きが 96 MiB 未満なら無効化する（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:37-59`）。

## 実行時の詳細

`CublasPfState` は関数内 static の共有 singleton で、CUDA の `Runner` 初期化中に `ensure(st)` が呼ばれる。線形 cuBLAS および MLA 経路からも同じ状態を参照する（`engine/src/hy4flash/run/hy4_graph.hip.h:1704-1711`、`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:100-103`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:51-52`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2099,2130-2132`）。

scratch 値自体は static 変数に別途保存されないが、`ensure` が `tried` を設定してから GPU メモリ確認・確保を行うため、その後は同じ GPU への呼び出しが保存済みの `ok` を返し、値を再読込・再確保しない。通常は初期化時の試行値が使われ、プロセス中の環境変更は反映されない。`HY4_CUBLAS_PF` の数値 parse 結果は関数内 static に保存される一方、UMA 判定での「明示設定あり」確認は `getenv` を直接行う。`ensure` が `tried` を設定する前に戻るのは、モード無効、GPU 取得失敗、stream capture 中などであり、条件が後に解消すれば後続呼び出しで再試行し得る。その場合、scratch は再試行時の値が読まれる。`cudaMemGetInfo` や確保の失敗は `tried` 設定後なので同じ GPU では再試行しない。scratch 変数は統合 UMA の自動無効判定より後で読むため、その経路では読み取りません（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-17,37-55,61-80`）。

空き VRAM を確認し、条件を通ると cuBLAS handle、scratch、nonblocking side stream、イベントを作成する。要求領域は `base` に確保され、線形層ではその全体を等分した double buffer を使って重みを dequant し、GEMM をタイル処理する。MLA の Q prep / V up も同じ `base` と `total_bytes` を一時領域として使う（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:47-83`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:53-90`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2100-2127,2133-2159`）。

非 CUDA ビルド、CUDA prefill 経路を選ばない条件、または `ensure` / GEMM が失敗した場合、この scratch に依存する経路は使われず呼び出し元の別 kernel 経路に戻る。CLI 引数がこの値を上書きする処理は確認できない。`docs/DETAILS.md` に本変数の記載はなく、挙動の根拠は実装コードによる。

## ログと測定値

状態の初期化に成功すると stderr に `[cublas-pf] side-stream double-buffered dequant + cuBLAS enabled (2 x %.0f MiB scratch, M >= %d)` を出す。ここで表示する `2 x` の値は、確保した総 bytes の半分を MiB 表示したもの（2 個の buffer の各サイズ）である。非 UMA GPU で VRAM 不足により無効化した場合は `[cublas-pf] disabled: low free VRAM (%.0f MiB)` を出す。統合 UMA GPU で自動無効化する場合は `[cublas-pf] auto-disabled on integrated UMA GPU (fused skwmma avoids LPDDR5X round-trip; set HY4_CUBLAS_PF=1 to override)` を出す。他の初期化失敗（handle / allocation / stream / event 作成失敗など）では、この実装に理由ログはない（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:51-80,89-90`）。資料に本変数の測定値はない。

## 根拠

- `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:37-91` — 有効判定、GPU/VRAM 条件、値の変換と最低値、scratch 確保、ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1704-1711` — Runner 初期化時の共有状態セットアップ。
- `engine/src/hy4flash/run/skhy4.hip.h:47-83`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90` — 線形 cuBLAS 経路と scratch buffer の利用。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2127,2130-2160,2164-2175,2256-2273` — MLA 経路と同じ scratch 領域の利用、適用条件。
- `engine/src/hy4flash/run/hy4_gpu.h:17-23,324-327`、`engine/CMakeLists.txt:884-908` — CUDA/HIP ビルド分岐。
