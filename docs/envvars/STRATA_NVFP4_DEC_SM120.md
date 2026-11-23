# `STRATA_NVFP4_DEC_SM120`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の Blackwell sm_120/sm_121 用 NVFP4 grouped decode/verify カーネルを opt-in で選びます。環境変数が有効でも、この経路の呼び出し条件を満たさない場合は既存の grouped expert カーネルに進みます。読み取りは `nvfp4_decode_sm120_available()` で行われ、主な呼び出し元は `native_expert_grouped()` です（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:392-400`、`engine/src/kernels/cuda/iq_kernels.cu:7085-7104`）。

## 値と判定

`std::getenv` の結果を初回 `nvfp4_decode_sm120_available()` 呼び出し時に `static const bool` へ保存します。未設定または空文字列なら無効です。それ以外は先頭 1 文字だけを見て、`'0'` なら無効、別の文字なら有効です。数値・真偽値としての全体 parse、空白除去、大文字小文字変換はありません（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:392-399`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 実装入り CUDA ビルド。テスト用 override が未設定（既定 `-1`） | 無効 | `1`、`true`、`false`、`abc`、` 0` | 空文字、`0`、`0anything` |
| 実装入り CUDA ビルド。`nvfp4_decode_sm120_set_override(mode)` が `mode >= 0` | override が環境変数に優先 | `mode != 0` | `mode == 0` |
| CUDA 以外、または対象カーネルを含まないビルド | 無効 | なし | 常に無効 |

値は一度初期化されるとプロセス内でキャッシュされ、後から環境を書き換えても再評価されません。API の override は `-1` なら環境値に従い、0 以上なら環境値を置き換えます。公開ヘッダーはこれを test/benchmark override と定義しています（`engine/include/strata/kernels/nvfp4_decode_sm120.hpp:13-18`）。

## 有効になる条件

- CMake が CUDA compiler 13.0 以降で、CUDA architecture の指定から 120 または 121 が選ばれる必要があります。`all` / `all-major` は両方を追加します。この条件を満たすと実装 `.cu` が入り、そうでない場合は `nvfp4_decode_sm120_absent.cpp` の stub が選ばれて常に `false` を返します（`engine/cmake/backends/cuda.cmake:101-130`）。HIP ビルドも stub を追加します（`engine/cmake/strata_gpu_engine.cmake:107-111`）。
- 実装入りビルドでは現在の CUDA device の compute capability が 12.0 または 12.1 である必要があります。device の判定は device ごとに cache されます（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:365-383`）。
- grouped expert の呼び出しで `STRATA_GROUPED_V1` が `env_on()` 判定で有効になっていないこと、`cap_entries > 10`、gate/up と down の型がともに NVFP4（type 40）、`gu_nib` が false、`had_block == 0`、`g_exp_phase == 0` が必要です。`STRATA_GROUPED_V1` は unset / 空文字 / 先頭が `0` なら無効で、それ以外は有効です（`engine/src/kernels/cuda/iq_kernels.cu:3689-3692, 6831-6832, 7092-7095`）。
- さらに専用関数内で `n_embd` が 256 の倍数、`n_ff` が 64 の倍数である必要があります。寸法が合わなければ `false` を返し、呼び出し元は通常の grouped expert 実装へ続きます（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:402-409`、`engine/src/kernels/cuda/iq_kernels.cu:7094-7112`）。
- CLI 引数によるこの環境変数の上書きは、確認した Strata 所有ソースにはありません。

## 実行時の詳細

`native_expert_grouped()` は `cap_groups` または `cap_entries` が 0 以下なら先に戻るため、専用判定にも到達しません。上記の grouped verify 条件を満たし、`nvfp4_decode_sm120_available()` が true の場合、scratch の後半を `hq_ptr` として専用関数へ渡します。専用関数は gate/up と SwiGLU・Q8_1 化の kernel、続いて down kernel を同じ stream に launch し、`cudaGetLastError() == cudaSuccess` の結果を返します。成功時は呼び出し元が return し、失敗時は専用 kernel の結果を採用せず通常経路へ進みます（`engine/src/kernels/cuda/iq_kernels.cu:7088-7103`、`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:402-421`）。

環境値は専用関数の最初の availability 判定で一度だけ読む cache です。GPU capability の判定も device ごとに cache されます。通常の Strata 実行経路に override の呼び出し箇所はなく、リポジトリ内で setter を呼ぶ箇所は CUDA test code です（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:365-399`、`engine/tests/cuda/nvfp4_decode_sm120_test.cpp:118-129`）。

## ログと測定値

この環境変数の有効・無効を示す実行時ログはありません。専用関数が失敗を返す場合も、この分岐自体は理由を出力せず通常経路へ続きます（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:421`、`engine/src/kernels/cuda/iq_kernels.cu:7099-7104`）。ソースコメントには別の DFlash2 条件での速度記載がありますが、ここでは測定条件や観測結果を独立確認したものとして扱いません（`engine/src/kernels/cuda/nvfp4_decode_sm120.cu:395`）。

## 根拠

- 直接の環境読み取り、値の判定、cache、override、device gate: `engine/src/kernels/cuda/nvfp4_decode_sm120.cu:365-400`
- NVFP4 grouped kernel の形状 gate と launch 結果: `engine/src/kernels/cuda/nvfp4_decode_sm120.cu:402-421`
- grouped verify 側の選択条件と fallback: `engine/src/kernels/cuda/iq_kernels.cu:7085-7112`
- CUDA 実装の build 選択: `engine/cmake/backends/cuda.cmake:101-130`
- HIP stub の追加: `engine/cmake/strata_gpu_engine.cmake:107-111`
