# `STRATA_Q6P_GRID`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Q6_K の packed MMVQ カーネルで起動する CUDA grid / SYCL work-group 数の上限を指定する。実際の個数は `min(n_out, q6p_grid())` であり、カーネルは各 group が `row_step` 間隔で行を処理する。通常の GGUF 配置の Q6_K kernel や、Q6_K 以外の処理はこの値では変わらない。読み取り実装は CUDA/HIP 側の `engine/src/kernels/cuda/native_mmvq.cu` と SYCL 側の `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` にある（それぞれ `2845-2853`, `2709-2717`, `2933-2941`, `2830-2873`）。

この変数が使われるのは packed Q6_K 行列が MMVQ に登録され、packed kernel が選ばれた場合に限る。登録のためには別変数 `STRATA_Q6_PACKED` が厳密に文字列 `1` である必要がある。Q6_K の出力 head（GGML type 14）および MTP draft head がこの設定で packed される経路がある（`engine/src/kernels/cuda/native_mmvq.cu:3145-3150`, `engine/src/core/native_head.cpp:261-264`, `engine/src/core/mtp.cpp:988-995`; SYCL は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`, `engine/sycl/src/core/native_head.cpp:92-96`, `engine/sycl/src/core/mtp.cpp:865-872`）。

## 値と判定

CUDA/HIP と SYCL の両実装とも `std::getenv` の結果を `std::atoi` に渡し、変換結果が `> 0` の場合だけ採用する。未設定、空文字、変換できない文字列、0、負値はすべて既定値 `640` になる。文字列全体の妥当性検査はなく、`atoi` が読める先頭の数値部分だけが使われるため、たとえば `12abc` は `12`、`0anything` は既定値、` 12` は `12` と判定される。`+2` は `2`、`-2` は既定値となる。大文字小文字の概念はない。整数範囲を超える文字列の扱いは `atoi` に委ねられ、Strata 側での範囲検査はない（`engine/src/kernels/cuda/native_mmvq.cu:2845-2852`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2709-2716`）。

| 条件 | 未設定 | 正の整数に変換される設定値 | 既定値に戻る設定値 |
|---|---:|---|---|
| CUDA/HIP または SYCL の packed Q6_K kernel | `640` | `1`, `640`, `12abc`, ` 12` → それぞれ変換された正整数 | 空文字、`0`, `0anything`, `-2`, `abc` → `640` |

この値を使った grid はさらに `n_out` 以下に制限される。したがって指定値が `n_out` より大きくても起動数は `n_out` で止まる（`engine/src/kernels/cuda/native_mmvq.cu:2933-2941`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2830-2873`）。

## 有効になる条件

- Strata が CUDA/HIP または SYCL の native Q6_K MMVQ 実装を使うこと。
- `STRATA_Q6_PACKED` が厳密に `1` であり、Q6_K の対象 head が packed 行列として登録されること。未設定や `1` 以外では、この変数を読む `q6p_grid()` を通る packed launch に到達しない（CUDA/HIP: `engine/src/kernels/cuda/native_mmvq.cu:3145-3150`, `engine/src/core/native_head.cpp:261-264`; SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`, `engine/sycl/src/core/native_head.cpp:92-96`）。
- packed 化関数は `n_in > 0`、`n_in` が 256 の倍数、`n_in / 256 >= WARPS * WARP / 32`、`n_out >= 2048` などの形状条件を満たす必要がある。満たさない場合は packed 登録されず、この grid は使用されない（CUDA/HIP: `engine/src/kernels/cuda/native_mmvq.cu:3153-3155`; SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3191-3195`）。
- 登録済み weights と shape が一致し、packed registry が空でなく、self-test の bypass 中でなく、複数列の場合は `g_multi_exact` が有効であること。条件を満たさない `q6_packed_mmvq` は `false` を返し、通常の Q6_K 経路へ進む（CUDA/HIP: `engine/src/kernels/cuda/native_mmvq.cu:2944-2949`, `engine/src/kernels/cuda/native_mmvq.cu:3600-3614`; SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3938`）。
- この変数を読むコードに CLI 引数・設定ファイルによる上書きはない。

## 実行時の詳細

`q6p_grid()` は関数内 `static const int` の初期化 lambda で環境を読み、結果をプロセス内にキャッシュする。値を読むのは packed launch が初めて `q6p_grid()` を呼んだ時であり、head のロード時点ではない。初回評価後に環境を変更しても反映されない。CUDA/HIP と SYCL の各実装に独立した static cache がある（`engine/src/kernels/cuda/native_mmvq.cu:2845-2853`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2709-2717`）。

通常はキャッシュされた値と `n_out` の小さい方を grid / work-group 数にし、それを `row_step` として packed Q6_K kernel に渡す。各 group は担当する row から `row_step` ずつ進んで残りの行を処理するため、設定値が出力行数を超えない限り行を省略しない（CUDA/HIP: `engine/src/kernels/cuda/native_mmvq.cu:2871-2872`, `2933-2941`; SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2746-2748`, `2830-2873`）。

例外として `STRATA_Q6P_SELFTEST` の値が先頭文字 `1` または `2` の場合、packed 化時に自己検査・計測が走る。`2` で始まる値では grid sweep 中に `g_q6p_grid_override` が 160, 320, 640, 1280, 2560, 5120, 20480 に順次設定され、`q6p_grid()` は正の override を環境変数の cache より優先する。sweep 後は override を 0 に戻す。この一時 override は通常の `STRATA_Q6P_GRID` 値を変えず、self-test 以外には作用しない（CUDA/HIP: `engine/src/kernels/cuda/native_mmvq.cu:3184-3186`, `3236-3255`; SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3253-3255`, `3323-3349`）。

## ログと測定値

`STRATA_Q6P_GRID` 単独の値や採用 grid を通常実行で表示するログは見当たらない。packed head の登録時には `strata: STRATA_Q6_PACKED=1 packed the ...` が stderr に出る。`STRATA_Q6P_SELFTEST=2` の grid sweep では各候補について `strata: Q6_K packed grid sweep ... grid %d ncols %d: ...` を stderr に出すが、これは自己検査コード内の計測ログであり、通常実行時の性能値ではない（CUDA/HIP: `engine/src/kernels/cuda/native_mmvq.cu:3182-3183`, `3250-3251`; SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3251-3252`, `3345-3346`）。

## 根拠

- 全直接参照と値変換: `engine/src/kernels/cuda/native_mmvq.cu:2845-2853`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2709-2717`。
- packed launch の grid clamp と kernel への row step 受け渡し: `engine/src/kernels/cuda/native_mmvq.cu:2871-2872`, `2933-2941`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2746-2748`, `2830-2873`。
- packed 化条件、登録、Q6_K dispatch fallback: `engine/src/kernels/cuda/native_mmvq.cu:2944-2949`, `3145-3155`, `3600-3614`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`, `3191-3195`, `3935-3938`。
- 出力 head / MTP draft head からの登録: `engine/src/core/native_head.cpp:261-264`, `engine/src/core/mtp.cpp:988-995`; `engine/sycl/src/core/native_head.cpp:92-96`, `engine/sycl/src/core/mtp.cpp:865-872`。
- self-test grid override と観測ログ: `engine/src/kernels/cuda/native_mmvq.cu:3236-3255`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3323-3349`。
