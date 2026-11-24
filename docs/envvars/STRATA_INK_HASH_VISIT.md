# `STRATA_INK_HASH_VISIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA の Inkling-2 `InkCudaRunner` が `STRATA_INK_HASH` による診断ハッシュを有効にしているとき、内部段階（projection、attention、MoE）の追加ハッシュを取る visit 番号を選びます。全 visit の主要ハッシュ（`visit * 4 + 0..3`）や最終 norm の記録を選別する変数ではなく、それらに加えて選択した visit のスロット 193〜211 を記録するための診断設定です。`engine/src/inkling2/cuda/ink_runner.cuh:1795-1800,3228,3408-3420,3442,3513-3517,3535-3536,3649`

この変数を読むのは CUDA 側だけです。HIP 側の `ink_hip_backend.hip.cpp` は `STRATA_INK_HASH` を読みますが、`STRATA_INK_HASH_VISIT` の参照はありません（候補名の全参照検索結果）。したがって HIP で visit を選ぶ設定としては機能しません。`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742`

## 値と判定

`InkCudaRunner::init` がまず `std::getenv("STRATA_INK_HASH")` を調べ、その文字列の先頭が `'1'` の場合だけ本変数を読みます。親変数が未設定、空文字、または先頭が `'1'` 以外なら、本変数は読まれず既定の visit 0 が残ります。親変数の判定は文字列全体ではなく先頭 1 文字です。`engine/src/inkling2/cuda/ink_runner.cuh:1797-1799,2100-2108`

親スイッチが有効な場合、本変数が未設定なら `dbg_tap_visit` の初期値 `0` を使い、設定されていれば `std::atoi` の結果を代入します。`atoi` は整数全体の厳密な検証ではなく、先頭の空白と符号を許し、先頭の10進数部分を変換し、数字に続く文字列は無視します。数字で始まらない値や空文字は 0 になります。したがって、たとえば `2` と `2tail` は visit 2、`0anything`・`true`・空文字は visit 0、`-1` は visit に一致しません。値の範囲検査、clamp、無効値の警告はありません。整数表現の範囲外の入力についてはコードに独自の扱いがありません。`engine/src/inkling2/cuda/ink_runner.cuh:1798,2105`

| 条件 | 未設定 | 追加段階ハッシュを選ぶ値 | 選択に一致しない値の例 |
|---|---|---|---|
| CUDA `InkCudaRunner`、`STRATA_INK_HASH` の先頭が `1` | visit 0 | `0`〜`47` の整数。`atoi` がその値に変換する文字列 | `-1`、`48`、`x`（`atoi` 結果 0 のため visit 0 には一致） |
| 上記以外（親変数が未設定・空文字・先頭が `1` 以外、または HIP） | 本変数は未読。CUDA では既定 visit 0 | 該当なし | 本変数の値は選択に影響しない |

visit の番号は `run_visit` が 0〜47 と定義され、forward は prelude 0〜5、core 6〜41、coda 42〜47 を処理します。値 48 以上や負数でも拒否ログはなく、追加段階ハッシュの `visit == dbg_tap_visit` 条件に一致しません。`engine/src/inkling2/cuda/ink_runner.cuh:3120-3123,3568-3575,3588-3623,3626-3634`

## 有効になる条件

- CUDA の Inkling-2 `InkCudaRunner::init` を通る実行経路であること。本変数の実読み取りは `engine/src/inkling2/cuda/ink_runner.cuh` にあります。
- `STRATA_INK_HASH` が設定され、先頭文字が `1` であること。この条件を満たさない場合、本変数は読まれず、診断用 GPU バッファもこの処理では確保されません。`engine/src/inkling2/cuda/ink_runner.cuh:2100-2108`
- 対象 visit が実際に実行されること。通常の 48-visit forward では 0〜47 が実行対象です。早期 pass 終了などで visit が実行されなければ、その visit の追加段階ハッシュもありません。`engine/src/inkling2/cuda/ink_runner.cuh:3588-3634`
- ハッシュ関数は `rows` が 1〜16 のときだけカーネルを起動します。forward の表示関数も `M` が 1〜16 の場合に限って `[HASH]` 行を出力するため、より大きい batch ではこの診断出力は抑制されます。`engine/src/inkling2/cuda/ink_runner.cuh:1801-1814`
- HIP 実装には本変数の読み取りも visit 選択処理もありません。HIP の親ハッシュ設定から本変数の動作を推定することはできません。`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742`

## 実行時の詳細

値は `InkCudaRunner::init` ごとに一度読み、runner の `dbg_tap_visit` フィールドに保存します。各 visit の `run_visit` 中ではその保存値と現在の `visit` を比較し、一致したときだけ attention projection、attention 結果、MoE routing/top-k などの追加スロット 193〜211 をハッシュします。設定値を実行中に変更しても、すでに初期化済みの runner の選択値は変わりません。CUDA backend の runner 初期化が割当て再試行ループで再実行される場合は、新しい `init` で再読込されます。`engine/src/inkling2/cuda/ink_runner.cuh:1797-1800,2105,3228,3408-3420,3442,3513-3517,3535-3536` `engine/src/inkling2/cuda/ink_cuda_backend.cu:303-322`

訪問番号は `emit_48_visits` が `run_visit` に渡します。主要な per-visit ハッシュと最終 norm のハッシュは本変数に関係なく記録対象ですが、追加スロット 193〜211 は選択 visit に限られます。`dbg_hash` は GPU カーネルを stream に投入し、forward 経路の `dbg_hash_print` は stream を同期して結果を stderr に出します。`engine/src/inkling2/cuda/ink_runner.cuh:1801-1814,3419-3420,3535-3536,3649`

## ログと測定値

ハッシュ出力は stderr の `[HASH]` 行で、行頭以降に `tag`, `B`, `row`, `pos`, `dep`, `anchor`, `tok`, `par` と 212 個の16進スロット値を出します。逐次 forward 経路では `tag` が `fwd`、tree verify 経路では `tree` です。通常の逐次 forward と tree 経路はハッシュ表示関数を呼びますが、`forward_batched` には `dbg_hash_print` の呼び出しがないため、この経路では本変数が選んだ追加スロットも出力されません。`M` が 1〜16 以外の場合も表示関数の早期 return により行は出ません。`engine/src/inkling2/cuda/ink_runner.cuh:1805-1814,3691-3696,3816-3820,3823-3864`

無効な文字列や範囲外値に対する専用ログ、終了、fallback はありません。`atoi` 後の値が実行中の visit と一致しなければ追加段階スロットは書き込まれず、他のハッシュ有効条件を満たしていれば通常のハッシュ処理は継続します。`engine/src/inkling2/cuda/ink_runner.cuh:2105,3228,3408-3420,3442,3513-3517,3535-3536`

## 根拠

- `engine/src/inkling2/cuda/ink_runner.cuh:1795-1814` — 診断フィールド、カーネル投入条件、`[HASH]` の stderr 出力。
- `engine/src/inkling2/cuda/ink_runner.cuh:2100-2108` — 親変数による有効化、本変数の `getenv` / `atoi` 読み取り。
- `engine/src/inkling2/cuda/ink_runner.cuh:3120-3123,3228,3408-3420,3442,3513-3517,3535-3536` — visit 範囲と選択 visit に限る追加ハッシュ。
- `engine/src/inkling2/cuda/ink_runner.cuh:3568-3634,3649,3691-3696,3816-3820,3823-3864` — forward/tree/batched 経路と出力呼び出し。
- `engine/src/inkling2/cuda/ink_cuda.cuh:157-162` — Inkling-2 の visit 数が 48 である定義。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:303-322` — backend の runner 初期化と再試行ループ。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742` — HIP は親ハッシュ設定を読むが visit 変数は読まないこと。
