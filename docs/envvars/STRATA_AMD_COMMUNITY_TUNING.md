# `STRATA_AMD_COMMUNITY_TUNING`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

AMD 向けに追加された変更のうち、実行時に切り替えられる gfx103x の QSA selector 既定値と、特定の gfx1030 / rocBLAS build 用の community tuning table の読み込みを制御します。gfx1010 の SDWA dot4 はデバイスコードにコンパイルされるため、この環境変数では切り替わりません。ビルド時の CMake option `STRATA_AMD_COMMUNITY_TUNING` を `OFF` にすると、その dot4 を除いて portable loop をコンパイルします（`include/strata/core/amd_community.hpp:32-46,80-103`, `CMakeLists.txt:95-101`, `include/strata/hip_compat/intrinsics.hpp:30-55`）。

## 値と判定

`tuning_on()` は `std::getenv()` の結果を文字列全体で比較します。数値変換や大文字小文字の正規化はしません。

| 値 | 判定 |
|---|---|
| 未設定 | ON |
| 空文字 | ON |
| `0`, `off`, `false`, `no` | OFF（完全一致・小文字のみ） |
| その他すべて | ON。例: `1`, `00`, `0abc`, `OFF`, `False`, 空白 |

したがって `0abc` は `0` として扱われず ON です。無効値として拒否したり、別の値へ fallback したりする処理はありません。実装: `include/strata/core/amd_community.hpp:32-37`。

## 有効になる条件

- **gfx103x QSA block-score selector:** HIP の QSA 経路で、GPU の arch 名が `gfx103` で始まり、`STRATA_SELECT_SIMT` が未設定のとき、ON なら SIMT mode 2 (`simt2`)、OFF なら warp kernel が既定になります。`STRATA_SELECT_SIMT` が設定されていればそちらが優先されます。値は先頭文字だけで判定され、`1...` は mode 1、`2...` は mode 2、それ以外（空文字を含む）は mode 0 です。`STRATA_SELECT_OLD` が設定されている経路では QSA の新 selector 呼び出し自体を迂回します（`src/kernels/cuda/qsa_select.cu:2215-2226`, `src/prefill/prefill.cpp:4278-4284,7503-7510`）。
- mode 2 が選ばれても、QSA block-score 呼び出しが到達可能である必要があります。`STRATA_SELECT_ALT_MIN_TOKENS` が 0 以上に parse されるとその値が token 閾値になり、未設定または負値なら、環境変数未指定で選ばれた community mode 2 の閾値は 28,672 tokens です。必要な reach に届かない場合はこの関数が `false` を返し、呼び出し側が通常の `qsa_block_scores()` に進みます（`src/kernels/cuda/qsa_select.cu:2227-2238`, `src/prefill/prefill.cpp:4279-4284,7504-7508`）。
- **gfx1030 rocBLAS table:** HIP build に rocBLAS support があり、`STRATA_ROCBLAS_TUNING` で table ファイルまたは table directory が指定されて、実行中の arch と rocBLAS version が community table の組と完全一致する場合に限り、この変数が table の許可を決めます。対象組は gfx1030 と `5.4.0.ad84daa81c`、または gfx1030 と `5.2.0.dabb6df2b98-dirty` です。feature suffix は arch 比較前に除かれます。非 community table はこの変数にかかわらず許可されます（`include/strata/core/amd_community.hpp:49-73`, `src/prefill/gemm.cu:449-472,490-504`）。実際の GEMM 呼び出しで table の solution を使うには FP16 prompt GEMM 経路も必要です。Strata の AMD 資料は `STRATA_HIP_PROMPT_F16=1` と `STRATA_ROCBLAS_TUNING` を table 利用条件として記載しています（`src/prefill/gemm.cu:1324-1335`, `src/prefill/prefill.cpp:1891-1896`, `docs/AMD_HIP.md:700-706`）。
- **gfx1010 dot4:** 実行時の ON/OFF 判定はコンパイル済み device code を変えません。ビルド時の CMake option が ON なら SDWA sequence が入り、OFF なら `STRATA_AMD_COMMUNITY_DOT_OFF` によって portable loop が選ばれます。CMake option の既定値は ON です（`CMakeLists.txt:95-101`, `include/strata/hip_compat/intrinsics.hpp:30-55`）。

## 実行時の詳細

対象名の実際の環境読み取りは `include/strata/core/amd_community.hpp:33-36` の `getenv` です。同名を引数で渡す env helper はありません。`tuning_on()` 自体は static cache を持たず、呼び出しごとに環境を読み直します。ただし QSA 経路は `community_on` を `static const` に保持するため、最初の `qsa_block_scores_tc()` 呼び出し後の環境変更はその経路の既定値に反映されません（`src/kernels/cuda/qsa_select.cu:2221-2226`）。rocBLAS table は Gemm の初期化時に `create_rocblas_state()` が判定して読み込みます。初期化済み Gemm の table はその後の環境変更で再選択されません（`src/prefill/gemm.cu:470-504,673-695,744-767`）。

HIP engine の起動時には `apply_arch_defaults()` が `startup_line()` を呼び、gfx1010 または gfx103x なら stderr に状態を 1 行出します。gfx1010 で環境値が OFF でも dot4 が build に含まれていれば、実行時設定では外せず rebuild が必要である旨を表示します（`src/program/generate.cpp:3702-3719`, `src/core/arch_defaults.cpp:221-225`, `include/strata/core/amd_community.hpp:80-103`）。他の arch ではこの startup line は空です。

rocBLAS table が community table と判定され、環境値が OFF の場合、Strata は stderr に `prefill gemm: the rocBLAS table for ... is community-made and STRATA_AMD_COMMUNITY_TUNING=0; rocBLAS's default kernels run` を出して table を読み込まず、default kernel を使います（`src/prefill/gemm.cu:500-505`）。ON でも table の指定が空、arch/version が一致しない、ファイルの読み込みに失敗する場合などは table が利用されず、コード上の fallback / 診断はその経路に従います（`src/prefill/gemm.cu:470-510`）。

QSA で mode 1 または 2 が実際に選ばれると、Strata は初回に `qsa select: FP32 tiled scorer (STRATA_SELECT_SIMT=...), tiles ...` を stderr に出します。mode 2 では `block_scores_simt2_kernel` を起動し、CUDA error があればエラー文字列を出して終了します（`src/kernels/cuda/qsa_select.cu:2240-2258`）。このログは selector が実行された場合のもので、環境値が ON であることだけでは出ません。

## 根拠

- 共有判定、値の規則、community table の arch/version 条件、起動ログ: `include/strata/core/amd_community.hpp:30-105`。
- gfx103x QSA の既定選択、明示 selector の優先、token 閾値と fallback: `src/kernels/cuda/qsa_select.cu:2215-2258`, `src/prefill/prefill.cpp:4278-4284,7503-7510`。
- rocBLAS table の指定・読み込み・OFF 時の fallback と Gemm 初期化: `src/prefill/gemm.cu:449-510,673-695,744-767,1324-1335`。
- gfx1010 の build-time 切り替え: `CMakeLists.txt:95-101`, `include/strata/hip_compat/intrinsics.hpp:30-55`。
- AMD 向け条件の説明と table 利用要件: `docs/AMD_HIP.md:687-706`。ここにある性能値は貢献者による測定として記載された値であり、本調査では再測定していません。
