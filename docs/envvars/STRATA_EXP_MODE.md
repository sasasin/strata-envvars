# `STRATA_EXP_MODE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

grouped native experts が使う GPU カーネルレイアウトを選びます。主に AMD gfx906 向けのレイアウトと LDS（CUDA の shared memory に相当）を使う変種を選ぶ環境変数です。CUDA でも選択値は読み取られます。適用経路は `native_expert_grouped()` であり、VRAM 上の expert 計算や remote / peer expert の呼び出し元から使われます。ビルド済みの開発用 native-expert benchmark だけの設定ではありません。

## 値と判定

環境変数は `std::getenv()` で読み、値全体ではなく `std::atoi()` で整数化します。未設定は CUDA/HIP 実装では `-1`、SYCL の gfx906 実装では `7` です。空文字や数字で始まらない文字列は `atoi` により `0`、`12abc` は `12`、`-1` や `-2` は負数になります。変換エラーの検査や値域の clamp はありません。

| 指定値 | grouped expert の選択 |
|---|---|
| 未設定 | CUDA/HIP 実装では下記の GPU / backend 既定値。SYCL gfx906 実装では `7` |
| 負数 | CUDA/HIP 実装では下記の GPU / backend 既定値。SYCL gfx906 実装では負数のまま残り、通常 layout に進む |
| `0` | 通常の CUDA layout |
| `1`, `2`, `4` | 対応する AMD layout。`1` は 64 lane wavefront、`2` は 32 lane の論理 warp で2行を処理する R2、`4` は warp あたり4行を処理する変種。専用 kernel の形式外では通常 layout に戻る |
| `5`, `6`, `7` | 対応する量子化形式の gate/up に LDS variant。`6` は gfx906 にない byte-SIMD 操作を避ける符号処理、`7` は複数 token の活性を LDS に置き、weight load を共有する variant。down の LDS variant は `7` のみ |
| `8` | mode 7 の gate/up に SwiGLU と q8_1 量子化を融合する variant。対応形式で gate/up LDS を使う。down は mode 7 と同じ LDS variant |
| その他の非負値 | mode 1/2/4 や 5–8 の専用分岐に一致しない値は、通常 layout または backend fallback へ進む。5以上は専用 LDS kernel を使わない場合に CUDA では mode 0、gfx906 では mode 2 に fallback する |

CUDA/HIP の通常実装では環境変数由来の非負値が GPU 既定値より優先されます。native-expert benchmark が `native_expert_set_mode()` を呼ぶ場合、その非負の設定値がさらに優先しますが、この setter の呼び出しは benchmark ソース内です。実行時の `exp_mode()` が一度返した環境値は関数内 `static const` に保存され、プロセス内で環境を変更しても再読込されません。

## 有効になる条件

- CUDA/HIP ソースでは `STRATA_EXP_LAYOUTS` が有効なビルドに限ってこの選択分岐を使います。コード上は HIP gfx906 (`STRATA_HIP_GFX906`) または CUDA コンパイルで有効です。
- CUDA の既定は通常 `0`。sm_70 は `STRATA_SM70_TABLE` が設定され `atoi(value) != 0` の場合に `8`、Pascal GP100 / sm_60 は `STRATA_SM60_TABLE` が未設定または `atoi(value) != 0` の場合に `8` です。明示的な非負 `STRATA_EXP_MODE` はこれらの既定選択を上書きします。
- HIP gfx906 の既定は `7`。mode 1/2/4 の AMD layout は IQ 系の対象形式に限られ、mode 5–8 の LDS kernels も gate/up または down の対応形式に限られます。他形式では通常 layout または gfx906 の fallback mode 2 に進みます。
- CUDA の `native_expert_grouped()` で `grid_groups > 0 && grid_groups < cap_groups` の呼び出しは、環境変数や GPU 既定値を参照せず `mode 0` を選びます。その他の CUDA 呼び出しで `exp_mode()` が使われます。
- SYCL コピーでは `exp_mode()` の定義と利用は `STRATA_HIP_GFX906` の条件下にあります。該当ビルドでの未設定既定値は `7`。SYCL のこの経路は `STRATA_EXPERT_V2` / `STRATA_EXPERT_V2K` を無視すると診断メッセージを出す実装ですが、`STRATA_EXP_MODE` 自体について同様のメッセージはありません。

## 実行時の詳細

`native_expert_grouped()` が最初に必要とした時点で値を読みます。CUDA/HIP では一度 parse した値が `static` に保持されます。環境値が負数または未設定ならカード既定値を使い、CUDA はカードごとの既定 mode を device ごとの配列にも cache します。

CUDA/HIP gfx906 の grouped expert 呼び出しでは、mode 1/2/4 が選ばれ、かつ gate/up または down の形式が専用実装の対象なら対応する AMD kernel を launch します。mode 5–8 は対応する量子化形式の gate/up を LDS kernel に振り分け、mode 8 では対象形式の gate/up と SwiGLU・q8_1 量子化を一つの kernel に融合します。mode 7/8 の down LDS kernel は down type 20 または 42 に限られます。その他の型や専用分岐に一致しない mode は通常の `launch_gu` / `launch_down` 経路になります。CUDA では部分グループ呼び出しが mode 0 を固定するため、環境変数の値が常に全 expert 計算へ適用されるわけではありません。

この変数によるログ出力は実装にありません。カーネル launch の後に通常の `check()` がエラーを確認します。

## 文書との照合

`docs/AMD_HIP.md` は gfx906 grouped native experts の既定を mode 7 とし、`STRATA_EXP_MODE=2` を旧 AMD layout への切替として説明しています。ソースの gfx906 既定 `7` と合致します。`docs/NVIDIA_V100.md` は V100 の routed experts を mode 8 と説明し、`STRATA_EXP_MODE=0` で通常 CUDA layout に切り替えるとしています。コードでは sm_70 で mode 8 を有効にするには `STRATA_SM70_TABLE` が非ゼロである必要があり、`STRATA_EXP_MODE=0` はそれを上書きします。これらの文書・測定は記載された GPU と設定についての説明であり、他のカードでの性能を保証しません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:2816-2833` — ビルド条件、gfx906 / CUDA の既定値と fallback。
- `src/kernels/cuda/iq_kernels.cu:2996-3010,3199-3200,3249-3250,3317-3320` — LDS mode 5–8 の概要。
- `src/kernels/cuda/iq_kernels.cu:3406-3432` — `atoi`、未設定値、GPU 既定値、`STRATA_SM70_TABLE` / `STRATA_SM60_TABLE`、device ごとの cache。
- `src/kernels/cuda/iq_kernels.cu:3436-3443,3496-3503,3524-3559,3582-3615` — benchmark setter の override、部分グループ時の mode 0、実際の gate/up / down kernel 分岐。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5029-5033,5080-5128,5205-5228` — SYCL gfx906 の既定値と選択分岐。
- `src/core/remote_experts.cpp:318`, `src/core/peer_experts.cpp:240`, `src/core/verify.cpp:1582` — grouped native expert の runtime 呼び出し元。
- `docs/AMD_HIP.md:492-497`, `docs/NVIDIA_V100.md:38-45,85-91` — 文書にある gfx906 / V100 の mode 説明。
