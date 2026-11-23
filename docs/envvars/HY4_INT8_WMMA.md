# `HY4_INT8_WMMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

HIP の RDNA4 (`gfx1200` / `gfx1201`) で、Hy4 の S_K 重みを使う線形演算と MoE expert 演算に INT8 WMMA kernel を選ぶ実行時スイッチ。`1` は 1-term、`2` は 2-term の活性値量子化経路を選び、既定の `0` は既存の FP16 WMMA 経路を使う。S_K の重み形式は `S1.25`、`S1.5`、`S2`〜`S6`、`S8` が INT8 kernel の dispatch 対象で、`Q8ROW` は線形演算の先行分岐で reference kernel に送られる（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:12-15, 55-63, 442-475`、`engine/src/hy4flash/run/skhy4.hip.h:47-79`）。

GPU アーキテクチャが `gfx12` でなければ値を読み取らず `0` を返す。対象ヘッダー自体も `HY4_MMA && !HY4_CUDA` のビルドに限られ、命令呼び出しは `HY4_GFX12` が有効なときだけ実装される（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:21, 36-42, 45-63`、`engine/src/hy4flash/run/hy4_gpu.h:353-361`）。

## 値と判定

`int8_wmma_mode()` の初回呼び出し時に GPU が `gfx12` と判定されると、`getenv` の結果を `atoi` に渡す。変数が未設定なら `0`。整数値 `1` と `2` だけが INT8 kernel を選び、その他は `0` と同様に FP16 WMMA の通常経路へ進む。`atoi` のため文字列全体の妥当性検査や範囲検査はなく、数値変換できない先頭（例: `true`）は `0`、先頭の空白や符号の後に数字があればその数値を変換し、数字以降の文字は判定に使われない（例: `2junk` は `2`）。空文字も `atoi("")` により `0` になる。大文字小文字は文字列比較ではなく数値変換のため、`true` / `TRUE` とも `0`。負値、`3` など `1` / `2` 以外の整数は INT8 kernel を選ばない。整数範囲外の文字列に対する `atoi` の結果はこのコードで検査・規定していない（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:56-63`、`engine/src/hy4flash/run/skhy4.hip.h:65-79`）。

| 条件 | 未設定 | INT8 経路を選ぶ値 | INT8 経路を選ばない値 |
|---|---|---|---|
| HIP、`HY4_MMA`、実行中 GPU の arch 名が `gfx12` で始まる | `0` | `1` または `2`（例: `1`, `2`, `1.5` は `1`、`2junk` は `2`） | 空文字、`0`, `-1`, `3`, `true`, `0anything` |
| その他の実行中 GPU arch | `0` | なし。環境変数を読み取らない | 設定値すべて。デバイス判定で先に `0` を返す |

## 有効になる条件

- HIP ビルドであること。CUDA ビルドではこの環境変数の読み取り関数を含むヘッダーが取り込まれない（`engine/src/hy4flash/run/skhy4.hip.h:10-16`）。
- `HY4_MMA` が有効なビルドであること。対象ヘッダーと線形演算・MoE の INT8 分岐はこの macro でガードされる（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:21, 481`、`engine/src/hy4flash/run/skhy4.hip.h:59, 65-79`、`engine/src/hy4flash/run/skmoe.hip.h:1535-1541`）。
- 実行中デバイスの HIP arch 名が `gfx12` で始まること。判定に失敗した場合も `false` となり、環境変数は参照されず mode は `0`（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-60`）。ビルド側では `HY4_GFX12` は `__gfx1200__` / `__gfx1201__` で定義され、INT8 WMMA 命令もこの macro が有効な場合に呼ばれる（`engine/src/hy4flash/run/hy4_gpu.h:353-361`、`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:36-42`）。
- 線形演算では、`M <= 4` の GEMV 分岐は INT8 WMMA dispatch より先に選ばれる。`Q8ROW` も reference kernel に直行する。その他の形式では `M` が 5〜16 なら小タイル経路、`M > 16` なら通常の GEMM 経路で mode `1` / `2` が INT8 WMMA を選ぶ（`engine/src/hy4flash/run/skhy4.hip.h:47-79`）。
- `HY4_NO_W16` が未設定で、モデル重み・`M`・重みサイズの条件を満たすと、mode `0` の場合は FP16 化した重みを使う最適化経路が先に選ばれる。`HY4_INT8_WMMA=1` / `2` ではこの条件を満たさず、後続の線形 dispatcher に進む（`engine/src/hy4flash/run/hy4_graph.hip.h:1332-1347`）。
- MoE では `HY4_MMA` 有効かつ RDNA2 経路でない分岐で mode `1` / `2` が INT8 kernel を選ぶ。mode がそれ以外なら既存の WMMA kernel 群へ進む（`engine/src/hy4flash/run/skmoe.hip.h:1530-1565`）。

CLI 引数や別の環境変数が `HY4_INT8_WMMA` の値を上書きする処理は確認できない。`HY4_NO_W16` は mode `0` の FP16 重み最適化の適用条件を変えるが、mode の値は変更しない（`engine/src/hy4flash/run/hy4_graph.hip.h:1337-1347`）。

## 実行時の詳細

`is_gfx12_device()` は最初に呼ばれた時点で `hipGetDevice` と `hipGetDeviceProperties` を実行し、結果を関数内 `static` に保存する。いずれかの HIP 呼び出しが失敗した場合は `false` を保存する。`int8_wmma_mode()` も最初の呼び出し時に mode を関数内 `static` に保存し、GPU が gfx12 であればその時点の環境変数を `getenv` / `atoi` で読む。そのため、プロセス実行中に環境を変えても再評価されない（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-63`）。

mode `1` / `2` は線形演算 dispatcher からそれぞれ `HI=false` / `HI=true` の INT8 kernel launch に結び付く。MoE dispatcher も同じ mode を読み、同じ `HI` の選択で expert の gate/up と down kernel を起動する。`HI=true` の kernel は量子化活性値の残差項も計算し、`HI=false` は第 1 項だけを計算する（`engine/src/hy4flash/run/skhy4.hip.h:60-79`、`engine/src/hy4flash/run/skmoe.hip.h:1539-1561`、`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:283-329, 331-360`）。

HIP graph cache の key にも mode が含まれるため、mode ごとに graph cache entry が区別される。DFly2 の二つの graph cache key にも同様に値が格納される（`engine/src/hy4flash/run/hy4_graph.hip.h:3092-3103`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:612-630, 868-888`）。

## ログと測定値

この環境変数の読み取り、無効値、gfx12 判定失敗について専用のログやエラー出力はない。mode `1` / `2` 以外は通常 kernel 経路へ分岐するため、環境変数だけを理由とした終了や失敗処理はない（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-63`、`engine/src/hy4flash/run/skhy4.hip.h:65-79`、`engine/src/hy4flash/run/skmoe.hip.h:1540-1565`）。測定値は本書に記載できる条件付きの Strata 資料を確認できなかったため記載しない。

## 根拠

- `engine/src/hy4flash/run/sk_int8_rdna4.hip.h:21, 36-63` — ビルド guard、gfx12 判定、環境変数の読み取りと cache。
- `engine/src/hy4flash/run/skhy4.hip.h:47-79` — 線形演算の format / M による分岐と mode dispatch。
- `engine/src/hy4flash/run/skmoe.hip.h:1530-1565` — MoE の mode dispatch と fallback。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1337-1347, 3092-3103`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:612-630, 868-888` — FP16 重み経路の条件と graph cache key。
- `engine/src/hy4flash/run/hy4_gpu.h:353-361` — gfx1200 / gfx1201 向け build macro。
