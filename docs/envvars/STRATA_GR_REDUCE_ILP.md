# `STRATA_GR_REDUCE_ILP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

SYCL の fused hyper-connection（GR）で、低ランク SiLU 値を reduce カーネル内で再利用する経路が選ばれたとき、部分和の読み出しを 1 件ずつ行う実装か、8 件を先にロードしてから同じ順序で加算する実装かを切り替える。`true` 側は `gr_down_reduce_kernel<true, true>`、`false` 側は `<false, true>` を起動する。8 件を先行ロードする分岐ではロード待ちを隠す狙いだが、現行ソースから性能差は断定できない。部分和を足す順序はどちらも slice 0 から 79 まで同じで、reduce 結果から低ランク SiLU 値を作って保存する処理も共通である。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:775-806,3395-3406`。

この参照は SYCL backend の `fused_gr.dp.cpp` にあり、`engine/sycl/CMakeLists.txt:46` で SYCL engine に組み込まれている。CUDA/HIP/Metal の同名環境変数読み取りは確認できなかった。GR の対応形状は `fused_gr_supported` が `n_embd == N && hc == HC && hc_lr == LR` に限定する。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`。

## 値と判定

`strata::bm_default_on(name, device, false)` が `std::getenv` で値を取得する。空でない値は先頭 1 文字だけを見て、`'0'` 以外なら ON、`'0'` なら OFF。文字列全体の解析、数値変換、空白除去、大文字小文字変換はしない。空文字は明示値として扱われず、渡された既定値 `false` に戻る。この helper は既定値が true の場合だけ Battlemage 判定を行うため、この変数は未設定・空文字とも全 GPU で OFF。根拠: `engine/sycl/include/strata/sycl_queue.hpp:193-200`; 呼び出し側: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3395-3397`。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `bm_default=false` の判定 | OFF | `1`, `true`, `-1`, ` 1`（先頭文字が `0` 以外） | 空文字、`0`, `0anything`（未設定と空文字は既定 OFF） |

したがって `true` / `false` の意味を解釈せず、たとえば `false` も先頭が `f` なので ON になる。境界値・負値の数値判定はなく、先頭文字だけで決まる。CLI 引数や設定ファイルによる上書きはこの読み取り箇所にはない。

## 有効になる条件

値が ON でも、次をすべて満たし、対象の reduce 分岐まで到達した場合に限り 8 件先行ロード版を選ぶ。

- SYCL の fused-GR が使われること。GR 入力の形状が上記の対応形状であること。
- `m.cached_lo` が true であること。通常の設定経路では `STRATA_GR_LO_REUSE` が有効で、かつ Battlemage デバイス、`gr_norm_split()` と `gr_down_sliced()` が有効、`gr_more_groups()`・`gr_large_grf()`・`gr_up_ilp()` が無効、`gr_up_cols() == 16`、および `gr_reuse_safe(...)` が true である必要がある。`gr_reuse_safe` は低ランク出力領域などと入力・出力領域の重なりを検査する。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:304-329,3301-3308`。
- `STRATA_GR_REDUCE_ILP` の判定は `m.cached_lo` の分岐内でだけ行われる。したがって `STRATA_GR_LO_REUSE` が無効、またはレイアウト等の条件不足で低ランク値を再利用しない場合、この変数だけを ON にしても影響しない。`STRATA_GR_LO_REUSE` は helper の既定値が true なので、未設定時は Battlemage で ON、それ以外で OFF。根拠: `engine/sycl/include/strata/sycl_queue.hpp:193-200`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3301-3308,3395-3397`。
- `lo_once` の経路、GF reduce の経路、または `cached_norm` の経路が先に選ばれないこと。`STRATA_SYCL_GR_LO_ONCE` が `atoi` で非 0 なら down-sliced 時に `lo_once` が優先される。`STRATA_PRIVATE_GR_F32_REG` が `atoi` で非 0 かつ GF 条件を満たす場合は GF 経路が優先される。cached-norm は `STRATA_SYCL_GR_CACHED_NORM=3`、`STRATA_SYCL_GR_NORM_BOUNDS` の先頭文字 `1`、および down-sliced / norm-split などの条件がそろうと成立し、成立時は `!cached_norm` 条件により cached-lo 設定を通らない。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79,569-576,2685-2689,3298-3306,3359-3397`。
- `STRATA_GR_NORM_SPLIT` と `STRATA_GR_DOWN_SLICED` は unset または `atoi` 非 0 が必要。`STRATA_GR_MORE_GROUPS`、`STRATA_GR_LARGE_GRF`、`STRATA_GR_UP_ILP` が有効、または `gr_up_cols()` の評価結果が 16 以外の場合も cached-lo 設定から外れる（`STRATA_GR_UP_COLS` の不正値は 16 に fallback する）。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:812-850,1203-1210,3303-3306`。

## 実行時の詳細

`fused_gr_read_multi` の低ランク再利用設定 `reuse_lo` は関数内 `static const` で初回に固定される。対象変数の `reduce_ilp` も関数内 `static const` で、実際に `m.cached_lo` の reduce 分岐へ初めて到達した時点で読み取られ、その後は同じプロセス内でキャッシュされる。実行中に環境を変更しても再評価されないため、変更を反映するにはプロセスの再起動が必要。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3301-3302,3395-3406`。

ON の場合、reduce カーネルは各出力について 8 個の slice 部分値を先行ロードしてから順番に加算し、低ランク行では平均と SiLU を計算して `lo` に保存する。OFF の場合は部分値を 1 個ずつ読みながら同じ順に加算する。いずれも `REUSE_LO` の計算を行い、後続の up カーネルが cached-lo のときにその値を再利用する。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:775-806,3395-3406,867-895,1213-1222`。

この変数専用の CLI オプション、子プロセスへの転送、fallback、終了処理は見つからなかった。fused-GR の一般的な不正引数チェックは別に存在するが、本変数の値によるものではない。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3510-3517`。

## ログと測定値

本変数の ON/OFF を直接表示するログや、値不正時の警告・エラーはない。低ランク再利用経路に入ると `strata: GR reuse enabled: normalized activation %d, low-rank SiLU %d` が stderr に出るが、これは `STRATA_GR_REDUCE_ILP` の状態を表示しない。根拠: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3303-3314,3395-3406`。

`docs/INTEL.md:582-612` は Battlemage 向けの一連の制御について、記載された構成で「no」の 8 制御が中立またはやや遅かったという集約的な説明を載せている。個別の測定値や `STRATA_GR_REDUCE_ILP` 単独の結果は示していないため、本書では個別の速度・正確性の測定結果を記載しない。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:193-200` — helper の空文字・先頭文字・Battlemage 既定値規則。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:304-329,3301-3314,3392-3410` — cached-lo の成立条件、優先される reduce 経路、対象カーネルの選択。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:775-806,867-895,1213-1222` — 先行ロード・加算順・SiLU 保存と後続再利用。
- `engine/sycl/CMakeLists.txt:46` — 対象ソースの SYCL engine への組み込み。
- `docs/INTEL.md:582-612` — Battlemage 制御群についての文書記述と測定情報の範囲。
