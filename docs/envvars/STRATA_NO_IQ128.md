# `STRATA_NO_IQ128`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

AVX2 を使えないが AVX1 を使える CPU で、native expert の一部の gate/up 行と down 行に使う Strata の 128-bit AVX1 カーネルを無効にします。無効になると、それらの行計算は ggml-cpu の `vec_dot` にフォールバックします。この設定は native expert の CPU 経路に作用し、CUDA/HIP/SYCL の GPU カーネル選択は変更しません。

## 値と判定

値の内容は parse せず、`std::getenv("STRATA_NO_IQ128") == nullptr` かどうかだけを判定します。

| 環境変数の状態 | AVX1 カーネル |
|---|---|
| 未設定 | 有効候補（CPU・形式・行数の条件も満たす場合） |
| 任意の値を設定 | 無効。空文字、`0`、`false` を含む |

`native_gu_rows()` と `native_down_rows()` の各判定は関数内の `static const bool` に保存されるため、それぞれ最初に呼ばれた時点の値がプロセス内で使われます。その後に環境を書き換えても再判定されません。`generate.cpp` には起動時の経路説明ログ用に別の `getenv()` 判定があります。

根拠: `src/kernels/cpu/native_expert.cpp:143-166,233-254`; `src/program/generate.cpp:2898-2907`。

## 有効になる条件

この変数が未設定でも、AVX1 カーネルを使うには CPU の実行時判定で `cpu_avx1_ok()` が真、かつ `cpu_avx2_ok()` が偽である必要があります。AVX2 対応 CPU では AVX1 判定が常に偽なので、この変数を設定しても既存の AVX2/AVX-512 選択は変わりません。AVX1 が使えない CPUでも影響しません。

- Gate/up: `nt >= native_gu_mt_min(f.gu_type)` かつ形式が IQ3_XXS (18), IQ3_S (21), IQ2_S (22), IQ4_XS (23) のときだけ AVX1 カーネル候補です。既定の `STRATA_IQ_MT_MIN` は 2 で、別途設定されている場合は `atoi` の結果がしきい値になります。条件を満たさない場合や対象外形式では ggml-cpu の `vec_dot` に進みます。
- Down: 形式が IQ4_NL (20) または Q2_0 (42) の場合に AVX1 カーネル候補です。この分岐には gate/up の `nt` しきい値はありません。
- AVX1 カーネルの実装ソースは native expert CPU ターゲットに含まれ、AVX を有効にし AVX2/FMA/F16C を無効にしてコンパイルされます。CMake の ISA floor 設定は experimental older-CPU build の設定です。実際に呼ぶかどうかは上記の実行時 CPU 判定でも決まります。

根拠: `include/strata/kernels/cpu/iq_avx1.hpp:1-13,21-31`; `src/kernels/cpu/native_expert.cpp:124-140,143-193,233-255`; `src/kernels/cpu/iq_avx1.cpp:15-20`; `CMakeLists.txt:1284-1299,1317-1322,1343-1352`。

## 実行時の詳細

native expert の CPU pool は、expert の gate/up と down の行を `native_gu_rows()` / `native_down_rows()` に渡します。AVX1 経路が選ばれれば、該当行を 128-bit lane の専用ルーチンで計算します。無効化された場合は `traits(...)->vec_dot` を用いた ggml-cpu の行・token ごとの計算にフォールバックし、他の条件を満たす AVX2/AVX-512 経路にも昇格しません。

`generate.cpp` は native pack の起動時に AVX-512 非対応 CPU向けの説明を stderr に出します。AVX2 も非対応で、AVX1 が利用可能かつこの環境変数が未設定なら `AVX1 128-bit (iq_avx1, the older-CPU build)`、それ以外なら `ggml-cpu vec_dot (no AVX2: the older-CPU build)` と表示します。このログ判定は AVX1 カーネルの実行判定とは別で、形式や `nt` の条件までは見ていません。

ソースツリーの `docs/DETAILS.md` では `STRATA_NO_IQ128` の説明を確認できませんでした。性能値や計算結果への影響はこの調査では測定していません。

根拠: `src/kernels/cpu/pool.cpp:708-718`; `src/kernels/cpu/native_expert.cpp:180-229,243-278`; `src/program/generate.cpp:2898-2907`。
