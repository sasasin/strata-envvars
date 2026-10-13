# `STRATA_IQ256_GATHER`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Strata のネイティブ CPU expert 経路で、AVX2 の multi-token IQ カーネルが IQ3_XXS・IQ3_S・IQ2_S のグリッド値を scalar load で組み立てるか、AVX2 gather 命令で読むかを選ぶ。`1` は gather、`0` は scalar decode。未設定または空文字では CPU を判定して選ぶ。どちらも同じグリッド語を同じレーンへ渡す実装として書かれているが、この変数が指定するのは読み出し方式であり、出力の数値同一性を独立に測定したものではない。

## 値と判定

| 環境値 | 内部値 | 選択 |
|---|---:|---|
| 未設定 | `-1` | 呼び出しスレッドのコアで自動判定 |
| 空文字 | `-1` | 呼び出しスレッドのコアで自動判定 |
| `atoi(value) == 0` | `0` | 全コアで scalar decode |
| `atoi(value) != 0` | `1` | 全コアで gather |

`std::atoi` を使い、文字列全体の厳密な数値 parse はしない。したがって、先頭の空白や符号の後の数値部分を変換し、数値の後ろに文字があってもその部分は無視する（例: `2x` は gather、`0x` は scalar、`x2` は変換結果 0 で scalar）。負の数も変換結果が 0 でなければ gather。大文字小文字を判定する文字列比較はない。無効な数値文字列に対する警告や別の fallback はない。

`iq256_gather_setting()` の値は関数内の `static const` に初回評価時だけ保存される。プロセス起動後に環境値を変えても、その後の選択には反映されない。

## 有効になる条件

- Strata のネイティブ expert CPU 経路を使い、AVX2 が利用可能で、AVX2 IQ カーネルへ dispatch されることが必要。実際の gate/up 行は `native_gu_rows()` が CPU 機能、対応形式、`nt >= mt_min` を確認してから呼ぶ。AVX2 がない場合、`STRATA_NO_IQ256` が設定されている場合、または条件に合わない場合は ggml-cpu 等へフォールバックし、この変数による decode 選択は行われない。
- AVX-512 が利用可能で IQ512 カーネルが対応する IQ3_XXS・IQ3_S・IQ2_S では、通常は AVX-512 経路が先に選ばれるため、この変数はその経路を切り替えない。`STRATA_NO_IQ512` などで AVX-512 経路が無効なら、AVX2 経路に到達する可能性がある。
- gather 方式を適用するのは形式番号 18 (IQ3_XXS)、21 (IQ3_S)、22 (IQ2_S) のみ。IQ2_XXS、IQ2_XS、IQ4_XS にはこの gather decode の分岐を適用しない。
- 未設定・空文字時の自動判定は、`cpu_gather_fast()` による CPU 全体の条件と、`cpu_gather_fast_here()` による呼び出しスレッドのコア判定を使う。前者は `STRATA_FORCE_ISA` の上限が通常値で、Intel GenuineIntel、CPUID の AVX-VNNI feature があり、特定の E-core-only model でないことを条件にする。hybrid CPU では CPUID leaf `0x1A` の core type が P-core (`40h`) のスレッドだけ gather を選ぶ。E-core (`20h`) は scalar decode。非 hybrid CPU は core type なしとして CPU 全体の条件を満たせば gather を選ぶ。
- 明示的な非ゼロ値はこの自動性能判定を上書きし、AVX2 kernel が実行されるすべての対象スレッドで gather を選ぶ。環境値だけでAVX2 kernel自体を有効化することはなく、AVX2 CPU機能 gate は残る。

## 実行時の詳細

`native_gu_rows()` は IQ の gate/up 行を処理する際、AVX2 を使える条件を満たすと `iq256_gu_rows()` を呼ぶ。そこで `iq256_variant()` が `iq256_gather_setting()` を読み、設定値があれば一律にその選択を使い、未設定なら `cpu_gather_fast_here()` を呼んでスレッドごとに選ぶ。後者は P/E core の判定結果を `thread_local` に保存する。AVX-VNNI が使える場合は整数積和の VNNI 版も選ばれるが、gather/scalar の選択とは別の variant bit である。

選ばれた variant は、IQ3_XXS・IQ3_S・IQ2_S の decode template をそれぞれ gathered (`118`/`121`/`122`) または通常 (`18`/`21`/`22`) に分岐させる。これは CPU 計算経路の選択であり、この変数を読んだことによる stdout/stderr のログ、警告、エラー、終了処理は実装にない。

`STRATA_IQ3S_MT1` との相互作用もある。`STRATA_IQ_MT_MIN` が未設定で、`STRATA_IQ3S_MT1` が設定され、AVX2・非AVX-512等の条件を満たすと、IQ3_S の multi-token kernel を1 token groupにも使う判定が行われる。この判定は `iq256_gather_setting() != 0` と `cpu_gather_fast()` も条件にするため、`STRATA_IQ256_GATHER=0` はこの特別扱いを無効化する。これは `STRATA_IQ256_GATHER` 自体の gather variant 選択とは別の dispatch 条件である。

## 根拠

- `src/kernels/cpu/expert_layout.cpp:202-209` — `getenv`、未設定・空文字の処理、`atoi`、初回値の static cache。
- `src/kernels/cpu/expert_layout.cpp:211-250` — CPU 全体の自動判定条件と、呼び出しスレッドの core type 判定・thread-local cache。
- `include/strata/kernels/cpu/expert_layout.hpp:62-72` — API コメント上の設定値と自動判定の説明。
- `src/kernels/cpu/native_expert.cpp:37-43,115-131,134-179` — 対象形式、`STRATA_IQ3S_MT1` との条件、AVX2/AVX-512のgate/up dispatch。
- `src/kernels/cpu/iq_avx2.cpp:456-501` — variant の決定と gate/up 行から variant decode への受け渡し。
- `src/kernels/cpu/iq_avx2_rows.inl:209-235` — gather decode を使う型と、それ以外の型の dispatch。
- `docs/DETAILS.md:97-105` — 関連する `STRATA_IQ3S_MT1` の説明。Alder Lake以降かつAVX-512なしのIQ3_S経路でAVX2 kernelがgridをgatherすることに触れているが、`STRATA_IQ256_GATHER` の個別比較測定や値の parse 規則は説明していないため、本書ではコードを根拠にした。
