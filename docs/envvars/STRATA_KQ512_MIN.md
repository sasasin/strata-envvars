# `STRATA_KQ512_MIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU の native expert 行カーネルが、Q4_K gate/up と Q5_1 / Q8_0 down に AVX-512 VNNI 実装を使い始める最小 token 数を指定する。gate/up と down の両方で同じ既定値 8 を使い、各呼び出しの `nt` がこの数以上のとき候補になる。これは CPU native expert の行計算の dispatch 閾値であり、GPU カーネルの閾値ではない。実装は `native_gu_rows_impl` と `native_down_rows_impl`（`engine/src/kernels/cpu/native_expert.cpp`）にある。`ExpertPool::run_split_multi_native` 経由の CPU expert 処理で呼ばれ、CUDA prefill の CPU share もこの pool に job を渡す（`engine/src/kernels/cpu/pool.cpp:1559`、`engine/src/prefill/prefill.cpp:6303-6317`）。

## 値と判定

環境から `std::getenv` で取得し、未設定なら `8`、設定されていれば `std::atoi` の戻り値を使う。空文字も設定済みとして `atoi("") == 0` になり、数値として解釈できない先頭なら `0` になる。`atoi` は数値の後ろを検査しないため、たとえば `8junk` は 8、`3.5` は 3 として扱われる。先頭空白と符号は `atoi` の変換規則に従う。文字列全体の妥当性検査、大文字小文字の判定、範囲 clamp はない。値は符号付き `int` に格納され、範囲外入力の結果はここでは保証されない。分岐は `nt >= kq512_min` であるため、0 や負値も拒否されず、正の `nt` は閾値を満たす。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| Q4_K gate/up (`f.gu_type == 12`)、AVX-512 条件等を満たす場合 | 8 | `8`, `4`, `0`, `-1`, `8junk`（atoi 結果が 8 以上で、`nt` も以上） | `9`（`nt` が 8 のとき）、`3.5` は 3 と解釈され `nt < 3` なら不成立 |
| Q5_1 / Q8_0 down (`f.d_type == 7` / `8`)、AVX-512 条件等を満たす場合 | 8 | 同上 | 同上 |

「有効」は閾値条件を満たす意味であり、カーネルが実際に選ばれるには後述の CPU・型・適合性条件も必要。`STRATA_NO_KQ512` が設定されている場合は AVX-512 経路自体が無効になる。`STRATA_KQ256` が非ゼロなら、AVX-512 経路が選ばれなかったときに別の AVX2 KQ 経路が選ばれる場合がある（`native_expert.cpp:658-672, 806-817`）。

## 有効になる条件

- x86 CPU と OS が `cpu_avx512_ok()` の AVX-512 判定を通ること。判定は ISA cap、CPUID、OSXSAVE と XCR0 も確認する。`STRATA_FORCE_AVX2=1` または ISA cap の制限などで AVX-512 が無効なら本変数の値にかかわらず使われない（`engine/src/kernels/cpu/expert_layout.cpp:75-105`）。
- `STRATA_NO_KQ512` が未設定であること。これは値の真偽ではなく設定有無で判定するため、空文字を含め何らかの値があれば AVX-512 KQ 経路を止める（`engine/src/kernels/cpu/native_expert.cpp:661-663, 807-809`）。
- gate/up は型 12 (Q4_K)、down は型 7 (Q5_1) または 8 (Q8_0) であること。ほかの型にはこの閾値は適用されない（同ファイル `:287-288, 664-665, 810-812`）。
- `kq512_ok(type)` の一度きりの実行時照合が成功すること。対応型、CPU 判定、quant dot と activation 変換の有無を確認し、合成 block の結果をこの build の dot と比較する。失敗すれば当該型では AVX-512 KQ 行を選ばず後続 dispatch に進む（同ファイル `:290-301, 308-357, 663-665, 809-812`）。
- arithmetic が `NativeArithmetic::Default` であるか、`flavour_avx2()` が真であること（同ファイル `:664-665, 810-812`）。
- 実際のその行計算で `nt >= kq512_min` であること。閾値は clamp されない。

## 実行時の詳細

各行関数は、gate/up では型 12 に対して、down では型 7 / 8 に対して条件を評価し、条件が成立すると `kq512_gu_rows` または `kq512_rows` を呼んで通常の後続 dispatch を return する（`engine/src/kernels/cpu/native_expert.cpp:660-672, 806-817`）。この分岐は重みの行計算を選ぶもので、ルーティングされた expert や token の選択条件は変更しない。CPU pool は native job の token 数 `nt` を使って各 expert を処理し、CUDA prefill の CPU share では expert の job を `MAXT` 以下に分割する（`engine/src/kernels/cpu/pool.cpp:1559`、`engine/src/prefill/prefill.cpp:6303-6317`）。

閾値は `native_gu_rows_impl` / `native_down_rows_impl` の関数内 `static const int` 初期化で読み込む。通常の行関数と `WindowInvariant` 用の行関数は別 template specialization を通るため、それぞれ初回呼び出し時に一度評価される。その後の `setenv` などで同一 specialization の値は更新されない。実行ファイル起動時に一律で parse する処理、CLI 引数や設定ファイルによる上書きはない（同ファイル `:559, 662, 792, 808, 897-914`）。

AVX-512 KQ 分岐に入れない場合は通常の dispatch が続く。`STRATA_KQ256` を設定し `atoi` が非ゼロなら、AVX2 条件と `nt >= 2` 等を満たす型 12 / 7 / 8 で AVX2 KQ が候補になる。これも設定なしなら無効である（同ファイル `:658-672, 798, 814-817`）。閾値未満そのものを理由とするログやエラーはなく、別条件にも合わなければ後続のカーネルまたは dot-product fallback に進む。

## ログと測定値

閾値の読み取りや閾値未達を知らせるログはない。初回照合で build の dot と不一致の場合は stderr に `strata: the AVX-512 rows of type %d differ from this build's dot (n=%d, %d tokens): its dot runs per token instead` を出し、照合結果を型ごとに cache する。その型の AVX-512 KQ 行は選ばれず後続処理に進む。閾値が低くても照合自体は一致性確認であり、エラー終了にはならない（`engine/src/kernels/cpu/native_expert.cpp:294-301, 308-357`）。

`docs/DETAILS.md:1183` は `STRATA_NO_KQ512` の既定経路について、CPU prompt share の 8-token jobs と decode window の 2–7-token groups、Xeon 8352V で floor 3 / 4 時に 1–6% 遅く、8 で横ばいだったという測定説明を載せ、「`STRATA_KQ512_MIN=N` moves the token floor」と記す。これは同資料の記載であり、本調査では build や測定を実施していない。ソースコメントも同じ例を記載する（`engine/src/kernels/cpu/native_expert.cpp:659-662`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:287-301, 308-357` — 対応型、AVX-512 KQ の適合性検査と結果 cache。
- `engine/src/kernels/cpu/native_expert.cpp:658-672` — gate/up 側の閾値読み取り、型・条件、カーネル選択と AVX2 fallback。
- `engine/src/kernels/cpu/native_expert.cpp:806-817` — down 側の閾値読み取り、型・条件、カーネル選択と AVX2 fallback。
- `engine/src/kernels/cpu/native_expert.cpp:897-914` — Default / WindowInvariant の entry point。
- `engine/src/kernels/cpu/expert_layout.cpp:75-105` — CPU ISA cap、AVX-512 の CPU / OS 判定。
- `engine/src/kernels/cpu/pool.cpp:1559`、`engine/src/prefill/prefill.cpp:6303-6317` — CPU expert job dispatch と prefill CPU share からの呼び出し。
- `docs/DETAILS.md:1183` — Strata 資料の既定経路・測定値の記載。
