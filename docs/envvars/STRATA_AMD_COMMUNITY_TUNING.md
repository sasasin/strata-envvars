# `STRATA_AMD_COMMUNITY_TUNING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AMD 向けにコミュニティ由来の変更を実行時にまとめて切り替える。実行時値を OFF にすると、gfx1030 の特定 rocBLAS tuning table をロードせず、gfx103x の QSA block-score selector の simt2 既定選択も止める。一方、gfx1010 の SDWA dot4 はデバイスコードなので、すでにその命令列を含む build では実行時値だけで portable loop に戻せない。gfx1010 の dot4 を build から外すには、別の CMake option `-DSTRATA_AMD_COMMUNITY_TUNING=OFF` が必要である。実行時の判定と build 時の定義は同名だが別の設定である（`engine/include/strata/core/amd_community.hpp:32-47, 69-78`, `engine/CMakeLists.txt:107-113`, `engine/include/strata/hip_compat/intrinsics.hpp:26-35`）。

対象は次の経路で、他の GPU 世代にはこれらの変更を適用しない。

- gfx1010: build に含まれる dot4 命令列。
- gfx1030: 2 つの厳密一致 rocBLAS solution table。
- gfx103x: QSA block-score の simt2 selector 既定値。明示的な `STRATA_SELECT_SIMT` があればそちらを使う（`engine/include/strata/core/amd_community.hpp:49-78`）。

## 値と判定

`std::getenv` が返す文字列を数値変換せず、文字列全体で大文字小文字を区別して比較する。未設定 (`nullptr`) と設定済み空文字列は ON。値がちょうど `0`、`off`、`false`、`no` のいずれかなら OFF。それ以外はすべて ON で、`1`、`true`、`OFF`、`False`、先頭や末尾に空白のある値、`0anything` も ON になる。値域・数値妥当性の検査や trim はない（`engine/include/strata/core/amd_community.hpp:32-37`）。

| 条件 | unset | 設定時に ON | 設定時に OFF |
|---|---|---|---|
| 実行時スイッチ | ON | 上記4文字列以外。例: `1`, `true`, `OFF`, `0anything`, 空白付き ` off` | 完全一致する `0`, `off`, `false`, `no` |
| gfx1010 dot4 の build option | CMake の既定 `ON`（SDWA dot4 をコンパイル） | CMake option が `ON` | CMake option が `OFF` なら `STRATA_AMD_COMMUNITY_DOT_OFF` を定義し portable loop をコンパイル。実行時環境変数では切り替わらない |

CMake option が `OFF` でも、実行時スイッチは rocBLAS table と QSA selector の判定に残る。反対に CMake option が `ON` の build で実行時スイッチだけを OFF にしても、gfx1010 のコンパイル済み SDWA dot4 は残る（`engine/CMakeLists.txt:110-113`, `engine/include/strata/core/amd_community.hpp:39-47, 69-78`）。

## 有効になる条件

- **gfx1010 dot4:** HIP 互換 intrinsic の対象 build で gfx1010 をコンパイルし、CMake option を `ON` にして SDWA sequence を含めていること。実行時 OFF はこの命令列を除去しない。CMake option `OFF` または `STRATA_GFX1012_PORTABLE_DOT` 定義時は portable loop になる（`engine/include/strata/hip_compat/intrinsics.hpp:26-56`）。
- **gfx1030 rocBLAS table:** HIP build で `STRATA_ROCBLAS_AVAILABLE` が有効で、`STRATA_ROCBLAS_TUNING` が空でないパスを指し、runtime arch と rocBLAS version が community table の `gfx1030` / `5.4.0.ad84daa81c` または `gfx1030` / `5.2.0.dabb6df2b98-dirty` に一致し、実行時スイッチが ON であること。table が存在して読み込めても、shape に対応する tuned row がなければ既定 kernel を使う。実際の f16 GEMM 呼び出しには prompt の FP16 経路も必要（`engine/src/prefill/gemm.cu:563-624, 626-676, 1460-1471`, `engine/include/strata/core/amd_community.hpp:49-73`; `STRATA_HIP_PROMPT_F16` の経路は `engine/src/prefill/gemm.cu:681-709`）。arch または version が一致しない表、別の rocBLAS build、別 arch はこの community gate の対象外であり、この変数がそれらの table を無効化するわけではない。
- **gfx103x QSA selector:** HIP の QSA block-score path で、runtime device が gfx103x、かつ `STRATA_SELECT_SIMT` が未設定のときに限り、ON が simt2 (`2`) の既定値を選ぶ。gfx103x 以外ではこの既定値を選ばない。`STRATA_SELECT_SIMT` は未設定なら `-1`、設定されていれば先頭文字が `1` / `2` の場合にその mode、それ以外（空文字も含む）は `0` として static cache されるため、明示値は community 既定値より優先する。未設定の community 既定 simt2 は、`STRATA_SELECT_ALT_MIN_TOKENS` が未設定 / 空文字なら既定しきい値を使い、空でない値は `atoll` で変換する。変換結果が負なら既定値へ戻り、非負ならその値が下限になる。既定下限を使う場合、reach が 28,672 token 未満なら tiled scorer を使わず fallback する。`STRATA_SELECT_SIMT=2` が明示された場合はこの community 既定下限を適用しない（`engine/src/kernels/cuda/qsa_select.cu:2326-2348`）。
- Server / CLI 固有の別判定はない。エンジンプロセスの環境を読む。ソース内にこの変数の子プロセス転送・上書き処理は見つからなかった。`STRATA_SELECT_SIMT` は QSA のみ、`STRATA_ROCBLAS_TUNING` と FP16 prompt 経路は rocBLAS table のみを左右する。

## 実行時の詳細

共通判定 `strata::amd_community::tuning_on()` は関数呼び出しごとに `getenv` する。gfx1010/gfx103x の起動時説明は `apply_arch_defaults()` から出力され、モデル生成側では GPU device properties の取得後に呼ばれる（`engine/include/strata/core/amd_community.hpp:32-37, 80-105`, `engine/src/core/arch_defaults.cpp:302-306`, `engine/src/program/generate.cpp:4288-4321`）。この説明行自体は環境値を cache しない。

QSA 経路では `STRATA_SELECT_SIMT` と `tuning_on()` の結果を `qsa_block_scores_tc()` 内の関数ローカル `static` に保存する。したがって最初の呼び出し後にプロセス環境を変更しても、この経路の選択には反映されない。実行時変数が未設定で gfx103x の既定 simt2 を使う場合は 28,672 token の下限があり、条件を満たさない呼び出しは tiled scorer を使わず false を返して呼び出し側の別経路へ進む。simt2 を実行した後の CUDA/HIP API エラーは `qsa_block_scores (simt2): ...` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:2326-2363`）。

rocBLAS 経路では、`Gemm::init()` / external handle 設定時に `create_rocblas_state()` が `STRATA_ROCBLAS_TUNING` を読み、そのとき `tuning_on()` で community table を許可するか判定する。状態は Gemm ごとに保持される。shape ごとの solution pick は map に cache され、solution が3回拒否されるとその shape は以後 default kernel に切り替わる（`engine/src/prefill/gemm.cu:563-624, 628-675, 793-798, 854-878`）。起動後の環境変更を Gemm state や shape cache が再評価する保証はなく、QSA のように変数値を static cache する実装とも異なる。

## ログと測定値

`apply_arch_defaults()` は対象世代について stderr に1行出す。gfx1010 では build 側で dot4 が無効なら `strata: AMD community tuning (STRATA_AMD_COMMUNITY_TUNING=0 turns it off): off in this build (gfx1010 dot4: portable loop)`、build には SDWA が入っていて実行時値が OFF なら `... set to 0, but this gfx1010 build has the SDWA dot4 compiled in; rebuild with -DSTRATA_AMD_COMMUNITY_TUNING=OFF to drop it` を出す。gfx103x は ON/OFF と QSA selector の扱いを説明し、gfx1030 ON の場合は table の対象 version と `STRATA_ROCBLAS_TUNING` への依存も表示する。gfx1010/gfx103x 以外ではこの行を出さない（`engine/include/strata/core/amd_community.hpp:80-104`, `engine/src/core/arch_defaults.cpp:302-306`）。

community table を実行時 OFF にしてロード対象とした場合は `prefill gemm: the rocBLAS table for %s / %s is community-made and STRATA_AMD_COMMUNITY_TUNING=0; rocBLAS's default kernels run` を stderr に出し、既定 kernel に進む。rocBLAS handle / version / HIP device の照会失敗、table の読込失敗も、それぞれ理由を stderr に出して default kernels に fallback する。tuned solution の拒否は shape ごとに最大3回試し、3回目は理由を stderr に出して以後その shape の default kernel を使う（`engine/src/prefill/gemm.cu:567-603, 661-675`）。

`docs/AMD_HIP.md:714-733` は4変更をコミュニティ測定として記載し、gfx1010 の dot4 は実行時環境変数で戻せない旨も記載しており、ソースの build/runtime 分離と一致する。そこにある速度・一致率・KL 値は寄稿者の測定値で、Strata 側では再現していないと明記されているため、この文書では性能値として一般化しない。

## 根拠

- 読み取り・完全一致判定・runtime gate・起動説明: `engine/include/strata/core/amd_community.hpp:32-105`
- gfx1010 の build option と device code 分岐: `engine/CMakeLists.txt:107-113`, `engine/include/strata/hip_compat/intrinsics.hpp:26-56`
- 起動時ログの呼び出し: `engine/src/core/arch_defaults.cpp:302-306`, `engine/src/program/generate.cpp:4288-4321`
- rocBLAS table の条件・fallback・shape cache: `engine/src/prefill/gemm.cu:563-675, 793-798, 854-878, 1460-1471`
- QSA selector の値優先・cache・token 条件・実行: `engine/src/kernels/cuda/qsa_select.cu:2313-2363`
- 設計説明との照合: `docs/AMD_HIP.md:714-733`
