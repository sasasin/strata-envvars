# `STRATA_IQ3S_GU_ROW_REUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の grouped-expert IQ3_S gate/up 計算で、2 行分の weight を処理するときに activation 側の読み出し・展開結果を共有する専用 kernel を選ぶ。通常の lane kernel に対する計算経路の切替であり、変数自体は gate/up の値を設定したり、down 計算を切り替えたりしない。`native_expert_grouped` は `L.gu_type == 21` を `launch_gu<21>` に渡し、その中でこの分岐を判定する（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6020-6037, 7767-7781, 7874-7878`）。

## 値と判定

`strata::bm_default_on` が `std::getenv` で値を読み、文字列全体ではなく先頭 1 byte だけを見る。未設定または空文字列は Battlemage 既定に戻る。空でない値は先頭 byte が `'0'` なら false、それ以外なら true であり、数値・真偽語としての parse、空白除去、大文字小文字変換はしない（`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。

| 条件 | unset / 空文字 | 設定時に reuse 判定が true | 設定時に reuse 判定が false |
|---|---|---|---|
| SYCL、`STRATA_GRID_SLM` が 0（既定） | `intel_gpu_gen(device)` が Battlemage なら true、それ以外は false | `1`、`true`、`false`、` 0`、`-0` など先頭が `0` 以外 | `0`、`0anything` など先頭が `0` |
| `STRATA_GRID_SLM` が 1 でビルド | この変数の判定コード自体がコンパイル対象外 | 該当なし | 該当なし |

環境変数で reuse 判定が true になっても、後述の実行条件に Battlemage 判定が別にあるため、非 Battlemage の SYCL GPU では専用 kernel は選ばれない。`intel_gpu_gen` は GPU 以外を Unknown とし、`STRATA_INTEL_GEN=battlemage` は Battlemage、`alchemist` / `unknown` はそれぞれの分類を強制する。未設定時はデバイス情報から分類し、Xe3 も Battlemage 扱いにする。不正値は無視され、`strata: STRATA_INTEL_GEN=%s is not battlemage, alchemist or unknown; ignored` を stderr に出す（`engine/sycl/include/strata/sycl_queue.hpp:139-171`）。

## 有効になる条件

専用 kernel を選ぶには、次をすべて満たす必要がある（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6025-6037`）。

- SYCL のこの grouped-expert dispatch を通り、gate/up type が IQ3_S（type 21）である。
- `STRATA_GRID_SLM` が 0。ソースでの既定値は 0 で、1 の build では row-reuse 分岐が除かれる（同ファイル `:484-489, 6025-6027`）。
- 環境判定後の `reuse` が true。
- `g_old_kernels` と `g_split_multi` がともに false。前者は初期値を `STRATA_OLD_IQ_MMVQ`、後者は `STRATA_EXPERT_SPLIT` から `env_on` で設定する。`env_on` は未設定・空文字・先頭が `0` の値を false、それ以外を true とする。`g_old_kernels` は `iq_set_old_kernels(bool)` でも変更可能だが、通常の CLI 上書きはこの経路では見つからない（同ファイル `:3927-3937, 6124-6128`）。
- `gu_lanes() == 8`。lane 数は `STRATA_GU_LANES` があれば `atoi` で読み、4/8/16/32 以外は `STRATA_EXPERT_LANES` に戻る。compile-time の既定値は 8（同ファイル `:1173-1180, 4481-4487`）。
- `L.n_embd == 2560` かつ `L.n_ff == 640`。
- `intel_gpu_gen(device) == Battlemage`。したがって明示的な非ゼロ値は、変数判定を true にするだけで GPU 条件を迂回しない。
- `native_expert_grouped` の通常 gate/up 経路が実行されること。`g_exp_phase == 2` では gate/up dispatch 自体を通らない。また `fused_gu_sycl` が成立すると type 21 も fused launcher に送られ、通常の `launch_gu<21>` 分岐を通らない。成立条件は expert mode 8、`v1` でない、Hadamard block なし、`n_ff` が 32 の倍数、旧 kernel / split を使わない、KQ split 有効、8 lanes、phase が 2 / 3 以外、対応 type である（同ファイル `:7797-7819`）。

CLI 引数がこの環境値を上書きする処理は、対象名の全参照および dispatch で確認できない。`STRATA_GU_LANES`、`STRATA_OLD_IQ_MMVQ`、`STRATA_EXPERT_SPLIT` と GPU 分類は、上記の個別条件として作用する。

## 実行時の詳細

`launch_gu<21>` の `static const bool reuse` は、`STRATA_GRID_SLM` が 0 の build で同関数の最初の呼び出し時に `bm_default_on` を評価し、その後はプロセス内で cache する。従って実行中に環境変数を変更しても再評価されない。評価に使う device も最初の呼び出し時の device で固定される（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6020-6028`）。

条件が成立すると、stderr に `strata: IQ3_S two-row GU reuse enabled (8 lanes, SIMD16, direct activation reads)` を一度出し、`launch_gu_row_reuse<21>` を起動して通常の lane kernel 選択へは進まない（同ファイル `:6030-6037`）。この launcher は 16-lane subgroup の SYCL kernel を投入する。この実装経路は kernel を起動するもので、子プロセスへ環境変数を転送する処理はない。kernel は 2 行を組にし、各 expert/token の activation を読み、IQ3_S の 2 weight 行それぞれとの dot 結果を gate または up の scratch 出力へ書く（同ファイル `:4326-4372, 4374-4425, 4428-4458`）。IQ3_S（`TG == 21`）では launcher の `e3` が定数 true となるため、この経路は `STRATA_EXPERT_ROW_E3` の値に依存しない（同ファイル `:4437-4451`）。

reuse 条件が成立しないときは通常の dispatch が続く。`g_old_kernels` が false で、`STRATA_IQ3S_GU_SLM` の判定が有効、かつ `L.n_embd == 2560` / `L.n_ff == 640` なら、その後段で SLM kernel を選ぶ。`STRATA_IQ3S_GU_SLM` も `bm_default_on` を使うが、既定値は false で、Battlemage でも明示的に有効化しなければ選ばれない。この分岐は `g_split_multi`、lane 数、Battlemage 条件を個別には検査しない。reuse 分岐が専用 kernel を選ぶと直ちに return するため、その呼び出しでは SLM 分岐に進まない（同ファイル `:6036-6055`）。

## ログと測定値

上記の有効ログは専用 kernel を実際に選んだときだけ出る。未設定/無効値や条件不成立の理由を示す個別ログはなく、通常 kernel へ進む。呼び出し直後の `check("native_expert_grouped/gu")` はこのファイル内では `e = 0` の stub で、ここに環境変数固有のエラー表示・終了処理はない（同ファイル `:72-84, 7883`）。

`docs/INTEL.md:584-587` の性能値は build option と14個の runtime control を合わせた測定であり、この変数単体の差分測定ではないため、本変数の性能値としては記載しない。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:139-200` — GPU 世代分類と `bm_default_on` の値判定。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:484-489, 1173-1180, 3927-3937, 4481-4487` — build macro、lane 数、関連する実行条件。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4326-4458` — 2 行 reuse kernel と launcher。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6020-6055, 7767-7819, 7874-7884` — 読み取り、分岐、呼び出し元、fallback とログ後の処理。
