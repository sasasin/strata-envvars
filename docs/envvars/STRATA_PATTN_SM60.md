# `STRATA_PATTN_SM60`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。調査対象 checkout は `## main...origin/main` で、未コミット変更はなかった。

## 役割

CUDA の実験ビルドで、QSA の prompt attention を処理する score/value カーネルを選ぶための試験用スイッチ。`1` 固定の真偽値ではなく、`atoi` の結果が 0 以外なら選択を有効にする。対応経路では従来の decode attention の代わりに `ps_score_x_kernel` と `ps_value_d4_kernel` を使う。該当する call site は `Prefill::run_impl` の QSA attention（`engine/src/prefill/prefill.cpp:5553-5569`）、判定とログは `pattn_mode()`（`engine/src/kernels/cuda/qsa_pattn.cu:34-50`）。

## 値と判定

初回 `pattn_mode()` 呼び出し時に `std::getenv` で読み、未設定または空文字なら 0、それ以外は `std::atoi` の結果を使う。したがって文字列全体の厳密な数値検証はなく、先頭の空白と符号は `atoi` の規則で扱われ、数字以降は変換されない。数値として変換された値が 0 なら無効、0 以外なら有効側に進む（`engine/src/kernels/cuda/qsa_pattn.cu:35-50`）。

| ビルド | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA + `STRATA_EXPERIMENTAL_SM60` | 通常 attention | `1`, `2`, `-1`, `1tail`, `  +3` | 空文字, `0`, `0anything`, `true`, `false`, `tail` |
| それ以外（通常 CUDA、HIP） | 通常 attention | 非ゼロに変換される値は警告を出す | 空文字または 0 に変換される値 |

2 行目でも環境変数の判定自体は行われるが、カーネルは選択されない。CUDA ソースは `STRATA_EXPERIMENTAL_SM60` が定義され、かつ HIP でない場合だけカーネル本体を組み込む（`engine/src/kernels/cuda/qsa_pattn.cu:25-30,451-455`）。

## 有効になる条件

- 実験 CUDA ビルドであること。CMake の `STRATA_EXPERIMENTAL_SM60` は既定 OFF で、ON の場合にコンパイル定義を追加する（`engine/cmake/backends/cuda.cmake:28,76-80`）。カーネルソースは GPU engine の CUDA/HIP 共通ライブラリに含まれるが、実カーネル実装は CUDA かつ同 macro の場合だけ有効（`engine/cmake/strata_gpu_engine.cmake:8-17,90-96`; `engine/src/kernels/cuda/qsa_pattn.cu:25-30`）。
- QSA prompt attention のこの呼び出しに到達すること。融合 gate が成立すると候補カーネルを呼ばない。通常の prompt attention が成功した場合も候補は呼ばれず、失敗または `STRATA_PROMPT_ATTN_OLD` の指定時に候補へ進む（`engine/src/prefill/prefill.cpp:5540-5564`）。この変数は `getenv != nullptr` 判定なので、`STRATA_PROMPT_ATTN_OLD` は空文字でも指定扱い（同:5540）。
- 実行時に選択中の CUDA device の compute capability major が 6 であること。device 属性の major を device ごとに cache し、6 以外は候補関数が false を返す。minor は確認しない（`engine/src/kernels/cuda/qsa_pattn.cu:385-405`）。
- attention の形状と KV が対象であること: `head_dim == 256`、`n_head == 12 * n_head_kv`、正の `cap`、int8 K/V と scale/page table があり、Q4 K/V ではないこと。加えて `ceil(cap/64) <= 33`（実質 `cap <= 2112`）と、scratch に少なくとも 1 query 分が入ることが必要。満たさない場合は通常 attention に戻る（同:411-423）。

## 実行時の詳細

環境値は `pattn_mode()` の関数内 `static const int` 初期化で一度だけ読み取る。最初の呼び出しより後にプロセス環境を変更しても再評価されない。Strata の該当箇所に子プロセスへの転送はない（`engine/src/kernels/cuda/qsa_pattn.cu:35-50`; 呼び出し元 `engine/src/prefill/prefill.cpp:5559-5563`）。

候補カーネルは 64 cell 単位の score 計算と value 集約を起動し、scratch 容量に合わせて query を複数 batch に分ける。shape / scratch 条件を満たさない場合や device が compute capability 6 でない場合は false を返し、呼び出し元が decode attention の通常 loop を実行する（`engine/src/kernels/cuda/qsa_pattn.cu:402-437`; `engine/src/prefill/prefill.cpp:5556-5569`）。カーネル起動エラーでは false を返し、通常経路へ戻る。QSA attention 出力の計算順は decode 経路と一致させる設計で、Strata の資料も bit-for-bit と説明している（`engine/src/kernels/cuda/qsa_pattn.cu:3-13,438-448`; `docs/OLDER_GPUS.md:176-183`）。

この変数を参照する production call site は上記 1 箇所。`Prefill::run_layer_major` 内の別 QSA attention 経路（`engine/src/prefill/prefill.cpp:9461-9473`）には `pattn_mode()` / `qsa_pattn_batch()` の呼び出しがなく、この変数はそこで作用しない。

## ログと測定値

- 値が 0 の場合はこの判定からログを出さない。
- 値が非 0 で実験 CUDA ビルドなら、初回判定時に stderr へ `strata pattn: STRATA_PATTN_SM60=%d: the prompt path's QSA attention on the sm_6x score / value kernels (bit for bit qsa_decode_attn_batch; int8 K/V)` を出す。device や shape の適用条件を満たさなくても、このログは候補関数が呼ばれたことを示すだけで、実際の起動成功を示さない（`engine/src/kernels/cuda/qsa_pattn.cu:40-43`）。
- 値が非 0 でカーネル本体のない build なら stderr に `strata pattn: STRATA_PATTN_SM60 is set, but this build has no sm_6x kernels (CUDA with STRATA_EXPERIMENTAL_SM60 only); the usual attention runs` を出す（同:44-47）。
- 起動失敗時は最初の一度だけ stderr に `strata pattn: launch failed (%s); the usual attention runs instead` を出す。shape/device/scratch 不適合による false では、この関数自身は理由ログを出さない（同:411-423,438-446）。
- `docs/OLDER_GPUS.md:180-183` は、著者による測定として GP100 1 die・26K context で 1,536-query chunk の QSA layer attention が 43.3 ms から 30.8 ms、4 dies の 8K–150K token prompt で 2–3% less time と記す。同資料は Strata 側で未測定と明記しているため、一般的な性能値ではない。

## 根拠

- `engine/src/kernels/cuda/qsa_pattn.cu:25-50` — build 条件、環境値の変換、cache、ログ。
- `engine/src/kernels/cuda/qsa_pattn.cu:385-448` — device 条件、shape/scratch の拒否条件、起動と fallback。
- `engine/src/prefill/prefill.cpp:5540-5569` — prompt 経路の優先順位と通常 attention への fallback。
- `engine/src/prefill/prefill.cpp:9461-9473` — 別 prefill 経路では候補を呼ばないこと。
- `engine/cmake/backends/cuda.cmake:28,76-80`; `engine/cmake/strata_gpu_engine.cmake:8-17,90-96` — build option とソース組み込み。
- `docs/OLDER_GPUS.md:176-183` — 対象条件、設計説明、測定値と Strata 側の測定状況。
