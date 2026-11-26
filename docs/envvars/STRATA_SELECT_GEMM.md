# `STRATA_SELECT_GEMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

SYCL prefill 中の QSA block selection で、pooled indexer keys と indexer queries のスコア計算に oneMKL FP32 GEMM を使うかを選ぶ。`1` 以上ならカード世代・active block 数に関係なく GEMM を選択し、`0` は warp scorer に固定する。未設定または負数は自動選択となり、既定では active blocks が閾値以上の Battlemage GPU だけが GEMM 候補になる。選んだスコアから `qsa_block_topk` が selection ID を作るため、経路は prompt の選択結果に関わる。CUDA/HIP の同名変数読み取りはなく、この制御は SYCL prefill の実装に限られる。`engine/sycl/src/prefill/prefill.cpp:3666-3719`

## 値と判定

値は `std::getenv` で読み、未設定は `-1`、設定時は `std::atoi` で整数化する。文字列全体の妥当性検査はなく、先頭の整数変換結果だけで `> 0` / `< 0` / `== 0` を判定する。したがって空文字、`true`、`false`、`0anything` は `0` となり warp 固定、`1anything` は `1` となり GEMM を要求する。先頭の空白や符号は `atoi` の変換規則に従う。数値に変換できない文字列も `0` になる。`engine/sycl/src/prefill/prefill.cpp:3685-3688`

| `STRATA_SELECT_GEMM` の状態 | mode | 選択判定 |
|---|---:|---|
| unset | `-1` | `STRATA_SELECT_GEMM_MIN` 以上の active blocks かつ Battlemage なら GEMM 候補 |
| `0` に変換される値（例: `0`, 空文字, `false`, `0anything`） | `0` | warp scorer を使用 |
| 正数に変換される値（例: `1`, `2`, `1anything`） | 正数 | 常に GEMM を候補にする |
| 負数に変換される値（例: `-1`, `-2`） | 負数 | unset と同じ自動選択 |

自動選択の閾値 `STRATA_SELECT_GEMM_MIN` も同じ場所で一度だけ `std::atoll` され、unset 時は `2048` blocks。設定値に clamp や明示的な検証はないため、閾値以上かどうかをその変換値で比較する。`engine/sycl/src/prefill/prefill.cpp:3686-3688`

## 有効になる条件

- GEMM 判定は `engine/sycl/src/prefill/prefill.cpp` の SYCL `Prefill::run_impl` 内にある。非 SYCL 実装にはこの環境変数の読み取りがない。`engine/sycl/src/prefill/prefill.cpp:2692-2694, 3685-3688`
- unset / 負数の自動選択では、`active >= STRATA_SELECT_GEMM_MIN` かつ `strata::intel_gpu_gen(...) == Battlemage` が必要。デバイス世代判定は `STRATA_INTEL_GEN` による override を受けるため、同変数で `battlemage` を指定すれば自動選択条件に影響し、`unknown` なら Battlemage 条件を満たさない。`engine/sycl/src/prefill/prefill.cpp:3687-3688`; `engine/sycl/include/strata/sycl_queue.hpp:141-156`
- `STRATA_SELECT_GEMM=0` は自動選択条件を無視して GEMM 判定を false にする。正数は閾値と GPU 世代の条件を無視して GEMM 候補にする。
- GEMM 候補でも、`STRATA_SELECT_OLD` が設定されている場合は GEMM 経路を使わず warp scorer へ進む。値の内容ではなく設定有無を見ている。`engine/sycl/src/prefill/prefill.cpp:3674-3675, 3692-3717`
- さらに `m.attn_scratch != nullptr`、QSA shape が `idx_dim == 128` かつ `idx_n_head == 4`、計算された `sel_tile >= 256` が必要。条件に合わない場合は GEMM を試さず既存 scorer に進む。`engine/sycl/src/prefill/prefill.cpp:3689-3694`
- GEMM が使えない、または試行後に完了しなかった場合、既存の tensor-core scorer が利用可能ならそちらを試し、それも使えない場合は warp scorer に fallback する。`STRATA_SELECT_GEMM` はこの fallback を無効にしない。`engine/sycl/src/prefill/prefill.cpp:3713-3717`

## 実行時の詳細

環境値は `Prefill::run_impl` 内の関数局所 `static` 初期化子で読み取られる。最初にその選択コードへ到達したときの値がプロセス内で cache され、同じプロセスで後から環境を変更しても反映されない。`STRATA_SELECT_GEMM_MIN` も同様に cache される。CLI 引数や設定ファイルから値を上書きする処理は、この変数の参照経路にはない。`engine/sycl/src/prefill/prefill.cpp:2693-2697, 3685-3688`

GEMM 経路では active blocks を `sel_tile` 幅の区間に分け、各区間で oneMKL の column-major FP32 GEMM を実行してから `qsa_block_scores_reduce` に渡す。全区間の処理後に `sel_done` を立て、その score を `qsa_block_topk` が選択 ID に変換する。GEMM の `std::exception` は握りつぶさず理由を stderr に一度だけ出し、その回は既存 scorer に fallback する。`engine/sycl/src/prefill/prefill.cpp:3689-3719`

## ログと測定値

通常の unset / warp / GEMM 選択を通知するログはない。GEMM 中の例外時には、プロセスで最初の一度だけ stderr に次を出し、warp scorer に fallback する。

```text
prefill: the GEMM block scores failed (<例外文字列>); the warp kernel instead
```

文字列は `engine/sycl/src/prefill/prefill.cpp:3707-3711`。ソースコメントには特定 GPU / prompt 長での速度・スコア差の記述があるが、測定条件の全体をこの実装から確定できないため、一般的な性能値としては記載しない。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:3666-3719` — active block の計算、旧 scorer の優先、環境変数の読み取り、GEMM eligibility・計算・fallback・top-k。
- `engine/sycl/include/strata/sycl_queue.hpp:141-156` — 自動判定に使う Intel GPU 世代と `STRATA_INTEL_GEN` override。
