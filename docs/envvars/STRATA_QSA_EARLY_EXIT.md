# `STRATA_QSA_EARLY_EXIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の block-score 多重カーネルで、各 CTA がクエリを共有メモリへ読み込む前に、自分の担当範囲が全クエリの有効 block 範囲外かを判定して早期 return するかを切り替える。ON では `top`（全クエリの `n_bid` の最大値）を求め、CTA の先頭 block `blockIdx.x * SCORE_WARPS` が `top` を超える CTA はクエリを読み込まず終了する。OFF では全 CTA が先にクエリを読み込み、その後に担当範囲を走査する。スコア計算式とその後の top-k 選択はこのスイッチで切り替わらない。CUDA/HIP 側の `block_scores_multi_body` と SYCL 側の同等カーネルに実装がある（`engine/src/kernels/cuda/qsa_select.cu:979-1003`, `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1128-1169`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 各読み取り箇所（CUDA/HIP または SYCL） | ON | `1`, `2`, `-1`, `1abc` | 空文字, `0`, `-0`, `true`, `false`, `0anything` |

## 値と判定

読み取りは `getenv` の null 判定後、`std::atoi(v) != 0`。未設定は ON。設定済みなら空文字を含め `atoi` の結果が 0 のとき OFF、それ以外は ON となる。`atoi` による整数変換で、文字列全体の妥当性や大文字小文字を検査しない。先頭の空白と符号は変換規則に従い、数値の後ろの文字列は判定に使われない（例: `1abc` は ON、`0anything` は OFF）。`true` / `false` は数値として始まらないため 0 扱い。値の clamp、別設定値への fallback はない。CUDA/HIP の通常・slot 系経路は `scores_early_exit()` の static 値を共有し、CUDA と SYCL の rows 経路および SYCL の通常経路にはそれぞれ関数内 static がある（`engine/src/kernels/cuda/qsa_select.cu:1607-1615,1997-2014,2295-2306`; `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1574-1592,1632-1637`）。

## 有効になる条件

- CUDA/HIP の通常 `qsa_block_scores` は、`nq <= 8`、`active_blocks <= 0`、かつ `STRATA_SCORES_MULTI` が未設定または `atoi` で非ゼロの場合に、多重スコア経路の候補になる。Turing/Volta では `scores_halve_on()` が true なら別カーネルへ進み、この変数は通常経路では使われない（`STRATA_SCORES_HALVE` による上書きあり）。`STRATA_QSA_ROWS` が厳密に文字列 `1` で `nq <= 4` の場合も別の rows kernel に進み、通常経路のこの変数は使わない（`engine/src/kernels/cuda/qsa_select.cu:1607-1609,2179-2191,2194-2229`）。
- CUDA/HIP の slot / slot-group scorer は `STRATA_SCORES_MULTI` が有効で、query 数・group 数・各 group のサイズなどの上限を満たす場合に多重カーネルを使う。条件不足や `STRATA_SCORES_MULTI=0` では呼び出し側の個別 scorer に fallback する。slot-group で `STRATA_QSA_ROWS=1` かつ最大 group が 4 query 以下なら別の rows kernel に進み、この変数は使わない（`engine/src/kernels/cuda/qsa_select.cu:1997-2052`）。
- CUDA/HIP の `QsaScoreRows` overload は verify の batch rows 経路から呼ばれる。CUDA では `STRATA_BATCH_ATTN_ROWS` が有効で、batch/recurrent 条件を満たし、行数上限内で、各行が KV streaming でない場合にこの経路になる（`engine/src/core/verify.cpp:2191-2200,2218-2230`）。この overload は `STRATA_SCORES_MULTI` とは別に対象変数を読み取る（`engine/src/kernels/cuda/qsa_select.cu:2295-2306`）。
- SYCL の通常経路では `STRATA_SCORES_MULTI` が未設定または `atoi` で非ゼロ、`nq <= 8`、`active_blocks <= 0` が必要。満たさない場合は通常の block-score kernel へ進み、対象変数は使われない。SYCL の `QsaScoreRows` 経路でも対象変数を読む（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1574-1592,1625-1675`）。
- verify の `sel_long_` 経路は `qsa_block_scores_long` を使うため、この変数の対象外（`engine/src/core/verify.cpp:2266-2274`）。CLI やサーバー引数がこの環境変数の値を上書きする処理は、確認した読み取り・呼び出し経路にはない。

## 実行時の詳細

読み取り値は各関数内 `static` に初回評価時に保存される。したがって同じ読み取り箇所について、初回評価後にプロセス環境を変更しても反映されない。別々の static を持つ rows / 通常経路は独立に初回評価される。CUDA/HIP では `scores_early_exit()` を使う多重カーネルへ bool を渡し、SYCL もカーネル投入時に bool をコピーして渡す。

ON の場合、CUDA/HIP は query ごとの `n_bid` を共有メモリに置き、CTA ごとの先頭 block が batch の最大 `n_bid` より大きければ return し、残った CTA だけがクエリを staging する。OFF では全 CTA が staging を済ませてから有効範囲を調べる。SYCL も同じ順で判定・return・staging を行う。ループ内では各 query の `n_bid` を超える block のスコアを書かず、対象変数はその範囲判定やスコア値を変更しない（`engine/src/kernels/cuda/qsa_select.cu:985-1032`; `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1142-1169,1171-1187`）。CUDA ソースコメントは `=0` で従来の staging に戻し、スコアは同じ bit と記しており、実装も staging の順序と CTA return 以外のスコア演算を共用する（`engine/src/kernels/cuda/qsa_select.cu:1611-1615,979-1032`）。

## ログと測定値

この変数の値や ON/OFF を知らせる専用ログはない。通常のカーネル起動エラーは CUDA/HIP 側で `qsa_block_scores multi: %s`、slot 系で `qsa_block_scores_slots: %s` / `qsa_block_scores_slot_groups: %s`、rows 側で `qsa_block_scores_rows: %s` を stderr に出して `exit(1)` する。rows の形状不一致は `qsa_block_scores_rows: unsupported geometry` を出して終了するが、これらは環境変数の値に固有の警告ではない（`engine/src/kernels/cuda/qsa_select.cu:2011-2014,2046-2052,2225-2229,2298-2306`）。SYCL の形状不一致も同じ unsupported geometry 文言で終了する（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1574-1582`）。`docs/DETAILS.md` にこの変数の条件付き測定値や専用説明は見つからなかったため、性能値は記載しない。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:979-1042` — 多重スコア kernel の staging / early return とスコア演算。
- `engine/src/kernels/cuda/qsa_select.cu:1607-1615,1997-2052,2194-2306` — 値の読み取り、cache、CUDA/HIP 呼び出し条件。
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1128-1190,1574-1592,1625-1690` — SYCL 実装と呼び出し条件。
- `engine/src/core/verify.cpp:2191-2230,2266-2276`; `engine/sycl/src/core/verify.cpp:1484-1522` — verify の rows / long-context 呼び出し条件。
- `engine/cmake/strata_gpu_engine.cmake:80-96` — CUDA engine に `qsa_select.cu` を含める。
