# `STRATA_HC_Q8_TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の fused GR における Q8_0 hyper-connection 読み取りで、INT8 Tensor Core の up projection、および任意で down projection も使う経路を選ぶ。CUDA compute capability major が 8 以上なら既定で有効。`1` は fast down + INT8 Tensor Core up、`2` 以上は INT8 Tensor Core down + up を選ぶ。無効にしても Q8_0 読み取り自体を止める設定ではなく、後続の BF16 Tensor Core 経路（既定で有効）または通常の Q8 経路へ進む（`engine/src/kernels/cuda/fused_gr.cu:3902-3923,3958-3988`）。

この分岐に到達するのは `FusedGrArgs` に `q8_down` と `q8_up` の両方が渡されたときだけ。これはモデルの hyper-connection 重みが Q8_0 として供給される経路であり、重みの読み込みをこの変数が有効化するわけではない。通常の CUDA `generate` は Q8_0 hyper-connection を含む GGUF で `STRATA_HC_Q8` を自動設定する場合がある。HIP では本変数の判定関数が常に 0 を返し、この INT8 Tensor Core 分岐を使わない（`engine/src/kernels/cuda/fused_gr.cu:4284-4291`; `engine/src/program/generate.cpp:5164-5168`; `engine/src/core/native_dense.cpp:683-690`）。

`docs/SETTINGS.md:101` は対応先を「NVIDIA and AMD」と記すが、実装は HIP で無効であり、CUDA の sm_80 以上を条件にしている。したがって同資料の AMD 表記は、この実装の適用範囲と一致しない。

## 値と判定

`hc_q8_tc_mode()` の関数内 `static const int` が、初回呼び出し時に `std::getenv` で読み、空でなければ `std::atoi` で整数化する。値全体の厳密な検証はしない。`atoi` のため、先頭空白と符号は許容され、数値の後ろの文字列は無視される。数値に変換できない先頭（例 `true`）は 0 になる（`engine/src/kernels/cuda/fused_gr.cu:3902-3910`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| HIP ビルド | 常に無効 | なし | すべて（関数が直ちに 0 を返す） |
| CUDA、実行 GPU が sm_80 以上、Q8 down/up が渡される | 既定で mode 1 | `1`, `2`, `3`, `-1`, `2tail` | `0`, `true`, `0anything` |
| CUDA、実行 GPU が sm_80 未満、または device 属性取得失敗 | 無効 | なし | すべて（値にかかわらず 0） |

CUDA 行では、`atoi` 結果が 0 なら INT8 TC を無効にする。正数はそのまま mode として返し、1 は fast down + TC up、2 以上は TC down + TC up を選択する。負数は `env > 0` が偽なので mode 1（既定）になる。したがって `-1` は無効化ではない。mode 0 では `launch_q8_t` が次の `STRATA_HC_Q8_BF16TC` 判定へ進む（`engine/src/kernels/cuda/fused_gr.cu:3911-3922,3960-3988`）。

## 有効になる条件

- HIP ではなく CUDA のビルドであること。HIP 判定は即座に無効を返す（`engine/src/kernels/cuda/fused_gr.cu:3902-3905`）。
- 使用 GPU の compute capability major が 8 以上であること。CUDA device query に失敗した場合も無効になる。適合判定は device ごとに `ok[64]` へキャッシュされる（`engine/src/kernels/cuda/fused_gr.cu:3912-3922`）。
- `fused_gr_read_multi_slice` に `q8_down` と `q8_up` の両方が渡されること。そうでなければこの `launch_q8` 分岐には入らない（`engine/src/kernels/cuda/fused_gr.cu:4284-4291`）。通常の `generate` では `STRATA_HC_Q8` とモデルの GGUF 内重み形式がこの状態に関係する（`engine/src/program/generate.cpp:5164-5168`; `engine/src/core/native_dense.cpp:683-690`）。
- `LR`、`Q8_KC`、およびコンパイル時定数が INT8 TC カーネルの divisibility 条件を満たすこと。条件を満たさない場合は INT8 TC 分岐を通らず、BF16 TC 判定へ進む（`engine/src/kernels/cuda/fused_gr.cu:3962-3978`）。
- `STRATA_HC_Q8_TC` が未設定・空・0相当の場合も `STRATA_HC_Q8_BF16TC` が別に判定される。したがって本変数だけでは Tensor Core 全般を無効化しない。BF16 TC も選ばれない場合は通常の Q8 down/up 経路を使う（`engine/src/kernels/cuda/fused_gr.cu:3943-3955,3974-4052`）。

この変数に対応する CLI 引数による上書きは、対象ソースの参照では確認できない。環境値は `hc_q8_tc_mode()` の初回呼び出し時に読み取られて固定されるため、プロセス実行中に環境を変更しても反映されない。GPU 能力判定も device ごとに一度キャッシュする（`engine/src/kernels/cuda/fused_gr.cu:3906-3922`）。

## 実行時の詳細

`launch_q8_t<T>` はまず本変数の mode を取得する。mode が 1 以上かつタイル寸法条件を満たすと、mode 1 では `gr_down_q8_fast_kernel` と `gr_up_q8_tc_kernel`、mode 2 以上では `gr_down_q8_tc_kernel` と `gr_up_q8_tc_kernel` を起動して戻る。GPU の launch error は呼び出し側で `cudaGetLastError()` により検査され、失敗時は `fused_gr_read_multi q8: %s` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/fused_gr.cu:3962-3972,4284-4289`）。

INT8 TC 分岐を通らない場合は `STRATA_HC_Q8_BF16TC` が先に評価され、有効なら BF16 TC down/up 経路を起動する。さらにそれも選ばれないと、`STRATA_TSUM`、`STRATA_GR_Q8_PFS` などで選択される既存の Q8 経路へ進む（`engine/src/kernels/cuda/fused_gr.cu:3943-4052`）。本変数自体について成功時の有効化ログはない。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:3902-3924` — 環境値の変換、CUDA/HIP 差、GPU 能力確認とキャッシュ、既定 mode。
- `engine/src/kernels/cuda/fused_gr.cu:3253-3262` — sm_80 以上 CUDA 向け INT8 TC カーネルのビルド条件。
- `engine/src/kernels/cuda/fused_gr.cu:3943-3955` — BF16 TC の独立した設定と fallback。
- `engine/src/kernels/cuda/fused_gr.cu:3958-3988,3990-4052` — mode 別カーネル選択と後続経路。
- `engine/src/kernels/cuda/fused_gr.cu:4284-4291` — Q8 重みが渡されたときの呼び出しと失敗時の観測。
- `engine/src/program/generate.cpp:5164-5168`; `engine/src/core/native_dense.cpp:683-690` — CUDA generate が Q8_0 重みを検出して `STRATA_HC_Q8` を自動設定する経路。
