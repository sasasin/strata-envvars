# `STRATA_PF_SWITCH_MIN_T`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt の token 数 `T` が指定値以上かを判定し、複数の opt-in prompt kernel・データ stride 切替を許可する下限です。この変数自身は機能を opt-in しません。たとえば `STRATA_PF_GEMM=1`、`STRATA_PA_FAST=1`、`STRATA_PF_HCDOWN=1`、`STRATA_HCD_EXACT=1`、`STRATA_HC_UPMIX=1`、または `STRATA_PF_PAD=1` と組み合わせて初めて各機能の候補になります。主な読み取り元は CUDA/HIP の `pf_switch_min_t()`、`Gemm::f16()` / `Gemm::native()`、QSA WMMA の `launch_wmma()` と、SYCL 側の同等コードです。`engine/src/prefill/prefill.cpp:975-979`、`engine/src/prefill/gemm.cu:1307-1315,1491-1505`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2346-2364`、`engine/sycl/src/prefill/prefill.cpp:372-376`、`engine/sycl/src/prefill/gemm.dp.cpp:952-960`、`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1946-1960`。

## 値と判定

各読み取り箇所は環境変数が未設定なら `0`、設定されていれば `std::atoll()` の戻り値を `int64_t` にします。空文字や数値に変換できない文字列は `0` になります。`atoll` は先頭の空白と符号を含む数値部分を変換し、数値の後ろに続く文字列は判定に使いません。したがって `4096tail` は `4096`、`0anything` や `junk` は `0`、`-1` は `-1` として扱われます。全体一致や値域検証、clamp はありません。各場所で `static const` に保存するため、その場所で初めて評価された後の環境変更は反映されません。

| 条件（build / 読み取り箇所） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---:|---|---|
| CUDA/HIP・SYCL prefill の HC padding / HC upmix / padded stride 判定 | `0` | `4096`、`4096tail`、`-1`（ただし各機能の追加条件も必要） | しきい値としては `4096` 未満の `2048`。`junk` / 空文字は `0` |
| HIP build の `Gemm::f16()` / `Gemm::native()` 内の PF GEMM 判定 | `0` | `4096` と `T >= 4096`（さらに `STRATA_PF_GEMM=1` 等が必要） | `T < 4096`。`STRATA_PF_GEMM` が無効なら本変数だけでは切り替わらない |
| HIP WMMA QSA prompt attention の fast 判定 | `0` | `4096` と `n_q >= 4096`（さらに `STRATA_PA_FAST=1` が必要） | `n_q < 4096`。`STRATA_PA_FAST` が無効なら切り替わらない |

比較は `T >= min_t` または `n_q >= min_t` です。負値は正の token 数より小さいため、この比較だけなら常に通ります。`0` も prompt の正の `T` / `n_q` に対しては常に通ります。prefill の一部は別途 `max(min_t, 64)` と比較し、CUDA の HC upmix はさらに `max(min_t, 33)` を使います。`atoll` の整数変換を使う実装であり、無効な文字列をエラーとして報告したり拒否したりするコードはありません。根拠: `engine/src/prefill/prefill.cpp:975-979,989-997,5102-5104,5129-5130,5195,5541`、`engine/src/prefill/gemm.cu:1310-1314,1495-1501`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2348-2364`。

## 有効になる条件

- HC の `xn16` padded stride は `STRATA_PF_HCDOWN=1` または `STRATA_HCD_EXACT=1` で `hc_pad()` が真であり、`T >= max(min_t, 64)`、unfused 経路でなく、低位成分を別保持していない場合に使われます。条件を満たさないと通常 stride の経路です。CUDA は同じ判定を使い、SYCL はその後に HC down/exact kernel または通常 projection へ進みます。`engine/src/prefill/prefill.cpp:1001-1016,5102-5124`、`engine/sycl/src/prefill/prefill.cpp:384-399,3439-3459`。
- HC upmix は `STRATA_HC_UPMIX` の値の先頭文字が `1` で、`T >= max(min_t, 33)`（CUDA）または `T >= min_t`（HIP）、unfused でなく、対応する weight が BF16-in-F32 で形状条件を満たし、Q8 scale や低位成分の非対応条件に当たらないときに試されます。`gr_upmix()` が使えない場合は通常 projection に戻ります。`engine/src/prefill/prefill.cpp:989-997,5127-5155`、`engine/sycl/src/prefill/prefill.cpp:370-379,3460-3463`。
- PF GEMM の FP16 projection 切替は `STRATA_PF_GEMM` の先頭文字が `1` で、HIP build の `Gemm::f16()` に渡された `T >= min_t`、かつ `strata_pf_gemm_f16()` が成功した場合です。失敗時は WMMA GEMM、hipBLASLt など後続の通常経路へ進みます。`engine/src/prefill/gemm.cu:1307-1328`、`engine/sycl/src/prefill/gemm.dp.cpp:952-985`。
- PF padded GEMM は `STRATA_PF_PAD=1` と `STRATA_PF_GEMM=1`、`T >= max(min_t, 64)` に加えて `N >= 512`、`K % 32 == 0`、scratch 容量、現在の device で padded product が利用可能であることを要します。GDN/QSA の `y` / `attn` stride にも `pf_pad()` と同じ token 下限が使われ、stride の必要な projection がその stride を消費します。条件外なら通常 stride / GEMM 経路です。`engine/src/prefill/prefill.cpp:1034-1051,5193-5213,5540-5544`、`engine/src/prefill/gemm.cu:1491-1507`。
- QSA attention の fast 分岐は `launch_wmma()` に到達した場合に限られ、`STRATA_PA_FAST` の先頭文字が `1` かつ `n_q >= min_t` で FP16 の単一画像側の kernel を選びます。未成立なら split 表現の通常 WMMA kernel です。HIP の QSA WMMA 呼び出し自体にも KV pool、shape、ID / page table などの適合条件があります。CUDA/HIP の呼び出し元は `engine/src/kernels/cuda/qsa_prompt_attn.cu:2456-2468,2471-2517`、SYCL/HIP 側は `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1946-1968,1973-2026`。
- この変数を読む箇所に CLI 引数や設定ファイルからの上書きはありません。`docs/SETTINGS.md` の OS / backend 一覧は候補情報として掲載されていますが、実際の適用は上記の build guard と実行時条件に限られます。

## 実行時の詳細

読み取りは process 起動時に一括されず、各関数の最初の評価時に関数ローカル static として cache されます。実装ごとに static は別々です（たとえば `pf_switch_min_t()`、GEMM の `pf_min_t`、QSA WMMA の `min_t`）。したがって、あるコード経路での初回評価後に環境を変更しても、その cache には反映されません。CUDA と SYCL の prefill は prompt chunk ごとに実際の `T` を比較します。HC padding / PF padded stride では既定下限 `64`、CUDA HC upmix では `33` が `STRATA_PF_SWITCH_MIN_T` の値より小さい場合の追加下限です。HIP GEMM と QSA WMMA fast にはこの変数による別の下限 clamp はなく、各々の `T` / `n_q` 比較を使います。`engine/src/prefill/prefill.cpp:975-979,5102-5104,5129-5130,5195,5541`、`engine/src/prefill/gemm.cu:1310-1314,1495-1501`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2348-2364`。

この変数自体によるログ出力、警告、終了処理はありません。機能の実行失敗は各機能の既存経路に従います。例として `STRATA_PF_HCDOWN` の projection 実行失敗は prefill を `false` で返し、QSA WMMA の launch error はエラー文字列を stderr に出して FP32 prompt attention 側へ fallback します。`engine/src/prefill/prefill.cpp:5114-5124`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2366-2371`。

## ログと測定値

この変数を有効化したことを示す専用ログはありません。`docs/AMD_HIP.md` は `STRATA_PF_GEMM=1 STRATA_PF_SWITCH_MIN_T=4096` と他設定を組み合わせた報告として 925 → 1,092 tok/s を記載していますが、これは同資料にある特定 reporter の結果で、変数単独の効果ではありません。ソースコードから一般的な性能差は導けません。`docs/AMD_HIP.md:801`。

## 根拠

- 直接の全読み取り: `engine/src/prefill/prefill.cpp:975-978`、`engine/src/prefill/gemm.cu:1311,1497`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2349`、`engine/sycl/src/prefill/prefill.cpp:372-375`、`engine/sycl/src/prefill/gemm.dp.cpp:956`、`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1952`。
- `rg -n --hidden --glob '!.git/**' 'STRATA_PF_SWITCH_MIN_T' .` で全参照を確認。残りはコメント、資料、計測記録、設定レジストリで、環境からの読み取りではありません。動的な env helper 経由の読み取りは見つかりませんでした。
