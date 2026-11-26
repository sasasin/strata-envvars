# `STRATA_SELECT_SIMT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の prompt block-score 計算で、通常の warp scorer の代わりに FP32 tiled scorer を選ぶための実行時スイッチです。モード `1` は通常の tiled scorer、`2` は simt2 scorer を選びます。score の加算順序が warp scorer と異なるため bitwise 一致は保証されず、後続の top-k が選ぶ block と attention の入力が変わることがあります。QSA の block score 計算を行う prefill 経路が対象で、Metal にはこの dispatch がありません。[`qsa_select.cu:2309-2312,2320-2364,2377-2422`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu) [`qsa_select.hpp:71-76`](../../../../Niko1221/Strata/engine/include/strata/kernels/qsa_select.hpp) [`prefill.cpp:5387-5393,9450-9457`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

## 値と判定

両 backend は `getenv` の戻り値の**先頭 1 文字だけ**を見ます。文字列全体の数値 parse はせず、空白除去、大文字小文字変換、後続文字の検査もありません。未設定は `nullptr` として別扱いです。CUDA の pre-sm_80 経路では未設定をモード `0`、HIP では未設定を gfx103x の community default 判定へ渡します。[`qsa_select.cu:2326-2329,2395-2399`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)

| backend / 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA、実行 GPU が sm_80 未満 | `0`（warp scorer） | 先頭が `1` なら mode 1、`2` なら mode 2 | 空文字、`0`、`true`、` 1`、その他。mode 0 となり warp scorer へ戻る |
| CUDA、実行 GPU が sm_80 以上 | この変数を読まない。tensor-core scorer の経路 | 該当なし | 設定値にかかわらずこの dispatch では選択されない |
| HIP、gfx103x（gfx103 で始まる arch 名）、`STRATA_AMD_COMMUNITY_TUNING` が on | mode 2。ただし後述の既定 minimum token 数を満たす場合 | 先頭 `1` / `2` で各モードを指定 | 空文字、`0`、`true`、その他は mode 0 にして community default を上書き |
| HIP、上記以外の GPU または community tuning が off | `0`（warp scorer） | 先頭が `1` / `2` なら各モード | 空文字、`0`、`true`、その他は mode 0 |

たとえば `1anything` は mode 1、`2 ` は mode 2、`10` は mode 1、`0anything`・`true`・` 2`・空文字は mode 0 です。負値や数値範囲の検査はありません。HIP の gfx103x unset default は、`STRATA_AMD_COMMUNITY_TUNING` が未設定または空文字なら on です。同変数の値が正確に `0`、`off`、`false`、`no` のいずれか（大文字小文字を区別）なら off、それ以外の設定値なら on です。[`qsa_select.cu:2326-2331`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu) [`amd_community.hpp:32-37,75-78`](../../../../Niko1221/Strata/engine/include/strata/core/amd_community.hpp)

## 有効になる条件

- 呼び出し側が QSA の block score を計算する prompt 経路であること。主経路は `qsa_block_scores_tc` を試し、`false` なら通常の `qsa_block_scores` に fallback します。[`prefill.cpp:5371-5393,9445-9457`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)
- CUDA では実行 GPU の compute capability が sm_80 未満であること。sm_80 以上では tensor-core scorer に進み、この変数は参照されません。`STRATA_QSA_WARP=1` または `select` が sm_80 以上のデバイスを pre-sm_80 用分岐として扱わせる場合は、同分岐でこの変数が評価されます。[`qsa_select.cu:2377-2399`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)
- HIP では `qsa_block_scores_tc` の geometry 条件（`nq > 0`、indexer geometry 一致、`nq <= 65535`）を満たすこと。mode 1/2 の scorer が返す `false` は呼び出し側で warp scorer へ fallback します。[`qsa_select.cu:2309-2312,2340-2344,2352-2365`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)
- HIP の gfx103x で unset から選ばれる mode 2 は、`STRATA_SELECT_ALT_MIN_TOKENS` が未設定または空であれば `28,672` token 以上の active reach でのみ実行されます。それより短ければ `qsa_block_scores_tc` が `false` を返して warp scorer になります。`STRATA_SELECT_ALT_MIN_TOKENS` に非空値があれば `atoll` で変換し、0 以上ならその値が threshold です。無効な非空文字列は 0、`12tail` は 12、負値は既定 threshold 選択へ戻ります。利用者が `STRATA_SELECT_SIMT` を設定した場合（先頭が `0` や無効値でも）、この既定 threshold は適用されません。[`qsa_select.cu:2332-2344`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)
- HIP の gfx12 で `STRATA_SELECT_WMMA` の先頭文字が `0` 以外かつ空でない場合、SIMT 分岐は WMMA scorer と共存できない条件になり、mode 1/2 より WMMA scorer が優先されます。`STRATA_SELECT_WMMA` の設定有無判定と gfx12 判定は別です。[`qsa_select.cu:2313-2319,2345-2375`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)
- prefill 側で `STRATA_SELECT_OLD` が設定されている場合は（空文字を含め値を問わず）tensor-core/SIMT dispatch を呼ばず、warp scorer に進みます。条件を満たした `STRATA_SELECT_TWO_PASS` 経路が `tp_call` となった場合も、その呼び出しの主 scorer は two-pass です。[`prefill.cpp:5356-5389,9450-9455`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)
- Metal backend はこの `qsa_block_scores_tc` dispatch を呼ばない条件でコンパイルされます。[`prefill.cpp:5355-5357`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

## 実行時の詳細

HIP では `qsa_block_scores_tc` が geometry 検査を通過した最初の呼び出しで、関数内 `static` として変数・community default・minimum token 設定を読み込みます。CUDA では sm_80 未満のデバイス分岐に初めて入った時に `static` として読み込みます。いずれもプロセス内で一度だけで、読み込み後に環境を変更しても再評価されません。HIP の device architecture 判定は device ごとに cache されます。[`qsa_select.cu:2316-2339,2348-2349,2378-2399`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)

mode 1 は `block_scores_simt`、mode 2 は `block_scores_simt2_kernel`（HIP/CUDA とも 32×128 tile）を起動し、tail block は warp scorer と同じ演算の `block_scores_tail_kernel` で計算します。CUDA の pre-sm_80 mode 2 だけは `STRATA_SIMT2_TILE` を `atoi` し、値が 2 なら 64×64 tile、それ以外は 32×128 tile を使います。選択結果は後続の `qsa_block_topk` に渡されます。[`qsa_select.cu:2352-2364,2392-2422`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu) [`prefill.cpp:5390-5393,9454-9457`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

mode 1/2 が geometry、minimum-token 条件、SIMT2 grid 条件などを満たさず `false` を返す場合は呼び出し元が warp scorer を使います。CUDA scorer の kernel launch error は stderr に `qsa_block_scores (simt): ...` または `qsa_block_scores (simt2): ...` を出して `exit(1)` します。HIP で代替 scorer が実際に起動すると、プロセス内最初の一度だけ `qsa select: FP32 tiled scorer (STRATA_SELECT_SIMT=<mode>), tiles <...>` を stderr に出します。mode が選ばれず fallback するとこの行は出ません。[`qsa_select.cu:2340-2363,2415-2422`](../../../../Niko1221/Strata/engine/src/kernels/cuda/qsa_select.cu)

## ログと測定値

この文書では性能値を記載しません。Strata の設計資料・測定記録に値はありますが、本調査では変数の現行コード挙動の説明に必要な条件付き性能値を採用していません。HIP の実行ログと launch error は「実行時の詳細」に記載したとおりです。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2309-2365,2377-2445` — backend ごとの値判定、cache、device/threshold 条件、scorer dispatch とエラー経路。
- `engine/include/strata/core/amd_community.hpp:32-37,75-78` — HIP gfx103x の unset default と別環境変数による上書き条件。
- `engine/src/prefill/prefill.cpp:5355-5393,9445-9457` — prompt 経路での scorer 呼び出し、優先経路、fallback と top-k への接続。
- `engine/include/strata/kernels/qsa_select.hpp:71-76` — scorer の役割と数値特性。
