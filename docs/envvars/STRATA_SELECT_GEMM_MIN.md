# `STRATA_SELECT_GEMM_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の QSA prefill でブロックスコア計算に oneMKL GEMM を選ぶ自動判定の下限を、ブロック数で指定する。既定値は 2,048。閾値だけでは GEMM は有効にならず、自動モードでは GPU 世代が Battlemage であることも必要となる。GEMM が選ばれて実行できた場合はブロックスコアの計算方法が変わり、その後の top-k 選択へ渡されるスコアを変え得る。選択結果や生成内容が同一になる保証は、このコードからは確認できない。実装は `Prefill::run_impl` 内の QSA 選択処理にある（`engine/sycl/src/prefill/prefill.cpp:3645-3688`）。

## 値と判定

`std::getenv` が返す文字列を `std::atoll` で `int64_t` に変換する。環境変数が未設定なら 2,048。設定済みの空文字や数値に変換できない文字列は、変換結果 0 として扱われる。数値全体の妥当性検査、後続文字の検査、範囲 clamp はない。したがって、例えば `"12tail"` は数値接頭部 12、`" 12"` は 12、`"true"` は 0 として扱われる。数値部分のない値は 0 となる。`atoll` の表現範囲を超える入力について Strata は独自の検査やエラー処理をしていないため、その結果はここでは規定しない。閾値は `active >= sel_gemm_min` と比較される（`engine/sycl/src/prefill/prefill.cpp:3686-3688`）。

| 判定状態 | `STRATA_SELECT_GEMM_MIN` が未設定 | 設定値の例 | 閾値条件 |
|---|---:|---|---|
| `STRATA_SELECT_GEMM` が未設定、または負数に変換される値（自動モード） | 2,048 | `2048` は 2,048 以上、`0`・空文字・`true` は 0 以上、`-1` は -1 以上で条件を満たす | `active` が変換後の閾値以上なら真 |
| `STRATA_SELECT_GEMM` が 0 に変換される値 | 2,048 | `0`、空文字、`true` | この変数の閾値は使われず、自動選択は無効 |
| `STRATA_SELECT_GEMM` が正数に変換される値 | 2,048 | `1`、`2` | この変数の閾値を問わず GEMM 選択フラグは真 |

上表の `STRATA_SELECT_GEMM` は同じコード箇所で `std::atoi` により読み取られ、未設定時は -1 となる。設定済みで数値に変換できない文字列は 0 となり、自動ではなく GEMM 無効の分岐になる。つまり、この文書の変数が閾値として働くのは `STRATA_SELECT_GEMM` の変換結果が負数のときだけである（`engine/sycl/src/prefill/prefill.cpp:3685-3688`）。

## 有効になる条件

- この読み取りと分岐は `engine/sycl/src/prefill/prefill.cpp` の SYCL 実装にある。CUDA、HIP、Metal の実装からこの変数を読む参照はなく、同じ動作をそれらの backend へ一般化できない（`engine/sycl/src/prefill/prefill.cpp:3685-3688`）。
- 値が閾値条件を満たしても、自動モード（`STRATA_SELECT_GEMM` が未設定または負数）では `strata::intel_gpu_gen(...) == Battlemage` が必要。その他の世代では自動判定が偽となる（`engine/sycl/src/prefill/prefill.cpp:3687-3688`）。
- `STRATA_SELECT_GEMM` が 0 に変換されると GEMM を選ばず、正数なら閾値に関係なく選択フラグを真にする（`engine/sycl/src/prefill/prefill.cpp:3685-3688`）。
- `STRATA_SELECT_OLD` が設定されていると、空文字を含め `old_sel` が真になり、GEMM 実行条件 `!old_sel` を満たさない（`engine/sycl/src/prefill/prefill.cpp:3674-3675,3692`）。
- GEMM の実行にはさらに attention scratch が存在すること、QSA の `idx_dim == 128` と `idx_n_head == 4`、計算された `sel_tile >= 256` が必要。条件を満たさない場合は GEMM を実行せず後続のスコア計算へ進む（`engine/sycl/src/prefill/prefill.cpp:3689-3693,3713-3717`）。
- 判定位置は prefill 内の QSA 層のブロックスコア選択ループである。QSA 層がなくこの位置に到達しないモデルや、SYCL prefill を通らない経路では、この値による選択は行われない（`engine/sycl/src/prefill/prefill.cpp:3645-3668`）。CLI とサーバーモードでこの環境変数を別途優先・上書きする処理は、候補名の全参照からは確認できない。

## 実行時の詳細

閾値は `run_impl` のローカル static として初回評価時に読み込まれ、以後そのプロセス内ではキャッシュされる。したがって、最初の評価後に環境を書き換えても再読み込みされない。評価まで値を読まない実装であり、プロセス起動時の一括読み取りではない（`engine/sycl/src/prefill/prefill.cpp:2693-2695,3686`）。

各 QSA prefill バッチについて、コードはバッチ末尾 query の step table にある `n_bid` に 1 を足して `active` とし、自動モードでは `active >= sel_gemm_min` と Battlemage 判定を組み合わせて GEMM の選択フラグを決める。閾値の単位はコードコメント上「blocks (4 cells each)」。選択フラグが真でも、上記の scratch・形状・tile 条件を満たす場合に限り、`active` 範囲を `sel_tile` ごとに分けて oneMKL FP32 GEMM と `qsa_block_scores_reduce` でスコアを計算する。top-k はその後に同じループで実行される（`engine/sycl/src/prefill/prefill.cpp:3666-3673,3686-3705,3718-3719`）。

GEMM 実行中に例外が起きると、stderr に `prefill: the GEMM block scores failed (%s); the warp kernel instead` を一度だけ出し、そのバッチは後続のスコア計算へ進む。GEMM が完了しなかった場合は tensor-core スコア計算を試し、それが選ばれない／使えない場合は `qsa_block_scores` の warp 経路に進む。環境変数の値自体が無効だという警告やエラー、プロセス終了はこの読み取り箇所にはない（`engine/sycl/src/prefill/prefill.cpp:3706-3717`）。

## ログと測定値

閾値の読み取りや GEMM の選択だけを知らせるログはない。GEMM 実行時の例外では、上記の stderr メッセージを出して fallback する（`engine/sycl/src/prefill/prefill.cpp:3707-3710`）。近傍コメントには特定 GPU での閾値や性能・スコア差の記述があるが、再現に必要な測定条件一式はこの箇所に揃っていないため、一般的な測定値としては記載しない（`engine/sycl/src/prefill/prefill.cpp:3676-3684`）。`docs/DETAILS.md` および関連する説明文書には、この変数固有の説明を確認できなかった。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:2693-2695` — `Prefill::run_impl` の実装。
- `engine/sycl/src/prefill/prefill.cpp:3645-3673` — QSA 層でのスコア選択位置、`active` の算出。
- `engine/sycl/src/prefill/prefill.cpp:3674-3719` — 関連環境変数、閾値、GEMM 条件、例外ログおよび fallback。
