# `STRATA_IQ3S_WIDE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の IQ3_S 行列ベクトル／複数ベクトル積で、既定の multi kernel の代わりに wide kernel を選びます。IQ3_S の dense 行列のうち、`iq_mmvq()` を通る処理に適用されます。ソース中の説明と `docs/INTEL.md` では opt-in とされています。

## 値と判定

`iq3s_wide_on()` は `std::getenv()` の結果を `std::atoi()` に渡し、戻り値が 0 でなければ有効とします。文字列全体の妥当性検査はありません。未設定と空文字は無効です。先頭の空白や符号の後に数字があればその整数部分で判定され、数字で始まらない文字列は 0 として無効になります（例: `1junk` と `-1` は有効、`true` と `0x1` は無効）。

判定結果は関数内の `static const bool` に保存されます。初回の IQ3_S `iq_mmvq()` 呼び出しで評価され、その後プロセス内で環境変数を変更しても再評価されません。

## 有効になる条件

環境変数の判定が有効でも、wide kernel の起動には追加条件があります。

- 量子化型が IQ3_S（type `21`）であること。
- 入力幅 `n_in` が `QK_K` の倍数であること。
- ベクトル列数 `ncols` が 1〜8 であること。

幅または列数が条件外なら wide kernel は起動せず、`iq_mmvq()` は通常の `launch_mmvq()` に進みます。SYCL 以外の backend の実装にはこの環境変数の読み取りは見つかりませんでした。

## 実行時の詳細

wide kernel は各出力行を4 sub-group の work-group で処理し、IQ3_S 重みと Q8_1 活性値を読み、列ごとに内積を累積します。`ncols` ごとにテンプレートを選び、起動に成功した場合は `iq_mmvq()` が `check("iq_mmvq")` を呼んで戻ります。条件に合わない場合の通常 multi kernel も同じ `iq_mmvq()` の dispatch 内で選択されます。環境変数固有のログ出力はありません。

## 文書と測定値

`docs/INTEL.md` は B70、IQ3_XXS、1 GPU、T=1 の unitrace で、対象行列の kernel time が token あたり 1.36 ms から 0.60 ms になった一方、greedy 出力は token 198/256 で既定経路と分岐したと記録しています。また、B70 の IQ3_S を使った 5 組の interleaved 測定では decode が 33.39 から 33.29 tok/s（-0.3%）、4K prompt が 40.71 から 40.79 tok/s と記録し、opt-in のままとしています。これらは同資料の条件付き測定値であり、他の環境での性能・出力を保証するものではありません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4564-4568`: `atoi` による値判定と static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4570-4590`: wide kernel の起動と `ncols` 1〜8 の範囲。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4592-4604`: IQ3_S type `21` のみの wide dispatch と multi kernel fallback。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4075-4085`: native MMVQ dispatch から `iq_mmvq()` を呼び出す箇所。
- `sycl/CMakeLists.txt:217`: `iq_kernels` を SYCL kernel source set に含める箇所。
- `docs/INTEL.md:484-489`: opt-in の説明と上記測定記録。
