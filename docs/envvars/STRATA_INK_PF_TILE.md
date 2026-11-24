# `STRATA_INK_PF_TILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2-Mini の CUDA MoE dispatcher で、SF4 または MX8 expert の prefill を 64-token tile の FP16 Tensor Core kernel に切り替えるかを制御する。無効の場合は従来の 16-token kernel を使う。分岐は `launch_ink_moe_dispatch_only` にあり、対象 kernel は gate/up と down の両方に起動される（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3666-3687,3724-3749`）。

変数を有効にしても、router、選択 expert、重み、出力の arithmetic はこの切替では変えない。64-token kernel の設計コメントは 16-token kernel と同じ arithmetic で bit-identical としている（`engine/src/inkling2/cuda/ink_moe_prefill.cuh:1-18`）。

`docs/SETTINGS.md:402` は NVIDIA と AMD の設定として掲載するが、この commit で実際に値を読む箇所は CUDA 実装だけである。AMD/HIP、CPU、Metal、SYCL 側でこの名前を読む処理は見つからなかった。

## 値と判定

`std::getenv` の結果について、未設定でないことに加えて先頭文字だけを調べる。先頭文字が ASCII `0` の場合だけ無効で、それ以外は有効。文字列全体の parse、空白除去、大文字小文字変換、数値検証はしない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3681-3684`）。

| 環境変数値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 `""` | 有効 |
| `0`, `0anything` | 無効 |
| `1`, `true`, `false`, `OFF`, ` 0` | 有効 |

有効/無効の値に CLI 引数や別の環境変数による優先順位はない。`force_exact_dec` は別の引数であり、Blackwell kernel の選択を変えるため間接的にこの環境変数が効くかどうかに関係するが、値自体を上書きしない（同 `:3678-3684`）。

## 有効になる条件

- `strata-inkling` の CUDA backend がビルドされ、その CUDA dispatcher が実行されること。Inkling CUDA backend の追加は `STRATA_ENABLE_CUDA` の条件下にある（`engine/src/inkling2/CMakeLists.txt:192-198,237-239`）。
- MoE dispatch の `M` が 256 以上であること。64-token tile の下限は `kInkPrefillTileMinM = 256`（`engine/src/inkling2/cuda/ink_moe_prefill.cuh:17-18`）。
- `launch_ink_moe_dispatch_only` が FP16 Tensor Core 経路を選ぶこと。コード上の条件は `M >= 24` かつ sm_120 経路でなく、デバイス capability が INT8 Tensor Core を持つこと。capability 判定は CUDA device の major が 8 以上（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:2305-2311,3678-3684`; `engine/include/strata/core/ink_caps.hpp:16-18`）。
- 現在の layer の expert 情報に SF4 または MX8 が含まれること（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3684`）。S_K や GGUF のみの layer ではこの変数による tile 切替は起きない。
- sm_120 が利用可能で通常の Blackwell kernel を選ぶ場合、`use_fp16_tc` が false になるため本変数はその dispatch に影響しない。`force_exact_dec` が true なら sm_120 経路を選ばず、ほかの条件を満たす FP16 TC 経路では本変数の判定対象になり得る（同 `:3678-3684`）。

## 実行時の詳細

値は `launch_ink_moe_dispatch_only` 内の関数ローカル `static const bool` として初回評価時に読み取られ、以後そのプロセス内では cache される。起動後に環境を変更しても判定は更新されない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3683`）。

有効時は bin kernel に 64 行 tile を渡し、SF4/MX8 用の `k_ink_moe_pf_fp16tc` を gate/up と down でそれぞれ起動する。無効時は 16 行単位で bin し、既存の FP16 TC kernel 経路に入る（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3684-3688,3724-3749`; `engine/src/inkling2/cuda/ink_moe_prefill.cuh:17-27`）。混合 layer で S_K expert もある場合、共有される `tile_rows` によって S_K Tensor Core kernel も 64 行 variant を選ぶ（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3784-3798`）。GGUF expert の処理はこの変数で切り替わらない（同 `:3812-3844`）。

通常の runner は batch `M`、layer の expert 情報、device に応じて dispatcher を呼ぶ。単一 GPU、hybrid、expert parallel の経路から同じ dispatcher が使われる（`engine/src/inkling2/cuda/ink_runner.cuh:3444-3509`; `engine/src/inkling2/cuda/ink_hybrid.cuh:2505-2519,2720-2731`）。環境変数の評価自体に CLI 引数・サーバーモードによる別規則はない。

## ログと測定値

この変数の値や選択 kernel を直接表示する Strata のログ、警告、エラー文言は実装にない。`docs/DETAILS.md` に本変数の測定値は見つからず、速度向上はここでは断定しない。ソースコメントには算術結果が bit-identical との設計記述があるが、これは当調査で実行検証した測定結果ではない（`engine/src/inkling2/cuda/ink_moe_prefill.cuh:9-11`）。

## 根拠

- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3666-3688` — dispatcher、GPU capability と値の判定、bin tile の選択。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3724-3749,3784-3798,3812-3844` — SF4/MX8、混合 S_K、GGUF の実行経路。
- `engine/src/inkling2/cuda/ink_moe_prefill.cuh:1-27` — 64-token prefill kernel の範囲と設計上の算術説明。
- `engine/include/strata/core/ink_caps.hpp:14-18` — device capability 判定。
- `engine/src/inkling2/CMakeLists.txt:192-198,237-239` — CUDA backend の build 条件。
- `engine/src/inkling2/cuda/ink_runner.cuh:3444-3509`; `engine/src/inkling2/cuda/ink_hybrid.cuh:2505-2519,2720-2731` — 通常 runner と hybrid dispatcher 呼び出し。
- `docs/SETTINGS.md:402` — 候補設定表の記載（実装範囲との食い違い）。
