# `STRATA_QSA_CLUSTER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の block top-k 選択で、条件を満たす CUDA 呼び出しを 1 query あたり 8 CTA の thread-block cluster kernel に振り分けるかを制御する。未設定または整数として 0 以外なら cluster 経路を試し、0 として読まれる値なら通常の dispatcher へ進む。対象は選択 kernel の実装経路であり、CLI 引数で選択 ID を指定する設定ではない。CUDA の cluster kernel は通常経路と同じ ID を出力する設計である（`engine/src/kernels/cuda/qsa_select.cu:1388-1412`, `1464-1484`, `engine/include/strata/kernels/qsa_select.hpp:87-91`）。

この値が効くのは `qsa_block_topk` が呼ばれる場合だけである。例えば decode の QSA fast-select 経路と prefill の選択処理が同 dispatcher を呼ぶ（`engine/src/core/layer.cpp:1277-1282`, `engine/src/prefill/prefill.cpp:5392-5393`）。QSA を使わない処理や、別の選択経路だけを通る処理では参照されない。

## 値と判定

CUDA と SYCL の `qsa_block_topk` は、`nq <= 0` の早期 return の後に `std::getenv` を行い、設定値を `std::atoi(v) != 0` で判定する（`engine/src/kernels/cuda/qsa_select.cu:3016-3028`, `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2024`）。文字列全体の検証や範囲チェックはなく、`atoi` が読む整数部分が非 0 かどうかで決まる。

| ビルド・経路 | unset | cluster を有効にする例 | cluster を無効にする例 |
|---|---|---|---|
| CUDA dispatcher | 有効（`v == nullptr`） | `1`, `2`, `-1`, `1tail`, `  +1` | `0`, `00`, 空文字, `0tail`, `true`, `false`, `tail` |
| SYCL dispatcher | 判定値は有効 | CUDA と同じ整数判定 | CUDA と同じ整数判定。ただし後述のとおり実装が cluster を起動しない |
| HIP (`__HIPCC__`) | この変数を読まない | 該当なし | cluster 実装が常に `false` を返す |

空文字は未設定ではなく `atoi("") == 0` と判定される。先頭の空白と符号は整数変換に従い、整数の後ろの文字は無視されるため `1tail` は有効、`0tail` は無効となる。数字として読めない文字列は 0 になる。大文字小文字を区別する文字列比較はない。ソースに明示的な許容範囲・clamp・無効値警告はない（同上）。

同じ `qsa_block_topk` には `STRATA_TOPK_OLD` もあり、これは値ではなく `getenv(...) != nullptr` で判定する。空文字や `0` を設定した場合も旧 reference kernel を選び、`!old` 条件によって cluster 経路を抑止する（`engine/src/kernels/cuda/qsa_select.cu:3016-3029`, `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2025`）。

## 有効になる条件

- `qsa_block_topk` が正の query 数で呼ばれること。`nq <= 0` は環境変数の初期化より前に return する（`engine/src/kernels/cuda/qsa_select.cu:3016-3028`）。
- decode の `--no-fast-select` が選ばれていると `layer.cpp` は `qsa_block_topk` ではなく旧 index/top-k 経路を呼ぶため、この変数はその decode 経路では評価されない（`engine/src/program/generate.cpp:4267`, `6111`, `engine/src/core/layer.cpp:1277-1282`）。
- CUDA では `STRATA_TOPK_OLD` が未設定で、呼び出し query 数が `CL_MAXQ` 以下であること。`CL_MAXQ` は 16（`engine/src/kernels/cuda/qsa_select.cu:1410-1412`, `3029`）。
- CUDA device の確認に成功し、device index が 0–63、実 device または `STRATA_EMULATE_CC` による compute capability major が 9 以上で、対象 kernel の PTX version と binary version もそれぞれ 90 以上であること（`engine/src/kernels/cuda/qsa_select.cu:2485-2505`, `engine/include/strata/core/emulate.hpp:58-77`）。つまり GPU の能力だけでなく cluster 対応コードを含む build も必要。`STRATA_EMULATE_CC` は 75–119 の整数を受け付ける実装で、値を設定しても build の PTX/binary 条件は別途残る。
- CUDA で `idx_block == R`、`cap >= qsa_selection_width(kTopkMaxCells, s)`、`max_blocks > 0` を満たすこと。また必要な shared memory（`ceil(max_blocks / 8) * sizeof(uint32_t)`）を設定でき、8 CTA の active cluster を少なくとも 1 個 resident にできること（`engine/src/kernels/cuda/qsa_select.cu:2485-2487`, `2506-2525`）。
- HIP では cluster 関数は常に `false` を返す。SYCL 生成実装でも dispatcher は値を読むが、cluster 関数の現在の `#if 1` 分岐は引数を未使用にして `false` を返すため、値にかかわらず通常の選択経路に進む（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1907-1914`, `2018-2026`）。
- この dispatcher には OS や server-mode による追加の分岐はない。実際の適用範囲は QSA の block top-k dispatcher が呼ばれる経路で決まる（`engine/src/kernels/cuda/qsa_select.cu:3016-3030`, `engine/src/core/layer.cpp:1277-1282`）。

上記の CUDA 条件を満たさないときは cluster 関数が `false` を返し、dispatcher は後続へ進む。`STRATA_QSA_CLUSTER=0` も cluster を抑止するだけで、CUDA の split dispatch 条件（`active_blocks <= 0` など）を満たせば split 経路が残り、それ以外も geometry に応じた register / wide kernel に進む。したがって、この変数だけで QSA top-k の最適化全体を無効化するわけではない（`engine/src/kernels/cuda/qsa_select.cu:3032-3041`, `3075-3105`）。

## 実行時の詳細

CUDA では `qsa_block_topk` 内の関数ローカル `static const bool cluster` が、最初の正 query 数の呼び出しで値を読み、その後プロセス内で保持される。SYCL 生成実装にも同じ関数ローカル static がある。したがって、初回評価後に環境変数を変更しても、その dispatcher の判定には反映されない（`engine/src/kernels/cuda/qsa_select.cu:3016-3028`, `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2024`）。CUDA の GPU/build 適合性と shared-memory opt-in 量も device index ごとの static 配列に保持される。判定に使う `STRATA_EMULATE_CC` も helper 内で static cache される（`engine/src/kernels/cuda/qsa_select.cu:2491-2525`, `engine/include/strata/core/emulate.hpp:58-65`）。

値が有効でも cluster 実行条件を満たさなければ理由ログを出さずに次の dispatcher 経路へ進む。cluster launch が成功すると dispatcher はその場で return する。launch 自体が失敗した場合は `qsa_block_topk cluster: %s\n` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:3029-3030`, `2533-2541`）。SYCL の cluster stub は `false` を返し、追加の cluster 固有ログを出さない（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1907-1914`, `2018-2026`）。

## ログと測定値

`docs/DETAILS.md:1621` は 0.1.36 の RTX 5070 / Q2_0 の記録として、decode 出力が 4K で 89 → 93.5 tok/s、128K で 64.5 → 76.4 tok/s と記載し、`STRATA_QSA_CLUSTER=0` を cluster decode kernel を切る設定として挙げる。ただし同じ記録は `STRATA_ARGMAX_MULTI` も同時に列挙しており、これら数値から `STRATA_QSA_CLUSTER` 単独の寄与は分離できない。実測値をこの変数単独の効果とは扱わない。

## 根拠

- CUDA の値判定と dispatch: `engine/src/kernels/cuda/qsa_select.cu:3016-3041`
- CUDA cluster の geometry・device/build・shared-memory 条件と launch: `engine/src/kernels/cuda/qsa_select.cu:2479-2542`
- cluster kernel 定数と出力処理: `engine/src/kernels/cuda/qsa_select.cu:1410-1412`, `1464-1484`
- 後続の split / reference / register / wide 経路と失敗ログ: `engine/src/kernels/cuda/qsa_select.cu:3032-3105`
- SYCL の値判定と cluster stub: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1907-1914`, `2012-2026`
- 呼び出し例: `engine/src/core/layer.cpp:1277-1282`, `engine/src/prefill/prefill.cpp:5392-5393`
- Strata の測定記録: `docs/DETAILS.md:1621`
