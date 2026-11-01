# `STRATA_TOPK_MULTI`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の長文脈 QSA decode select で、top-k を一つの CTA ではなく複数 CTA/ query で計算する経路を選びます。これは `STRATA_SELECT_LONG` が有効な window でのみ呼ばれる `qsa_block_topk_long()` 内の選択です。通常の `qsa_block_topk()` への切り替えであり、スコアや選択 ID の仕様を変える設定ではありません（`src/core/verify.cpp:1775-1781`, `src/kernels/cuda/qsa_select.cu:3086-3101`）。

実装は `STRATA_EXPERIMENTAL_SM60` を定義した CUDA ビルドにだけコンパイルされます。通常の CUDA ビルド、HIP、SYCL、Metal にはこの環境変数を読む top-k 実装がありません（`src/kernels/cuda/qsa_select.cu:3031-3037,3088-3101`; ビルド macro の定義は `CMakeLists.txt:236,280-284`）。

## 値と判定

値は `topk_multi_mode()` の最初の呼び出し時に `static const int` として一度だけ読み、未設定または空文字なら自動判定、それ以外は `std::atoi()` で変換します（`src/kernels/cuda/qsa_select.cu:3034-3039`）。

| 環境変数の状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | 自動判定 | 実行 device の compute capability major が 6 なら自動モード。それ以外は無効（`src/kernels/cuda/qsa_select.cu:3040-3051`）。 |
| 空文字 | 自動判定 | 未設定と同じ。 |
| `atoi` の変換結果が 0 | 明示 OFF | 無効。例: `0`、`false`、数値で始まらない文字列。 |
| `atoi` の変換結果が 0 より大きい | 明示 ON | 有効候補。例: `1`, `2`, `1suffix`。 |
| `atoi` の変換結果が負 | 自動判定へ移行 | `env >= 0` の明示値分岐には入らず、自動判定に進む。compute capability 6.x で条件を満たせば有効になり得る。 |

`atoi` は文字列全体の妥当性を検証しません。数値の後ろの文字列は判定に影響せず、変換できない先頭は 0 になります。読み取り後にプロセス環境を変更しても値は再評価されません。自動判定時の device 判定はスレッドローカルに device ごとに cache され、device 切り替え時に更新されます。`cudaGetDevice()` が失敗した場合は CUDA error を取得・クリアして無効を返します（`src/kernels/cuda/qsa_select.cu:3040-3051`）。

## 有効になる条件

明示 ON または自動モードでも、次の条件をすべて満たすときだけ multi-CTA top-k を起動します（`src/kernels/cuda/qsa_select.cu:3088-3096`）。

- CUDA の `STRATA_EXPERIMENTAL_SM60` ビルドである。
- verifier が長文脈 select を選び、`qsa_block_topk_long()` が呼ばれている。通常これは `STRATA_SELECT_LONG=1` が必要で、`STRATA_SELECT_LONG_AT`（既定 65,536 cells）以上の window で有効になります。build に multi-CTA scratch がない場合、`STRATA_SELECT_LONG=1` は stderr に `strata verify: STRATA_SELECT_LONG=1 needs the CUDA build with STRATA_EXPERIMENTAL_SM60; ignored` と出して無効になります（`src/core/verify.cpp:176-200,3076-3078`）。
- `STRATA_TOPK_OLD` が未設定である。設定値の内容は問わず、存在するだけで旧 top-k に戻ります（`src/kernels/cuda/qsa_select.cu:3090-3092`）。
- `nq > 0`、scratch が非 null、`active_blocks <= 0`、`nq <= MT_MAXQ`、`s.idx_block == R`、かつ `cap >= qsa_selection_width(kTopkMaxCells, s)`（同上）。
- mode が明示 ON、または自動モードで `max_blocks > TK_T * TK_PER`。自動 ON は compute capability 6.x のみで、register kernel の容量を超える場合に限られます（`src/kernels/cuda/qsa_select.cu:3040-3051,3093-3096`）。

条件を満たさなければ `qsa_block_topk()` を呼びます（`src/kernels/cuda/qsa_select.cu:3097-3101`）。従って、`STRATA_TOPK_MULTI=1` だけではこの経路を起動しません。別環境変数 `STRATA_SELECT_LONG` の条件や形状条件が別に適用されます。

## 実行時の詳細

multi-CTA 経路では、CTA 数は既定で `ceil(max_blocks / 2048)`、1 から `MT_NMAX` に clamp されます。別の `STRATA_TOPK_MULTI_N` が設定され、その `atoi` 結果が正なら固定 CTA 数を使い、同じ上限・下限を適用します。この値は関数内 static cache です（`src/kernels/cuda/qsa_select.cu:3054-3068`）。

起動するのは histogram kernel 4 回、count kernel、emit kernel の計 6 回です。`cudaGetLastError()` が失敗を返すと stderr に `qsa_block_topk multi: <CUDA error string>` を出し `exit(1)` します。成功時は呼び出し元へ戻り、条件不成立時は前述の通常経路を使います（`src/kernels/cuda/qsa_select.cu:3063-3071,3093-3101`）。

`STRATA_TOPK_MULTI` は設定有無や値を示す通常実行時ログを出しません。ビルドに multi-CTA 実装がない場合に警告するのは `STRATA_TOPK_MULTI` 自体ではなく、組み合わせて使う `STRATA_SELECT_LONG=1` の判定です（`src/core/verify.cpp:181-190`）。

## 根拠

- `src/kernels/cuda/qsa_select.cu:3031-3052` — compile guard、環境変数の変換、未設定・空文字時の compute capability 判定と cache。
- `src/kernels/cuda/qsa_select.cu:3054-3072` — CTA 数、multi-CTA kernel 群、エラー出力・終了。
- `src/kernels/cuda/qsa_select.cu:3086-3101` — runtime の形状・状態条件と通常 top-k への fallback。
- `src/core/verify.cpp:176-200,966-967,1775-1781,3076-3078` — 長文脈経路の opt-in、scratch、window 閾値と呼び出し。
- `CMakeLists.txt:236,280-284,539-550` — 実験 build macro と parity test の build 条件。parity test は `STRATA_TOPK_MULTI` の先頭文字が `1` であることを要求して独自に stderr/終了コードを返しますが、これは test executable の入力確認であり、本番 runtime の値判定とは異なります（`src/kernels/qsa_select_long_parity.cpp:181-187`）。
- `docs/OLDER_GPUS.md:178-185` — 4 基の GP100、全 expert 常駐、`--pipeline-windows 3` で 115K context の 400 token decode が 51.0 から 52.5 tok/s（+2.9%）という資料上の測定記載。これは `STRATA_SELECT_LONG` 全体の記載で、個別に `STRATA_TOPK_MULTI` の寄与を分離した値ではありません。資料は kernels のない build では「switch」を warning 付きで無視すると説明しますが、現行ソースでは warning 条件は `STRATA_SELECT_LONG=1` であり、`STRATA_TOPK_MULTI` 自体の警告ではありません。
