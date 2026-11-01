# `STRATA_SCORES_DX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の長文脈 decode 用 QSA スコア計算で、warp shuffle を使わない `block_scores_dx_kernel` を選ぶ設定です。これは `STRATA_SELECT_LONG` が有効なときに選択される decode 窓経路のスコア部分だけを制御します。別段の top-k カーネルを選ぶ `STRATA_TOPK_MULTI` とは独立しており、この変数を無効にしても long-context 経路の top-k は条件を満たせば使用されます。

この読み取りとカーネルは `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA ビルドに限られます。通常のビルド、HIP、Metal、SYCL ではこの実装がコンパイルされず、この変数を読む Strata 本番コードはありません。

## 値と判定

値は `std::getenv` で取得し、未設定または空文字なら既定値を表す `-1` にします。それ以外の文字列は `std::atoi` で整数に変換します。文字列全体の検証はありません。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | 既定動作。実行 GPU が compute capability 6.x の場合に有効 |
| `0`、または `atoi` の結果が 0 になる非空文字列（例: `abc`, `0tail`） | 無効 |
| 正数（例: `1`, `2`, `1tail`） | 実行 GPU の compute capability にかかわらず有効 |
| 負数（例: `-1`, `-2`） | 既定値と同様に compute capability 6.x の場合だけ有効 |

したがって、文字列の完全一致で `1` を要求する設定ではありません。空白や符号なども `atoi` の規則で変換され、変換結果が 0 なら無効です。値の範囲 clamp や無効値の警告はありません。実装は最初にこの関数を呼んだときに値を読み、`static const` に保存します。以後、プロセス内で環境を書き換えても再評価しません。

根拠: `src/kernels/cuda/qsa_select.cu:2966-2989`。

## 有効になる条件

値判定に加えて、次の条件が必要です。

- CUDA かつ `STRATA_EXPERIMENTAL_SM60` を定義したビルドであること。CMake option は既定 OFF です（`CMakeLists.txt:236,280-284`）。このビルド設定により該当 CUDA カーネルがコンパイルされます。
- `STRATA_SELECT_LONG` の先頭文字が `1` で、long-context select が有効であること。未設定や先頭文字が `1` 以外の値は無効です。実験ビルドでない場合は `strata verify: STRATA_SELECT_LONG=1 needs the CUDA build with STRATA_EXPERIMENTAL_SM60; ignored` を stderr に出して無視します（`src/core/verify.cpp:176-193`）。
- 検証窓が `pos0 + T >= STRATA_SELECT_LONG_AT` を満たすこと。しきい値の既定値は 65,536 cells、空文字または未設定も既定値です。値は `atoll` で変換され、`0` なら常に条件を満たします（`src/core/verify.cpp:194-200,3076-3078`）。
- スコア関数呼び出しで `nq` が 1〜8、`active_blocks <= 0`、QSA geometry が `IDX_DIM` / `IDX_HEADS` / `R` と一致し、`STRATA_SCORES_MULTI` が有効であること。どれかを満たさないと通常の `qsa_block_scores` に fallback します（`src/kernels/cuda/qsa_select.cu:3104-3113`）。
- 実行デバイスの取得と属性取得が成功し、multiprocessor 数が正であること。未設定・空文字・負数では compute capability major が 6 のときだけ、それ以外の正数では任意の CUDA compute capability で有効です。条件を満たさない場合、DX scorer は `false` を返して通常の scorer に fallback します（`src/kernels/cuda/qsa_select.cu:2974-2989`）。

`STRATA_SCORES_MULTI` は DX dispatch の追加条件です。これは未設定なら ON、設定時は `atoi(value) != 0` で判定され、判定結果を初回呼び出し時にキャッシュします（`src/kernels/cuda/qsa_select.cu:1547-1549`）。このため `STRATA_SCORES_DX=1` でも `STRATA_SCORES_MULTI=0` や `abc` では DX scorer が呼ばれません。

## 実行時の詳細

Verifier は長文脈用窓を capture する際、`STRATA_SELECT_LONG` と窓位置から `sel_long_` を決めます。選択された窓では QSA スコア計算と top-k の両方を long 用関数へ送り、スコア関数側がさらに上記条件を検査します。DX scorer を選んだ場合、最大 8 query に対して `block_scores_dx_kernel` を起動し、その後 tail block 用 kernel を起動します（`src/core/verify.cpp:3076-3084,1775-1781`; `src/kernels/cuda/qsa_select.cu:2991-3028,3104-3113`）。

デバイス番号、compute capability、multiprocessor 数は thread-local cache に保存され、デバイス切替時に再取得されます。環境変数の整数値は関数内 static に保存されます。`cudaGetDevice` または device 属性取得に失敗した場合は CUDA エラー状態をクリアして fallback し、その失敗をこの経路専用の警告として出しません。DX または tail kernel の起動後に `cudaGetLastError` が失敗した場合は `qsa_block_scores (dx): <CUDA error string>` を stderr に出して `exit(1)` します（`src/kernels/cuda/qsa_select.cu:2974-2988,3024-3027`）。

この実装のスコアは通常の scorer と同じ bits になる設計としてコメント・API に記載されています（`include/strata/kernels/qsa_select.hpp:81-88`, `src/kernels/cuda/qsa_select.cu:1557-1567`）。Strata の `docs/OLDER_GPUS.md` は `STRATA_SELECT_LONG` の説明中で `STRATA_SCORES_DX=0` がスコア側の半分を止めると記し、4 枚の GP100 での decode 測定を報告しています。ただしこれは `STRATA_SELECT_LONG` 全体の測定であり、この変数単独の効果を分離した測定ではありません（`docs/OLDER_GPUS.md:178-185`）。

## 根拠

- 全候補参照: `docs/OLDER_GPUS.md:183`, `include/strata/kernels/qsa_select.hpp:87`, `src/kernels/cuda/qsa_select.cu:1559,2967-2972`, `src/kernels/qsa_select_long_parity.cpp:181-185`, `CMakeLists.txt:549-550`。
- 本番の環境読み取りは `src/kernels/cuda/qsa_select.cu:2971` のみ。`src/kernels/qsa_select_long_parity.cpp` はテスト専用で、テスト実行前提確認と診断メッセージに使っています。CMake は parity テストに `STRATA_SCORES_DX=1` を設定しますが、これは製品ランタイムの設定ではありません（`CMakeLists.txt:539-550`）。
- 本番分岐と fallback: `src/kernels/cuda/qsa_select.cu:2974-2989,3104-3113`。
