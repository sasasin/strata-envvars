# `STRATA_PF_FUSED_Q6K`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Q6_K 量子化の MoE gate/up と Q8_0 down の組を、Strata の fused prompt expert kernel で処理する opt-in スイッチ。対象はこの量子化ペアであり、Q6_K down や他の down 形式まで対象を広げるものではない。CUDA では `native_kernel<T_Q6_K, true>` と Q8_0 down kernel、HIP では gfx12 の `native_w11_kernel<T_Q6_K, true>` へ到達する。設定は生成処理やモデル全体の量子化を変えない。`native_supported()` がこのペアを fused 対象と判定しない場合、上位の prefill planner がその層を別経路へ振り分ける。

CUDA と HIP の両方で値を読む箇所があるが、利用できる GPU 条件は異なる。通常の CUDA/HIP ビルドでは未設定は opt-in なし。例外として、MMQ なしのビルドでは prompt 経路の起動初期化が未設定時に `1` を設定し、Qwen3.6 エンジンは両方のエントリで未設定時に `1` を設定する。いずれの初期化も既に設定された値を上書きしない。`engine/src/prefill/prefill.cpp:223-255`、`engine/src/qwen35/q36_engine.cu:5431-5454`、`engine/include/strata/prefill/own_only_switches.hpp:18-25,48-56,75-82`

## 値と判定

CUDA と HIP の読み取り関数はいずれも `getenv()` の結果が null でなく、先頭バイトが文字 `'1'` の場合だけ true とし、その結果を関数内 `static const bool` に保存する。文字列全体や数値としての妥当性は検査しない。したがって `1`、`10`、`1anything` は true、`0`、`true`、` 1`、空文字は false。大文字小文字の変換、空白除去、数値変換、境界値処理はない。CUDA は `q6k_cuda_requested()`、HIP は `q6k_hip_requested()` で読み取る。`engine/src/prefill/moe_fused_iq.cu:2733-2737,3196-3202`

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の CUDA/HIP prefill | 無効 | `1`, `1anything` | 空文字、`0`, `true`, ` 1` |
| `STRATA_PF_OWN_ONLY` の prompt build | 起動時に `1` を補う | 既存値は維持し、先頭が `1` なら有効 | 空文字を含む既存値で先頭が `1` でなければ無効 |
| Qwen3.6 エンジン（`strata --model` 経由と standalone `strata-q36`） | `run` の初期化で `1` を補う | 既存値は維持し、先頭が `1` なら有効 | 空文字を含む既存値で先頭が `1` でなければ無効 |

2 種類の起動時既定値設定は `setenv(..., "1", 0)` 相当であり、環境変数が空文字でも既設定とみなして維持する。Qwen3.6 は `q36_entry_switches()` にこの名前を含め、MMQ の有無にかかわらず unset のときに既定値を入れる。`engine/include/strata/prefill/own_only_switches.hpp:18-25,48-56,75-82`、`engine/src/qwen35/q36_engine.cu:5431-5439`

## 有効になる条件

- **共通:** Q6_K gate/up と Q8_0 down のペアであること。CUDA 側の `native_supported()` はこの組だけを受け付ける。HIP 側も `gu_type == T_Q6_K` のとき down が Q8_0 の場合だけ受け付ける。`engine/src/prefill/moe_fused_iq.cu:3448-3452,3550-3554`
- **共通:** 上位スイッチ `STRATA_PF_FUSED` が無効でなく、`STRATA_PF_FUSED_NATIVE=0` による native fused kernel 全体の抑止もないこと。`native_supported()` は `STRATA_PF_FUSED=0` 相当を先に拒否し、続いて `STRATA_PF_FUSED_NATIVE` を確認する。prompt path の small-card override が 0 の場合も拒否する。`engine/src/prefill/moe_fused_iq.cu:3415-3432`
- **CUDA:** 通常は sm_80 以上であること。sm_75 は `STRATA_PF_FUSED_SM75=1` による Turing setup に入り、さらに Q6_K/Q8_0 用 kernel setup が成功する場合に対象となる。各必要 kernel の setup が両方成功し、device が fused kernel 対応 (`d.ok`) と判定されること。`engine/src/prefill/moe_fused_iq.cu:2899-2905,2913-2936,2984-2990,3448-3452`
- **HIP:** gfx12 として認識され、HIP の `dev_info()` が WMMA kernel を利用可能と判定すること。gfx11 ではこの Q6_K pair の条件を満たさず、環境変数によって fused Q6_K path には入らない。`engine/src/prefill/moe_fused_iq.cu:2858-2885,3061-3077,3550-3554`
- **共通:** `STRATA_PF_FUSED_NT=256` の setup が有効 (`occ_nt > 0`)、または `STRATA_PF_FUSED_WS` の warp-specialized setup が有効 (`ws`) の場合、この Q6_K pair は `native_supported()` が false を返す。`engine/src/prefill/moe_fused_iq.cu:3448-3452`
- **モデル状態:** GGUF の expert gate/up/down 型がそれぞれ Q6_K/Q8_0 である必要がある。たとえば `docs/UNSLOTH_Q6.md:37-41` は UD-Q6_K_XL の 48 層中 47 層が Q6_K/Q8_0、残る 1 層が Q8_0/Q8_0 と記載する。この記述はモデル形式の説明であり、全 Q6_K モデルへの対応を意味しない。

## 実行時の詳細

読み取り関数は最初の呼び出し時に一度値を評価し、`static const bool` に保持する。プロセス中の環境変更を再読込しない。CUDA では最初の `dev_info()` 呼び出しで device ごとの setup 結果も `g_dev[]` に保存し、`d.done` 後は再 setup しない。HIP でも device ごとの `d.ok` と gfx12 判定を保存する。通常の起動では起動時点の値を利用し、Qwen3.6 はモデルロード前に未設定スイッチを補う。`engine/src/prefill/moe_fused_iq.cu:2735-2737,2847-2853,3199-3202`、`engine/src/qwen35/q36_engine.cu:5431-5454`

CUDA は Q6_K gate/up と Q8_0 down の kernel setup を両方試し、両方成功した場合だけ `d.q6k` を true にする。sm_80+ では `setup_one`、Turing の sm_75 経路では 128-row の `setup_ww` を使う。HIP は gfx12 で同じ環境値を pair eligibility に使い、Q6_K gate/up を `native_w11_kernel` に dispatch する。`native_supported()` が true の場合、`experts_native()` は Q6_K gate/up kernel と Q8_0 down kernel を launch し、launch 後 `cudaGetLastError()` を確認する。`engine/src/prefill/moe_fused_iq.cu:2913-2936,2984-2990,3448-3452,3822-3823,3915-3918`

CLI 引数にこの環境変数と同じ指定はなく、対象値を CLI が上書きする処理もない。既存の環境値が優先される。Qwen3.6 エンジンは未設定の場合のみ値を設定する。MMQ ありの通常経路で pair が非対応なら planner が MMQ または FP16 経路を選び、MMQ なしの build では Strata の own-only prompt path が利用できる経路へ振り分ける。`docs/QWEN36.md:7-9` は Qwen3.6 専用エンジンへの切り替えを記載する。`engine/src/prefill/prefill.cpp:223-255,392-405`

## ログと測定値

スイッチが有効になったことを示す専用の成功ログは確認できない。CUDA の kernel setup が不成立の場合、`d.q6k` が立たず `native_supported()` が false になるため、Q6_K/Q8_0 ペアは fused launch に進まない。該当 setup 箇所には理由ログがない。実際に launch 後の CUDA error check が失敗した場合は stderr に `prefill fused experts (native): experts_native: <CUDA error text>` を出して終了コード 1 で終了する。`engine/src/prefill/moe_fused_iq.cu:68-72,2984-2990,3448-3452,3852-3853`

この環境変数による性能値や出力一致の測定値は本書では扱わない。`docs/UNSLOTH_Q6.md` は GGUF の型配置を説明するが、このスイッチの A/B 測定条件や測定値は記載していない。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:2733-2737` — CUDA の値判定
- `engine/src/prefill/moe_fused_iq.cu:3196-3202` — HIP の値判定
- `engine/src/prefill/moe_fused_iq.cu:2913-2936,2984-2990` — CUDA kernel setup と device cache
- `engine/src/prefill/moe_fused_iq.cu:3448-3452,3550-3554` — CUDA/HIP の pair 条件
- `engine/src/prefill/moe_fused_iq.cu:3822-3823,3915-3918` — Q6_K gate/up dispatch
- `engine/src/prefill/prefill.cpp:223-255` — MMQ なし build の起動時既定値
- `engine/src/qwen35/q36_engine.cu:5431-5454` — Qwen3.6 エンジンの起動時既定値
- `docs/UNSLOTH_Q6.md:37-41`, `docs/QWEN36.md:7-9` — モデル形式と専用 engine の説明
