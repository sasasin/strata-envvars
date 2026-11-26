# `STRATA_IQ_GATHER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AVX-512 の i-quant expert 行カーネルで、IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S のコードブック値を scalar table loads で集めるか、AVX-512 gather 命令で集めるかを選ぶ。値が変えるのはコードブック参照の実装方法であり、両方の分岐は同じ table entry を行ベクトルに組み立てる。対象コードのコメントは結果が scalar decode と bit-for-bit 同じとしている。読み取りは `engine/src/kernels/cpu/iq_avx512.cpp` の翻訳単位スコープ `gather` 初期化子だけにある。`engine/src/kernels/cpu/native_expert.cpp` は公開関数 `iq512_gather_on()` を通じて、IQ3_XXS / IQ3_S の一部 1-token 経路を選ぶ。

## 値と判定

`std::getenv` の結果を調べ、未設定または空文字なら `cpu_gather_fast()` の結果を使う。非空なら `std::atoi(v) != 0` を使うため、文字列全体の数値検査はなく、先頭の整数変換結果が 0 かどうかで判定する。先頭の空白や符号は `atoi` に従い、数値の後ろは検査されない。例えば `1`, `-1`, `2`, `1junk` は有効、`0`, `0junk`, `true`, `false`, `junk` は無効。空文字は明示されても自動判定に戻る。範囲チェックや無効値警告はない（`engine/src/kernels/cpu/iq_avx512.cpp:42-45`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `iq_avx512.cpp` を含む x86 CPU build | `cpu_gather_fast()` が true なら gather、false なら scalar loads | `1`, `2`, `-1`, `1tail` | `0`, `0tail`, `true`, `junk` |
| `iq_avx512.cpp` を含まない build / portable stub | この変数を読む実装ではない。portable stub の `iq512_gather_on()` は常に false | 該当なし | 該当なし |

`cpu_gather_fast()` は ISA 上限が AVX2 未満なら false とし、CPU vendor が GenuineIntel で、CPUID が AVX-VNNI を示す CPU のうち、列挙された E-core-only 型番でない場合に true とする（`engine/src/kernels/cpu/expert_layout.cpp:320-339`）。変数が空または未設定の場合、このプローブの機種判定が既定値となる。

## 有効になる条件

- `engine/cmake/backends/cpu.cmake:303-317` によれば、`iq_avx512.cpp` は native expert source のうち x86 build に追加される。CPU 側の実行時 dispatch は `cpu_vnni_ok()` が true かつ `STRATA_NO_IQ512` が未設定であることを要求する（`engine/src/kernels/cpu/native_expert.cpp:564-568`）。
- 主な使用先は native expert の gate/up 多 token 経路で、`nt >= native_gu_mt_min(...)`、対象形式が上記5種類、AVX-512 kernel が利用可能な場合に `iq512_gu_rows()` を呼ぶ（`engine/src/kernels/cpu/native_expert.cpp:540-546, 654-703`）。`STRATA_IQ_MT_MIN` による token 数のしきい値がこの経路を変える。
- 1 token では `avx512 && iq512_gather_on()` が真の場合にだけ、`STRATA_NO_IQ512X1` 未設定、format が IQ3_XXS または IQ3_S、tail がなく、`x512_one_ok()` が通る等の条件で exact row kernel を試す（`engine/src/kernels/cpu/native_expert.cpp:601-618`）。偽ならこの特別経路を使わず、後続の通常 dispatch / dot 経路に進む。
- gather が false でも AVX-512 multi-token kernel 自体は無効にならず、同カーネル内の scalar table-load 分岐で処理できる（`engine/src/kernels/cpu/iq_avx512.cpp:70-77, 91-99, 111-122, 132-139, 154-168`）。
- AVX2-only 経路の gather 設定名は別の `STRATA_IQ256_GATHER` であり、この変数は AVX2 gather を選ばない（`engine/src/kernels/cpu/iq_avx2.cpp:14-16`）。

## 実行時の詳細

`gather` は `iq_avx512.cpp` の翻訳単位スコープ `const bool` であり、初期化子が `getenv` を実行してから値を保持する。一度初期化された値を `iq512_gather_on()` が返し、decode 関数が IQ2 / IQ3 formats の grid lookup 分岐で使う（`engine/src/kernels/cpu/iq_avx512.cpp:42-45, 668`; decode 分岐は同ファイル `73-77, 95-99, 114-122, 135-139, 157-168`）。従って後からプロセス環境を変更しても、保持済みの `gather` の値は再読込されない。CLI 引数、設定ファイル、別環境変数によるこの値の上書き処理は見つからなかった。

native AVX-512 multi-token gate/up rows が使われる場合、値は IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S の各 decode 内で gather 命令か scalar table loads の選択に使われる。別の single-token exact IQ3 経路は `iq512_gather_on()` が true のときのみ候補になる。CPU backend の native expert 経路でなく、portable implementation では stub が false を返し、`iq_avx512.cpp` の `getenv` 実装も対象にならない（`engine/src/kernels/cpu/portable.cpp:113-120`）。サーバーモード固有の判定はない。

残る直接参照は実行時設定の読み取りではない。CMake は parity 用テストを `STRATA_IQ_GATHER=0` と `=1` でそれぞれ起動する（`engine/cmake/backends/cpu.cmake:442-448`）。`terminal/data/settings-register.json:18741-18760` は読み取り箇所を列挙する登録データで、Strata runtime が値を読む実装ではない。ベンチ結果の JSON と README にある参照も実行環境の記録である。

## ログと測定値

この変数を読み取った後に有効状態や無効値を通知する Strata のログ、警告、終了処理は見つからなかった。コードコメントには Ryzen 5 7600 で gather が scalar lookup より 3–5% 遅かったとの測定と、Sapphire Rapids で gather を使う exact row の測定記述があるが、コメントにある実験条件の範囲を超えて一般化できない（`engine/src/kernels/cpu/iq_avx512.cpp:38-41`; `engine/src/kernels/cpu/native_expert.cpp:601-605`）。`docs/DETAILS.md` にはこの変数名の説明がなく、ベンチ記録には `STRATA_IQ_GATHER=1` を含む実行環境の記載があるだけで、この設定の意味や効果を独立に検証した資料ではない（`docs/bench-results/2026-10-09-community-rtx-5080-w7-2475x-ud-iq4xs-786k/README.md:56`, `strata-ud-iq4_xs-786k.json:66`）。

## 根拠

- 読み取り・値判定・decode 分岐・公開状態関数: `engine/src/kernels/cpu/iq_avx512.cpp:38-53, 70-77, 91-99, 111-139, 151-168, 668-685`
- 既定値の CPU 判定: `engine/src/kernels/cpu/expert_layout.cpp:320-339`
- native expert の AVX-512 条件、single-token 経路、multi-token 経路: `engine/src/kernels/cpu/native_expert.cpp:540-546, 564-568, 601-618, 654-703`
- build source 条件と portable stub: `engine/cmake/backends/cpu.cmake:303-317`; `engine/src/kernels/cpu/portable.cpp:113-120`
- テスト設定と登録データ: `engine/cmake/backends/cpu.cmake:442-448`; `terminal/data/settings-register.json:18741-18760`
