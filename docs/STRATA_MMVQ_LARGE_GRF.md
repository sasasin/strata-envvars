# `STRATA_MMVQ_LARGE_GRF`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata が所有するソースコードであり、oneAPI/SYCL ランタイムや GPU ドライバー内部の動作は含めない。

## 役割

SYCL 版 native MMVQ の一部の複数列 wide kernel に、256 registers per thread を要求するカーネルを選ばせます。通常の 128-register wide kernel と同じ計算カーネル本体を起動しますが、SYCL の kernel property に `grf_size<256>` を付けます。1列の処理にはこの切替を使いません。

この変数を読む実装は `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあります。CUDA/HIP ネイティブ実装や一般の MMVQ 経路すべてに適用される設定ではありません。

## 値と判定

値は `std::atoi` で整数に変換し、結果が 0 かどうかで判定します。文字列全体の妥当性は検査せず、整数として読み取れる接頭部分の後ろは判定に使われません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 初回判定時の SYCL device が Alchemist なら有効、それ以外は無効 |
| 設定値が `atoi` で 0 になる | 無効。空文字、数字で始まらない文字列、`0`、`0abc` など |
| 設定値が `atoi` で 0 以外になる | 有効。`1`、`-1`、`2abc` など |

したがって `=1` だけが有効値ではありません。先頭の空白や符号を `atoi` が受け付け、数値以降の文字列は無視します。値を明示した場合は Alchemist の既定値を上書きします。判定結果は関数内の `static const bool` に一度保存されるため、最初の判定後にプロセス環境を変更しても再評価されません。複数の SYCL device を使う場合、未設定時の既定値はこの関数を最初に呼び出した queue の device で決まり、その後は共有されます。

## 有効になる条件

- Strata の SYCL native MMVQ 経路を使い、対象 kernel の dispatch 条件も満たす必要があります。
- Q4_K、Q5_K、IQ4_XS の wide kernel では、`try_wide()` が選択され、`ncols` が 2〜8 の場合に large-GRF 分岐が候補になります。1列では通常の wide kernel を使います。`STRATA_MMVQ_WIDE_K=0` で wide 経路が無効な場合、または `STRATA_MMVQ_WIDE_K_RPW` が 2 / 4 の kernel を選ぶ場合は、この変数による切替箇所を通りません。
- Q6_K の GGUF-layout wide kernel では `g_q6k_wide` が有効で、その呼び出し条件（列数、`n_in`、`n_out`）を満たし、さらに `rpw == 1` かつ `q6k_a2()` が有効なときだけ確認されます。1列、異なる `rpw`、または A2 を使わない経路では切替しません。
- Q6_K の planar 経路では、重みが planar registry に登録済みの場合に候補となり、列数が 2 以上の chunk で確認されます。1列 chunk では切替しません。
- Alchemist 以外でも、環境変数を `atoi` で非ゼロになる値に設定すればコード上は large-GRF kernel を選択します。ただし、その device / コンパイラーで 256-GRF property を利用できることを確認する fallback は、この選択箇所にはありません。

## 実行時の詳細

`mmvq_large_grf()` は初回呼び出し時に環境変数を読み、未設定なら `strata::intel_gpu_gen(device) == Alchemist` を既定値にします。SYCL device 分類は GPU 以外を `Unknown` とし、取得できる architecture 情報、または device 名から Alchemist / Battlemage を判定します（`sycl/include/strata/sycl_queue.hpp:120-153`）。

有効判定かつ複数列の対象経路では、Strata は `sycl::ext::intel::experimental::grf_size<256>` property を付けて `parallel_for` を呼び出します。通常経路ではその property のない wide kernel を起動します。環境変数を読む処理自体にログ出力はなく、値が不正な場合の警告やエラー処理もありません。カーネル起動後のコンパイラー / ランタイム / device の結果は Strata ソースからは一律に断定できません。

Strata の `docs/INTEL.md` は、この設定について Arc A-series で既定有効、`=1` で強制有効、`=0` で無効と説明し、wide kernel の 128 GRF 時の spill を避ける目的を記しています。ソース上では `atoi(...) != 0` のため、強制有効・無効はそれぞれ整数変換結果の非ゼロ・ゼロに対応します。性能記述は同資料の測定条件に限られ、ここでは独自に再測定していません。

## 根拠

- 環境変数の読み取り、`atoi` 判定、Alchemist 既定値、キャッシュ: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1718-1729`。
- Q6_K GGUF-layout wide kernel の適用条件と GRF256 起動: 同 `:1731-1769`、native Q6_K 呼び出し条件 `:3810-3832`。
- Q4_K / Q5_K / IQ4_XS wide kernel の GRF256 分岐、1列での除外、wide 適用条件: 同 `:1984-2009,2014-2026`。対象型の dispatch は Q5_K `:3428`、IQ4_XS `:3651`、Q4_K `:3742`。
- Q6_K planar kernel の GRF256 分岐と複数列 chunk: 同 `:2944-2965,2968-2997`。planar 経路の registry 判定と GGUF-layout wide より先に試す順序は `:3810-3817`。
- SYCL device の Alchemist / Battlemage 判定: `sycl/include/strata/sycl_queue.hpp:120-153`。
- Strata の説明および測定の文脈: `docs/INTEL.md:491-500`。
