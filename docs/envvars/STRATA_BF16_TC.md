# `STRATA_BF16_TC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA と SYCL の BF16 行列積で、対応する分岐に入ったとき BF16 の重み・活性を FP16 に変換し、FP16 の GEMM を使うかを選ぶ。CUDA の通常設定では compute capability 7.0–7.4 でこの経路が既定で選ばれ、7.5 では既定で cuBLAS の BF16 GEMM に残る。`1` は 7.x で FP16 経路を選び、`0` は 7.x で BF16 経路を選ぶ。`2` は既知のデバイスなら capability にかかわらず FP16 経路を選ぶ試験用値である。これはモデル全体の精度や全演算を切り替える設定ではなく、BF16 GEMM の特定経路に作用する（`engine/src/prefill/gemm.cu:947-958,1201-1257`; `engine/sycl/src/prefill/gemm.dp.cpp:626-637,897-931`）。

## 値と判定

両実装とも `getenv` の結果を関数内 `static const int` に一度保存し、空でない値だけ `std::atoi` に渡す。文字列全体の妥当性検査はない。`atoi` が読む先頭の十進整数部分で判定するため、`"1tail"` は 1、`"0tail"` と `"true"` は 0、先頭空白付きの `" 1"` は 1 になる。空文字は未設定と同じ `-1`。`atoi` が 0 を返す非数値文字列も 0 として扱われ、負の変換結果は `forced >= 0` の強制指定にはならず既定判定へ戻る。大文字小文字の比較はない。整数変換の範囲外入力の結果はコードで制限・検証していない（`engine/src/prefill/gemm.cu:948-952,953-958`; `engine/sycl/src/prefill/gemm.dp.cpp:627-631,632-637`）。

GPU capability は CUDA では `10 * major + minor`、SYCL では同じ形式で得る。次表は両 `bf16_path()` の判定順であり、利用経路は後述の GEMM 条件にも従う。

| capability / build | unset または空文字 | 設定値で FP16 経路になる例 | ここで FP16 経路にならない例 |
|---|---|---|---|
| 7.0–7.4 | 既定で FP16 | `1`, `2`, `3`, `1tail` | `0`, `0tail`, `true`, 負値 |
| 7.5–7.9 | 既定で BF16 | `1`, `2`, `3`, `1tail` | `0`, `0tail`, `true`, 負値 |
| 7.0 未満 | `bf16_path()` は path 2（FP32 selector） | `2` は既知デバイスなら先に path 1（FP16） | `0` / `1` は通常この capability 判定を覆さない |
| 8.0 以上 | 既定で BF16 | `2` は既知デバイスなら path 1（FP16） | `1` や `3` は path 0（BF16） |
| capability 不明 / 取得失敗 | path 0（BF16） | なし。path 2 の特例判定より capability 判定が先に終わる | すべて |

path 2 を Pascal 向け FP32 GEMM に使うのは `STRATA_EXPERIMENTAL_SM60` ビルドだけ。CUDA ではこの build guard がない path 2 は FP32 分岐に入らず、BF16 GEMM に進む（`engine/src/prefill/gemm.cu:918-927,953-958,1195-1201`; `engine/sycl/src/prefill/gemm.dp.cpp:580-589,632-637,897-913`）。

## 有効になる条件

- 読み取り実装は CUDA (`engine/src/prefill/gemm.cu`) と SYCL (`engine/sycl/src/prefill/gemm.dp.cpp`) にある。HIP コンパイルでは `bf16_path()` と CUDA/SYCL 向け分岐が `!defined(__HIPCC__)` で除外され、`bf16_converts_x()` も常に false を返す。HIP の WMMA、hipBLASLt、その他の BF16 経路をこの変数が選ぶコードは見つからない（`engine/src/prefill/gemm.cu:890,1143-1148,1195-1201`; `engine/sycl/src/prefill/gemm.dp.cpp:533,842-843,897-898`）。
- CUDA / SYCL の FP16 経路には `K > 0`、`N > 1`、`beta == 0.0f` が必要。これを満たさない積（単一出力行、`beta == 1` の加算積など）はこの経路を使わず、後続の通常 GEMM へ進む。Pascal の path 2 は CUDA では `STRATA_EXPERIMENTAL_SM60` build が必要で、この分岐は `N` / `beta` 条件とは別に扱われる（`engine/src/prefill/gemm.cu:1201-1208`; `engine/sycl/src/prefill/gemm.dp.cpp:898-915`）。
- `T <= 0` または `N <= 0` の GEMM は変数を判定する前に何もせず戻る（`engine/src/prefill/gemm.cu:1154-1158`; `engine/sycl/src/prefill/gemm.dp.cpp:845-850`）。
- CUDA の prefill では、`Gemm::bf16_converts_x()` が true になると、`STRATA_XN_F16` が未設定または先頭文字が `'0'` 以外で、かつ `m.f16_io` が false の場合に限り `m.xn_f16` が true になり得る。`STRATA_XN_F16=0` はこの活性変換の最適化を止めるが、重みを FP16 GEMM に回す `STRATA_BF16_TC` の選択自体は止めない。SYCL の `bf16_converts_x()` は false（`engine/src/prefill/prefill.cpp:2724-2735`; `engine/sycl/src/prefill/gemm.dp.cpp:842-843`）。
- capability query が CUDA で失敗した場合は 0（不明）となり、BF16 経路を選ぶ。SYCL では query エラーコードも 0 扱いとなる場合がある一方、投げられた `sycl::exception` は `what()` 等を stderr に出して `exit(1)` する（`engine/src/prefill/gemm.cu:928-945`; `engine/sycl/src/prefill/gemm.dp.cpp:590-624`）。

## 実行時の詳細

`forced` は最初の `bf16_path()` 呼び出し時にプロセス内で一度だけ環境から読み、以後の環境変更は反映されない。GPU capability は別に device ID ごとの `static` 配列へ cache される。CUDA の prefill 初期化では `bf16_converts_x()` 呼び出しが path 判定の初回になる場合がある。SYCL は `bf16_converts_x()` が false なので、通常は最初の適用対象 BF16 GEMM で判定する（`engine/src/prefill/gemm.cu:930-958,1143-1148`; `engine/sycl/src/prefill/gemm.dp.cpp:592-637,842-843,897-898`; `engine/src/prefill/prefill.cpp:2724-2735`）。

FP16 path 1 では BF16 の値を FP16 に変換して GEMM する。CUDA では重み全体と活性の row slice 用 buffer を確保し、FP16 化した値を `f16()` に渡す。通常 `beta == 0` の分岐で、`x_f16` が true なら既に FP16 の活性を再利用する。SYCL も BF16 重み・活性を FP16 buffer に変換して `f16()` を呼ぶ。確保関数がエラーを返す場合、両 backend とも BF16 GEMM にフォールスルーする。SYCL で確保時に `sycl::exception` が投げられた場合は捕捉して stderr に出し `exit(1)` する。CUDA でも path 1 の変換 buffer が確保できなければ通常の BF16 GEMM に進む。有限値の FP16 範囲外は CUDA/SYCL の変換 kernel で ±65504 に clamp される（`engine/src/prefill/gemm.cu:905-917,960-968,1201-1256`; `engine/sycl/src/prefill/gemm.dp.cpp:547-579,639-660,897-910`）。

CUDA では `x_f16` が true でも path 1 の GEMM を使えなかった場合、FP16 活性を BF16 に戻して通常 GEMM を行う。戻し buffer が確保できないと stderr にエラーを出して終了する。path 2 が `STRATA_EXPERIMENTAL_SM60` の Pascal FP32 経路として選ばれ、変換 buffer を最小サイズまで確保できない場合も stderr に理由を出して終了する（`engine/src/prefill/gemm.cu:1258-1272,1218-1224`）。

## ログと測定値

通常の値選択を知らせる `STRATA_BF16_TC` 専用ログはない。CUDA の Pascal path 2 で変換 buffer を確保できない場合、`prefill gemm: no GPU memory left for the FP32 conversion buffers ...` を stderr に出して `exit(1)` する。FP16 活性を BF16 に戻す buffer が足りない場合は `prefill gemm: no GPU memory for converting an FP16 image back to BF16` を出して終了する。SYCL の capability query 中に例外が発生すると、例外内容に続けて `Exception caught at file:` を stderr に出して終了する（`engine/src/prefill/gemm.cu:1218-1224,1261-1264`; `engine/sycl/src/prefill/gemm.dp.cpp:621-624`）。

`docs/OLDER_GPUS.md:127-129,275-298` は sm_75 での opt-in と丸め差、および一台の Quadro RTX 8000 での throughput / reply 比較を記載するが、ここではコードで再現測定していないため性能値は転記しない。`docs/DETAILS.md:1336-1346` は `STRATA_XN_F16` との併用を挙げており、上記 prefill 初期化の条件と整合する。

## 根拠

- `engine/src/prefill/gemm.cu:928-958,1143-1148,1154-1158,1195-1299` — CUDA の capability cache、値の読み取り・path 判定、経路と fallback。
- `engine/sycl/src/prefill/gemm.dp.cpp:590-637,842-845,897-944` — SYCL の capability cache、値の読み取り・path 判定、適用条件と経路。
- `engine/src/prefill/prefill.cpp:2724-2735,5101-5106,5109-5124` — CUDA prefill の `STRATA_XN_F16` 連携と BF16 活性の利用。
- `engine/src/prefill/gemm.cu:905-917,1218-1224,1258-1272` — FP16 変換、clamp、および CUDA の観測可能な失敗経路。
- `docs/OLDER_GPUS.md:127-129,275-298`; `docs/DETAILS.md:1336-1346` — 資料記述との照合（挙動の根拠は上記ソース）。
