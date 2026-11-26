# `STRATA_SCORES_DX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の実験的な long-context decode 選択経路で、QSA の block score 計算に `block_scores_dx_kernel` を使うかを制御する。通常の warp scorer と同じ score bits を作る実装として記述されているが、スイッチが選ぶのは scorer だけで、top-k 側は別の `STRATA_TOPK_MULTI` 判定で切り替わる。`STRATA_SCORES_DX=1` だけでは long-context 経路自体は有効にならない。通常の `qsa_block_scores` や prompt の active-block 呼び出しからはこの変数を参照しない。実読取は `engine/src/kernels/cuda/qsa_select.cu:3111-3115`、呼び出し条件は同 `:3248-3256`、long API の説明は `engine/include/strata/kernels/qsa_select.hpp:97-108`。

全参照を確認したところ、上記の実装読み取りに加え、`engine/src/kernels/qsa_select_long_parity.cpp:181-186` は parity 用実行ファイルの前提条件として値を読み、未設定または先頭文字が `1` でない場合に診断を出して終了する。CMake の `:164-165` はそのテストプロセスへ値を設定する。`docs/OLDER_GPUS.md:189`、header の `:103`、kernel の `:1619,3109` は説明コメントであり、`terminal/data/settings-register.json` は設定レジストリの項目であって、いずれも engine の実行時読み取り箇所ではない。

## 値と判定

CUDA の `STRATA_EXPERIMENTAL_SM60` ビルドに含まれる判定では、関数内 static 値として最初の呼び出し時に読み取る。未設定または空文字列は `-1`（自動選択）。それ以外は `atoi` で先頭から整数に変換する。文字列全体の妥当性検査はなく、先頭の空白・符号と数字の後ろの文字は `atoi` の規則に従う。整数として始まらない文字列は 0 となり明示的 OFF 扱いになる。

| 条件 | unset / 空文字 | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| CUDA + `STRATA_EXPERIMENTAL_SM60` | 自動: compute capability 6.x、または後述の Volta 既定条件で有効 | `atoi` 結果が正（例 `1`, `2`, `1tail`, ` 1`）なら全対応 CUDA device で許可 | `atoi` 結果が 0（例 `0`, `00`, `false`, `x1`）なら無効。負値は明示 OFF ではなく自動判定へ戻る |
| HIP、または `STRATA_EXPERIMENTAL_SM60` なし | この環境変数を読む DX 判定コードはコンパイルされない | 該当なし | DX 経路を利用しない |

判定は `env == 0` なら即座に OFF、それ以外は `env > 0 || pascal` である。そのため負値（例 `-1`）は自動判定と同じであり、値の範囲 clamp はない。設定の再読込はなく、プロセス起動後に環境を書き換えても判定には反映されない。根拠: `engine/src/kernels/cuda/qsa_select.cu:3111-3132`。

## 有効になる条件

- CUDA backend かつ `STRATA_EXPERIMENTAL_SM60` を有効にしてビルドされていること。この macro は CUDA backend の CMake option が ON のとき定義される。HIP や通常の release build にはこのコードがない（`engine/cmake/backends/cuda.cmake:28-29,76-80`; `engine/src/kernels/cuda/qsa_select.cu:3108,3172`）。
- Long-context verifier 経路が選ばれて `qsa_block_scores_long` を呼ぶこと。Verifier は `STRATA_SELECT_LONG` が有効で、window の `pos0 + T` が `STRATA_SELECT_LONG_AT` 以上のとき long variant を選ぶ。`STRATA_SELECT_LONG` は値の先頭文字が `1` の場合に ON となり、build が対応しない場合は警告して無視する。既定の threshold は 65,536 cells。根拠: `engine/src/core/verify.cpp:195-219,3710-3715,3837-3839`。
- DX scorer 呼び出し時に `nq > 0`、geometry が対応値、`STRATA_SCORES_MULTI` が ON、`nq <= MQ`（上限 8）、かつ `active_blocks <= 0` であること。どれかを満たさなければ通常の `qsa_block_scores` へ進む。従って `STRATA_SCORES_MULTI=0` も DX を迂回させる。根拠: `engine/src/kernels/cuda/qsa_select.cu:3248-3256`; `engine/src/kernels/cuda/qsa_select.cu:1607-1609,2194-2205`。
- 自動判定の対象は compute capability 6.x と、`sm70_default_on` が true の compute capability 7.0。Volta 既定は `STRATA_SM70_PERF` が未設定または先頭文字が `0` 以外で、かつ `STRATA_DEFAULTS` が厳密に `026` でない場合に限る。正の `STRATA_SCORES_DX` はこの GPU 世代既定を上書きし、DX を CUDA device 全般で許可する。根拠: `engine/src/kernels/cuda/qsa_select.cu:2155-2161,3121-3132`。
- device 取得に失敗した場合は無効。compute capability 属性取得に失敗すると自動選択は false となり、SM 数取得失敗時も false となる。正値指定で GPU 世代条件を上書きしても、SM 数が正であることは必要。根拠: `engine/src/kernels/cuda/qsa_select.cu:3116-3132`。

## 実行時の詳細

Verifier は long variant の window graph を選び、その実行時に `qsa_block_scores_long` を呼ぶ。ここで条件を満たすと `qsa_block_scores_dx` が環境値と device を判定し、成功すれば `scores_dx_launch` から query 数に対応した `block_scores_dx_kernel<NQ>` を launch した後、tail block 用 kernel も launch する。nq が 1〜7 なら同数の template、8 なら `<8>` を使う。DX 判定が false のときは通常の `qsa_block_scores` に fallback する。Verifier の long variant 自体は `STRATA_SELECT_LONG` で選ばれ、`STRATA_SCORES_DX` はその内部の scorer を選択する追加スイッチである（`STRATA_TOPK_MULTI` は top-k 側の独立したスイッチ）。根拠: `engine/src/core/verify.cpp:2266-2276`; `engine/src/kernels/cuda/qsa_select.cu:3111-3155,3157-3170,3248-3256`。

環境値は `scores_dx_device` の function-local `static const int` に一度保存される。device ID ごとの compute capability と SM 数は呼び出し thread ごとの `thread_local` cache に保持され、別 device に切り替わると更新される。occupancy は device index と NQ ごとの thread-local 配列に cache され、occupancy 問い合わせ失敗または 0 の場合は 2 CTA/SM を代用する。これらの cache と環境値はプロセス起動後の環境変更を反映しない。根拠: `engine/src/kernels/cuda/qsa_select.cu:3111-3129,3134-3149`。

DX kernel は tile ごとに query と pooled key を読み、block score を出力する。code comment は通常の scorer と bit-for-bit 同じ演算順を目指す実装と説明し、header も同一 score bits と記載する。選択された scorer の後にはどちらの経路も tail block scorer を実行する（`engine/src/kernels/cuda/qsa_select.cu:1617-1627,1633-1653,3152-3170`; `engine/include/strata/kernels/qsa_select.hpp:102-104`）。

## ログと測定値

成功時にこの変数専用の有効化ログはない。device 取得や属性取得に失敗した場合も DX判定は false/fallback となり、ここでは理由ログを出さない。kernel launch 後の CUDA error があれば stderr に `qsa_block_scores (dx): %s\n` を出し、`exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:3116-3128,3167-3170`）。

`docs/OLDER_GPUS.md:184-192` は long-context select の組合せについて、4 枚の GP100、experts resident、`--pipeline-windows 3` で 400 token decode / 115K context が 51.0 から 52.5 tok/s、64K 未満では変化なしという作者測定を記載する。これは `STRATA_TOPK_MULTI` と `STRATA_SCORES_DX` を含む組合せの説明で、DX 単独の測定ではなく、同文書は Strata 側で未測定としている。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:3111-3132` — 値の読み取り、変換、GPU 判定と cache。
- `engine/src/kernels/cuda/qsa_select.cu:3134-3170,3248-3256` — launch、エラー経路、通常 scorer への fallback。
- `engine/src/core/verify.cpp:195-219,2266-2276,3710-3715,3837-3839` — long-context 経路と threshold。
- `engine/cmake/backends/cuda.cmake:28-29,76-80` — build macro の定義。
- `engine/include/strata/kernels/qsa_select.hpp:97-108` — long API と適用条件の概要。
- `docs/OLDER_GPUS.md:184-192` — 組合せ機能についての作者測定値と未測定の注記。
