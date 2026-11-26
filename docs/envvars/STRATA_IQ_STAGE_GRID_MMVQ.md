# `STRATA_IQ_STAGE_GRID_MMVQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

IQ 系の単一行列 MMVQ カーネルで、i-quant / trellis の codebook grid を kernel ごとに shared memory（SYCL では work-group local memory）へ staging するかを opt-in で切り替える。`STRATA_IQ_STAGE_GRID_MMVQ` が staging を許可すると、対象型の `launch_mmvq` は `STAGE_GRID=true` の multi-column kernel を選び、無効なら `false` の kernel を選ぶ。カーネル内では true の場合に grid を shared/local memory へコピーして barrier 後に参照し、false の場合は staging pointer を `nullptr` として元の grid を参照する。ソースコメントは staging の有無で計算結果が bitwise 同一と記すが、性能値は実測を再確認したものではない。根拠: `engine/src/kernels/cuda/iq_kernels.cu:1997-2050,2071-2077,3791-3804`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2218-2270,2291-2303,4174-4227`。

CUDA/HIP 共通の GPU engine 実装と、独立した SYCL engine 実装がこの名前を直接読み取る。対象は MMVQ のみで、expert grouped kernels の grid staging 全体を制御する変数ではない。コード上、CLI 引数・設定ファイルからの上書きや子プロセスへの転送はない。根拠: `engine/cmake/strata_gpu_engine.cmake:1-9,98-100`、`engine/CMakeLists.txt:20-32`、`engine/src/kernels/cuda/iq_kernels.cu:3791-3804`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4174-4227`。

## 値と判定

この変数は `std::getenv` の結果を数値や真偽値として parse せず、値が存在し、**先頭文字が `'1'` か**だけを調べる。文字列全体の一致ではない。さらに親設定 `STRATA_IQ_STAGE_GRID` が staging を許可している必要がある。親設定は未設定・空文字なら有効、それ以外は先頭文字が `'0'` の場合だけ無効になる。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3696-3707`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3955-3966`。

| 条件 | `STRATA_IQ_STAGE_GRID_MMVQ` が未設定 | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| CUDA/HIP または SYCL の MMVQ 実装。かつ `STRATA_IQ_STAGE_GRID` が有効 | staging しない | `1`、`10`、`1anything`（いずれも先頭が `1`） | 空文字、`0`、`0anything`、`true`、`false`、` 1`（未設定・空文字は `getenv` が null または先頭が `\0`、その他は先頭文字のみで判定） |
| `STRATA_IQ_STAGE_GRID` の先頭文字が `0` | staging しない | なし。この変数を何にしても staging しない | `STRATA_IQ_STAGE_GRID=0`、`0anything` |

無効文字列に対する警告、エラー、数値境界処理はない。対象変数の値が `1` 以外で始まる場合は単に opt-in しない。`STRATA_IQ_STAGE_GRID` は未設定・空文字・先頭が `0` 以外なら有効なので、例えば `STRATA_IQ_STAGE_GRID=true` でも親ゲートは有効だが、対象変数は別途先頭 `1` が必要となる。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3696-3707`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3955-3966`。

## 有効になる条件

- `STRATA_IQ_STAGE_GRID_MMVQ` が読み取り時に設定され、先頭文字が `1` であること。空文字・`true`・先頭が空白の値は有効にならない。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3704-3707`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3963-3966`。
- 親設定 `STRATA_IQ_STAGE_GRID` が有効であること。親が先頭 `0` なら、この変数を `1` にしても無視される。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3696-3707`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3955-3966`。
- MMVQ 呼び出しが、grid staging 対象としてコンパイルされた型に到達すること。CUDA/HIP 側の `kStageIqGrid` は型 ID `16, 17, 18, 21, 22, 29, 144, 145, 146`、SYCL 側は `16, 17, 22, 29` に限定される。型ごとの `kSplit` が false の場合は通常の per-column kernel に入り、この staging 分岐には到達しない。根拠: `engine/src/kernels/cuda/iq_kernels.cu:987-995,3791-3804`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1250-1253,4174-4227`。
- `STRATA_OLD_IQ_MMVQ` によって旧 per-column kernel を選んでいないこと。CUDA/HIP と SYCL の `launch_mmvq` は旧 kernel 分岐を先に評価する。旧 kernel 用の `env_on` は未設定・空文字・先頭 `0` を off、それ以外を on とする。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3689-3695,3791-3804`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3932,4174-4227`。
- CUDA/HIP build では共通 GPU engine を有効にして当該 kernel を含めること。SYCL は別プロジェクトの実装であり、CUDA/HIP と同時に選択しない。CPU-only / Metal の実装にはこの名前の読み取り箇所がない。根拠: `engine/cmake/strata_gpu_engine.cmake:1-9,98-100`、`engine/CMakeLists.txt:20-32`。

コード上、この分岐にサーバーモード、特定 CLI option、モデル名、GPU 世代の追加判定はない。対象型の MMVQ 呼び出しに至らない場合は、この値による効果もない。

## 実行時の詳細

両実装とも `g_stage_grid` と `g_stage_grid_mmvq` を translation unit のグローバル初期化で一度計算する。対象変数の値をリクエストごと・kernel launch ごとに読み直さず、実行中に環境を変更してもこの判定には反映されない。`g_stage_grid_mmvq` は `g_stage_grid && (...)` なので、親設定が false のとき対象変数自体も評価されない。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3696-3707`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3955-3966`。

通常経路では `iq_mmvq` が型を dispatch し、`launch_mmvq` が `g_old_kernels` と compile-time の `kSplit` / `kStageIqGrid` を見て kernel を選択する。CUDA/HIP 実装では `g_stage_grid_mmvq` が true の場合 `launch_mmvq_multi_nc<TY, true>`、false の場合 `launch_mmvq_multi_nc<TY, false>` を呼ぶ。SYCL も同じ boolean 選択で `mmvq_multi_kernel` を起動する。テンプレート値は staging 用 shared/local-memory buffer のサイズと `stage_iq_grid` のコード経路を決める。根拠: `engine/src/kernels/cuda/iq_kernels.cu:1997-2050,2071-2077,3773-3804,5694-5705`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2218-2270,2291-2303,3968-3970,4174-4227,6552-6558`。

CUDA/HIP の型 ID 18 と 21 では grid のほか sign-mask table も staging 処理に含む。SYCL 側の対象型一覧には 18 と 21 が含まれない。Trellis ID 144–146 は CUDA/HIP 側で対象だが、147–149 は `kStageIqGrid` に含まれず、同じ staging opt-in の対象ではない。根拠: `engine/src/kernels/cuda/iq_kernels.cu:993-995,2025-2048,1660-1678`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1250-1253`。

## ログと測定値

対象変数の値や選択結果を出すログはなく、無効値に対する警告もない。コードコメントは、RTX 5070 の `IQ2_XS` / `IQ2_S` / `IQ1_M` の 3–8 column の MMVQ で staging が 10–20% 遅く、expert kernel では利得があったため MMVQ staging を `=1` の opt-in にした、と記している。これはコメント内の測定記述であり、本調査で再測定した結果ではない。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3701-3707`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3960-3966`。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:3689-3707` — env 判定、親ゲート、対象変数の初期化。
- `engine/src/kernels/cuda/iq_kernels.cu:987-995,1997-2050,2071-2077,3773-3804,5694-5705` — CUDA/HIP 側の型条件、staging 実装と dispatch。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3966,1250-1253,2218-2270,2291-2303,4174-4227,6552-6558` — SYCL 側の env 判定、型条件、staging 実装と dispatch。
- `engine/cmake/strata_gpu_engine.cmake:1-9,98-100`、`engine/CMakeLists.txt:20-32` — CUDA/HIP 共通 engine と SYCL 別 build の範囲。
