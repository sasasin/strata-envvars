# `STRATA_SM75_PERF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA engine の Turing（実効 compute capability 7.5）向けに、同じ結果になるとされる複数の代替カーネルを既定で選ぶための opt-in です。`sm75_series()` が値を読み、`sm75_default()` が値と対象 GPU の世代を組み合わせます。環境変数だけで全カーネルを無条件に強制するものではなく、個別スイッチ、データ形状、モデル状態などがさらに選択を制限します。`STRATA_EMULATE_CC=75` で実効 compute capability が 7.5 になっている場合も対象です。[`sm75_series.hpp:24-37`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)、[`emulate.hpp:58-75`](../../../../Niko1221/Strata/engine/include/strata/core/emulate.hpp)

主な適用先は fused GR の up/down、QSA attention・score・top-k、Q2_0 MMVQ、IQ expert layout、Q8_1 interleaved quantize、BF16 dequant の各 CUDA 経路です。各経路では Turing 用カーネルやレイアウトの既定選択を変えます。たとえば Q2_0 MMVQ は列数が 1〜4（複数列では exact layout のとき）に限って warp-row kernel を選び、QSA top-k は decode/prefill 状態と reach/capacity などの条件に合うときだけ split/sample 経路を使います。[`native_mmvq.cu:3428-3445`](../../../../Niko1221/Strata/engine/src/kernels/cuda/native_mmvq.cu)、[`qsa_select.cu:3032-3040,3082-3098`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)、[`verify.cpp:1832-1846`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

`docs/DETAILS.md` はこれらを bitwise-equivalent な Turing kernels と記述し、SM 7.5 実機での確認がないため既定では無効としていると説明しています。回答を変える数値経路はこのスイッチの対象外として別の opt-in に分けられています。[`DETAILS.md:1336-1346`](../../../../Niko1221/Strata/docs/DETAILS.md)

## 値と判定

`sm75_series()` は `std::getenv("STRATA_SM75_PERF")` を呼び、値が存在し、かつ `std::atoi(value) != 0` の場合だけ true にします。文字列全体の検証やエラー報告はありません。`atoi` は先頭の空白と符号を許容し、先頭の10進整数部分を変換するため、数値部分の後ろは判定されません。[`sm75_series.hpp:25-30`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `atoi(value) != 0` | 無効 | `1`, `2`, `-1`, `01`, `1tail`, ` 1` | 空文字, `0`, `0anything`, `true`, `false`, `nonnumeric` |

値の数値範囲を別途検証・clamp する処理はありません。既定値は unset 相当の false です。CLI 引数・設定ファイルによるこの値の上書きは見つかりません。なお、各カーネルには個別スイッチがあり、それが明示されるとシリーズ既定値を上書きするものがあります（次節）。[`sm75_series.hpp:25-30,36-43`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)

## 有効になる条件

- 対象は Strata の CUDA engine 経路です。調査した読み取りは `engine/include/strata/core/sm75_series.hpp` の helper に集約され、HIP の fused GR / verify 経路は明示的に false を返すか CUDA 用分岐から外れます。[`fused_gr.cu:1560-1565`](../../../../Niko1221/Strata/engine/src/kernels/cuda/fused_gr.cu)、[`verify.cpp:473-489,1835-1845`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- GPU の実効 compute capability が 7.5 であることが `sm75_default()` の条件です。`STRATA_EMULATE_CC=75` は実効値を 75 にし、CUDA 13 Volta compatibility proxy による 7.5→7.0 の remap も判定に反映されます。[`sm75_series.hpp:33-37`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)、[`emulate.hpp:58-75`](../../../../Niko1221/Strata/engine/include/strata/core/emulate.hpp)
- 対応カーネルがその実行経路で呼ばれ、対象の形状・量子化・モデル状態を満たす必要があります。例として GR up は `LR == 320` かつ token 数 3 以上、QSA decode attention v3 は `kv_mode == 1`、Q2_0 warp-row は `ncols <= 4` かつ複数列時に `g_multi_exact` を要求します。[`fused_gr.cu:1560-1562,1911-1919`](../../../../Niko1221/Strata/engine/src/kernels/cuda/fused_gr.cu)、[`qsa_decode_attn.cu:1093-1100,1331-1337`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_decode_attn.cu)、[`native_mmvq.cu:3428-3445`](../../../../Niko1221/Strata/engine/src/kernels/cuda/native_mmvq.cu)
- 個別スイッチはシリーズ既定を上書きします。`STRATA_SM75_IL`、`STRATA_SM75_EXP`、`STRATA_TC_SM75` は unset ならシリーズ値を使い、set なら `atoi(value) != 0` で on/off を決めます。これらは SM 7.5 以外では helper が先に false を返します。[`sm75_series.hpp:39-44`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)、[`tc_sm75.hpp:19-23`](../../../../Niko1221/Strata/engine/include/strata/core/tc_sm75.hpp)、[`native_mmvq.cu:4191-4214`](../../../../Niko1221/Strata/engine/src/kernels/cuda/native_mmvq.cu)、[`iq_kernels.cu:6795-6802`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `STRATA_GR_UP75` / `STRATA_GR_DOWN_TG`、`STRATA_SCORES_HALVE`、`STRATA_TOPK_SPLIT` / `STRATA_TOPK_SAMPLE`、`STRATA_ATTN_V3`、`STRATA_Q2_WARP`、`STRATA_FUSE_WAIT`、`STRATA_QIL`、`STRATA_PA_V1_PREFETCH`、`STRATA_SCORES_THREAD` も個別制御です。unset の場合にシリーズ既定を使う経路がありますが、明示値は各スイッチの規則に従います。すべてが SM 7.5 限定ではなく、たとえば `STRATA_SCORES_THREAD=1` は任意の CUDA card で有効にできるとコード資料に記載されています。[`DETAILS.md:1340-1346`](../../../../Niko1221/Strata/docs/DETAILS.md)、[`qsa_select.cu:2152-2176`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)、[`fused_gr.cu:1558-1608`](../../../../Niko1221/Strata/engine/src/kernels/cuda/fused_gr.cu)
- `STRATA_SELECT_SIMT`、`STRATA_PA_V2T`、`STRATA_PF_FUSED` と `STRATA_PF_FUSED_SM75`、`STRATA_PF_FUSED_Q2N`、`STRATA_BF16_TC` と `STRATA_XN_F16` は回答を変える別 opt-in であり、この変数だけでは有効になりません。[`DETAILS.md:1344-1346`](../../../../Niko1221/Strata/docs/DETAILS.md)

## 実行時の詳細

環境値は `sm75_series()` が最初に呼ばれた時点で関数内 `static const bool` に保存され、以後の呼び出しでは再読込しません。したがって、プロセス起動後に環境値を変更してもこのプロセスのシリーズ判定には反映されません。GPU ごとの適用可否も複数の呼び出し側で device ordinal ごとに cache されます。個別スイッチの読み取り時期は各スイッチの実装に依存します。[`sm75_series.hpp:24-37`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)、[`qsa_decode_attn.cu:475-488`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_decode_attn.cu)、[`verify.cpp:477-487`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

シリーズ判定はカーネル選択条件として使われます。たとえば GR up は専用スイッチが unset の場合にシリーズ判定を参照し、条件成立時に `gr_up75_kernel` 群へ分岐します。QSA top-k の split kernel は対象 GPU 判定に加えて old-kernel 無効、decode 状態、minimum `max_blocks`、capacity と selection-width の条件が必要です。[`fused_gr.cu:1560-1578,1911-1920`](../../../../Niko1221/Strata/engine/src/kernels/cuda/fused_gr.cu)、[`qsa_select.cu:2761-2774,3032-3040`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)

CLI やサーバーの起動引数からこの値を読み直す処理、子プロセス向けに値を加工・転送する処理は、候補名の全参照検索では確認できません。Strata が値を読んだ箇所に、この変数専用のログ、警告、終了処理はありません。別のカーネル起動失敗処理はありますが、この環境変数の無効値をエラーにするものではありません。[`sm75_series.hpp:24-44`](../../../../Niko1221/Strata/engine/include/strata/core/sm75_series.hpp)

## ログと測定値

この変数自体について値の採用・無効値・fallback を表示するログはありません。`docs/DETAILS.md` は Turing 向け kernels が置換前と bitwise equal であると説明し、SM 7.5 実機で未確認のため opt-in としています。新しい性能測定は行っていません。[`DETAILS.md:1336-1346`](../../../../Niko1221/Strata/docs/DETAILS.md)

## 根拠

- 読み取り・変換・cache・GPU 判定: `engine/include/strata/core/sm75_series.hpp:24-44`
- 実効 compute capability と emulation: `engine/include/strata/core/emulate.hpp:58-75`
- fused GR: `engine/src/kernels/cuda/fused_gr.cu:1558-1608,1839-1847,1911-1920`
- QSA attention と selection: `engine/src/kernels/cuda/qsa_decode_attn.cu:475-488,1093-1100,1331-1337`; `engine/src/kernels/cuda/qsa_select.cu:2152-2192,2202-2214,2261-2271,2761-2774,2997-3013,3032-3040,3082-3098`
- MMVQ / expert layout / BF16 dequant: `engine/src/kernels/cuda/native_mmvq.cu:3403-3416,3428-3445,4191-4214`; `engine/src/kernels/cuda/iq_kernels.cu:6795-6816`; `engine/include/strata/core/tc_sm75.hpp:19-23`; `engine/src/kernels/cuda/dequant_bf16.cu:441-452`
- verify quantization: `engine/src/core/verify.cpp:472-489,1832-1846`
- 設計資料との照合: `docs/DETAILS.md:1336-1346`
