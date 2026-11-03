# `STRATA_DF2_GEMM4`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata checkout は `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外です。

## 役割

DFlash2 drafter が Q4_0 重みの GEMM を実行するときに、行の分割方法などが異なる GEMM kernel variant を選びます。CUDA/HIP では既定の自動選択または従来型の kernel を選べ、10 以上を指定すると該当 variant ID を選びます。SYCL では既定 variant を使うか、対応する variant ID を直接選びます。Q8 重みの CUDA/HIP GEMM にはこの変数は使われません。`src/kernels/cuda/dflash2.cu:1031-1034,1079-1086`、`sycl/src/kernels/cuda/dflash2.dp.cpp:702-718`。

## 値と判定

両実装とも `std::getenv()` の結果を `std::atoi()` に渡し、未設定なら整数 `0` にします。文字列全体の妥当性検査はありません。`atoi` のため、先頭の空白と符号の後の数値部分が変換され、数値の後ろに文字があっても数値部分が使われます。空文字や数値として読めない文字列は `0` になります。したがって、たとえば `12junk` は `12`、`junk` は `0` として扱われます。`src/kernels/cuda/dflash2.cu:1032`、`sycl/src/kernels/cuda/dflash2.dp.cpp:716`。

| ビルド | unset / 0 | 非ゼロの指定値 |
|---|---|---|
| CUDA/HIP | 自動選択（`DF2_Q4_AUTO(rows)`） | 1〜9 および負値はすべて variant 1 相当。10 以上は整数値を variant ID として使う。実装にない ID は switch の既定経路へ進む。 |
| SYCL | 自動選択（既定 macro は rows が 1024 以下なら 40、超えるなら 41） | 整数値を variant ID として使う。対応 ID は 10, 11, 12, 17, 24, 25, 28, 34, 40, 41, 42, 43。それ以外は variant 28 の kernel を使う。 |

CUDA/HIP の環境値が 0 以外で 10 未満なら `v4=1` になりますが、switch に `case 1` はありません。そのためこの経路では switch の `default` が実行され、rows が 32 の倍数なら `gemm4_kernel<4>`、そうでなければ `gemm4_kernel<2>` を起動します（従来型）。10〜45 はそれぞれ `gemm4_rows_kernel<W,R,U>` の variant に対応します。10〜45 の範囲外の値も同じ switch の既定経路に落ちます。`src/kernels/cuda/dflash2.cu:1032-1078`。

SYCL は switch に列挙した variant ID だけを専用 kernel に対応させています。未対応値は `gemm4_nc<1,1,2>`、すなわち variant 28 相当の kernel に進みます。環境値 0 の自動選択は `DF2_Q4_AUTO(rows)` で、ソース既定では rows が 1024 以下なら 40、それ以外は 41 です。`src/kernels/cuda/dflash2.dp.cpp:698-700,716-732`。

CUDA/HIP の環境値 0 の自動選択は、ソース既定で HIP の gfx12 なら rows 640 以下で 31、超える場合は 26、それ以外の CUDA/HIP GPU では 17 です。`DF2_Q4_AUTO` が外部のコンパイル定義で上書きされていない場合の規則です。`src/kernels/cuda/dflash2.cu:998-1016`。

## 有効になる条件

- CUDA/HIP の DFlash2 kernel は CUDA または HIP build の `strata_kernels` に含まれます。SYCL build は別の `sycl/src/kernels/cuda/dflash2.dp.cpp` を含みます。Metal build には DFlash2 kernel がありません。`CMakeLists.txt:431-436,485-525`、`sycl/CMakeLists.txt:245-259`。
- 変数を読む GEMM 分岐は Q4_0 重みの場合だけです。CUDA/HIP では `mats[0].q4` が true の分岐内で読みます。SYCL は Q4_0 専用で、非 Q4 入力は `df2_gemm` の検査で例外になります。`src/kernels/cuda/dflash2.cu:1017-1033`、`sycl/src/kernels/cuda/dflash2.dp.cpp:702-717`。
- GEMM は 1〜3 個の行列、`n_in` が 512 の倍数、`ncols` が 1〜8、各行列の `n_out` が 16 の倍数である形状を受け付けます。CUDA/HIP では同一呼び出し内で量子化形式を揃える必要があります。これらを満たさない形状は環境変数の値によらず `std::invalid_argument` になります。`src/kernels/cuda/dflash2.cu:1017-1025`、`sycl/src/kernels/cuda/dflash2.dp.cpp:702-710`。
- 通常のアプリ経路では DFlash2 drafter の GEMM 呼び出し時に使われます。DFlash2 自体は `--draft dflash2` と draft model pack などを要する機能です。ベンチ用の `df2_gemm_variant(v)` が非 0 の値を設定している場合は、環境変数よりその明示値が優先されます。`src/core/dflash2.cpp:404-415`、`sycl/src/core/dflash2.cpp:319-330`、`src/kernels/cuda/dflash2.cu:21,995,1032-1034`、`sycl/src/kernels/cuda/dflash2.dp.cpp:37,716-718`、`src/program/generate.cpp:1157-1165`。

## 実行時の詳細

環境変数は GEMM 関数内の関数ローカル `static const int` に保存されます。CUDA/HIP では Q4 GEMM 分岐に初めて入った時、SYCL では `df2_gemm` の初回呼び出し時に読み取ります。以後プロセス内で環境を変更しても再評価されません。CUDA/HIP で先に Q8 GEMM を呼んでも、この変数の読み取りは起きません。`src/kernels/cuda/dflash2.cu:1031-1033`、`sycl/src/kernels/cuda/dflash2.dp.cpp:716-718`。

値は GEMM の kernel 選択だけに使われ、変数値や選択 variant を出力する専用ログ、無効値の警告、値の clamp はありません。形状検査に失敗すれば `df2_gemm: unsupported shape` などの例外になります。CUDA 実装では kernel 起動直後の `check("gemm4")` が launch error を検出すると、`dflash2 kernel gemm4: <CUDA error>` を stderr に出して `std::runtime_error` を投げます。環境変数の値自体がそのエラーを発生させるかどうかは、GPU 上で実行しない調査では確認していません。`src/kernels/cuda/dflash2.cu:24-29,1017-1025,1077`、`sycl/src/kernels/cuda/dflash2.dp.cpp:702-710`。

## 根拠

- 候補名の Strata ソース全体検索では、値の読み取りは `src/kernels/cuda/dflash2.cu:1032` と `sycl/src/kernels/cuda/dflash2.dp.cpp:716` の 2 箇所です。どちらも直接 `getenv` / `atoi` を使い、環境名を渡す helper はありません。
- CUDA/HIP の選択と起動: `src/kernels/cuda/dflash2.cu:998-1016,1017-1078`。
- SYCL の選択と起動: `sycl/src/kernels/cuda/dflash2.dp.cpp:698-732`。
- DFlash2 実行経路から GEMM への呼び出し: `src/core/dflash2.cpp:404-415`、`sycl/src/core/dflash2.cpp:319-330`。
- build 条件: `CMakeLists.txt:431-436,485-525`、`sycl/CMakeLists.txt:245-259`。
