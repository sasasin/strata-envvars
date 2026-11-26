# `STRATA_HC_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Verifier の hyper-connection multi-token read で使う実装 variant の上限を指定する。`0` は既存の plain read、`1` は split read まで、既定値および `2` は staged read までを候補にし、各カードで plain read とビット単位比較した自己検査に通った最も新しい候補を使う。CUDA/HIP は `fused_gr_check`、SYCL は同関数に加えて `STRATA_HC_CHECK` の設定が必要。これは `STRATA_GR_V3` の別経路を選ぶ設定ではなく、通常の multi read が `launch_multi` に進む場合に適用される。`engine/src/kernels/cuda/fused_gr.cu:1156-1173,1778-1814,4424-4425,4732-4811`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1510-1525,1893-1924,3794-3841`。

`plain` は従来の norm / down projection の読み方、`split` は norm を token と stream ごとに分けて down projection は plain の kernel、`staged` は split norm に加え down projection の activations を先行 staging する読み方。CUDA の sm_80 未満と HIP では staged の staging は非同期ではなく通常コピーになる。実装コメントでは各 variant は plain と同じ演算順序で結果をビット一致させ、自己検査も 1〜8 token、pending write の有無を含めて比較する設計になっている。`engine/src/kernels/cuda/fused_gr.cu:1156-1173,4561-4566,4666-4703`。

## 値と判定

値は `std::getenv` で読み、数値変換はしない。`env_variant` は文字列の先頭 1 文字だけを見る。unset と空文字、`0` 以外で先頭が `0`、先頭が `1`、それ以外で結果が分かれる。大文字小文字や空白の trim、残りの文字列の検証はない。`engine/src/kernels/cuda/fused_gr.cu:1933-1940,4732-4739`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2115-2122,3794-3802`。

| 条件 | unset | 有効になる値（例） | その他の値（例） |
|---|---|---|---|
| CUDA/HIP `fused_gr_check` がそのカードで実行される | staged を希望。検査後、staged が不一致なら split、split も使えなければ plain | 先頭 `0`（`0`, `0abc`）= plain。先頭 `1`（`1`, `1abc`）= split まで。先頭 `2`（`2`, `2abc`）= staged まで | 空文字・`true`・`false`・` 1`・`x` は staged を希望（不正値として拒否しない）。検査結果により split/plain へ fallback |
| SYCL `STRATA_HC_CHECK` が設定済みで、そのカードで `fused_gr_check` が実行される | staged を希望。検査後の fallback は上と同じ | CUDA/HIP と同じ先頭文字判定 | CUDA/HIP と同じ先頭文字判定 |
| SYCL `STRATA_HC_CHECK` が未設定 | `STRATA_HC_SPLIT` にかかわらず plain に固定 | なし | なし |
| `fused_gr_variant` が未検査カードで直接呼ばれる | plain | 先頭が `1` または `2` のときだけ `env_variant` を使う | unset、空、先頭 `0`、`true`、空白始まり等は plain |

検査を実施する経路では、先頭 `1` のとき staged は候補外で split が不一致なら plain。先頭 `2` や既定値相当では staged を優先し、staged が不一致なら split、split も不一致なら plain。先頭 `0` の場合はこの環境変数の自己検査を省いて plain を選ぶ。CUDA/HIP の分岐は `engine/src/kernels/cuda/fused_gr.cu:4756-4803`、SYCL は `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3807-3834`。

## 有効になる条件

- CUDA/HIP の通常 verifier 初期化は `Verifier::init` からカードごとに `fused_gr_check` を呼ぶ。Linux HIP の integrated gfx11 ではモデルの expert arena 読み込み前に先行して同関数を呼ぶ場合がある。`engine/src/core/verify.cpp:956-969`、`engine/src/program/generate.cpp:8507-8514`。
- SYCL は `STRATA_HC_CHECK` が未設定なら plain を cache して終了する。設定有無だけを見るため、空文字でも設定済み扱いになる。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3804-3819`。
- 自己検査はカードごとに一度。結果は `g_variant[64]` に保存し、以後の呼び出しはその値を返すため、実行中に環境を変更しても検査済みカードの選択は変わらない。`engine/src/kernels/cuda/fused_gr.cu:1942-1943,4732-4757`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2124-2125,3794-3814`。
- 未検査時に `fused_gr_variant` が直接使われる場合、先頭 `1` / `2` だけが split / staged を要求し、それ以外は plain。標準の verifier 初期化より前に read が呼ばれる経路や診断用途では、この fallback が適用される。`engine/src/kernels/cuda/fused_gr.cu:4732-4739`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3794-3802`。
- `STRATA_GR_V3` の read が先に選ばれる場合、および HIP gfx906 で `STRATA_GR_SPLIT=1` の専用経路が使われる場合は `launch_multi(..., fused_gr_variant(), ...)` に到達せず、この選択は使われない。`engine/src/kernels/cuda/fused_gr.cu:4351-4398,4399-4425`。
- staged の down kernel は `s_down != nullptr`（Q8 weight）なら選ばず、split 側の down kernelを使う。`engine/src/kernels/cuda/fused_gr.cu:1808-1814`。

## 実行時の詳細

CUDA/HIP では `fused_gr_check` が希望 variant を読み、plain と split/staged を合成入力で実行して比較する。比較対象は 1〜8 token、pending write の有無を含み、`lo`、`rs`、inject、mixed、R output を比較する。検査用メモリ確保や kernel 実行に失敗した場合は plain を選ぶ。検査実施後に `g_variant` へ保存し、通常の `fused_gr_read_multi` はその値で `launch_multi` の norm/down kernel を切り替える。`engine/src/kernels/cuda/fused_gr.cu:4561-4662,4666-4727,4790-4811,4424-4429,1778-1814`。

SYCL も同様にカードごとに `STRATA_HC_CHECK` を確認してから候補を検査し、結果を cache する。変数未設定なら検査を実施せず plain を保存する。自己検査中の SYCL exception は `exc.what()` とファイル・行を stderr に出して `exit(1)` する。通常の検査失敗は plain に fallback し、診断文を出す。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3786-3789,3804-3841`。

## ログと測定値

CUDA/HIP は plain を選ぶと `strata hc: CUDA%d: the hyper-connection read runs as the plain one (STRATA_HC_SPLIT=0)` を stderr に出す。split/staged 検査では、検査を実行できない場合に `strata hc: CUDA%d: the check of split/staged could not run (%s)`、不一致候補には `strata hc: CUDA%d: the %s read differs from the plain read on this card - not used: %s`、最終選択には `strata hc: CUDA%d: the hyper-connection read runs as ...` を出す。SYCL は `STRATA_HC_CHECK` 未設定時にはログを出さず return する。`engine/src/kernels/cuda/fused_gr.cu:4776-4809`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3810-3818,3828-3841`。

`docs/DETAILS.md` は `STRATA_GR_V3` など他の hyper-connection read 経路を記載するが、`STRATA_HC_SPLIT` の選択・測定値は記載していない。ソースコメントには RTX 4080 SUPER での過去の norm 時間比較があるものの、現行設定下の測定条件一式は示されないため、本書では性能値を一般化しない。`docs/DETAILS.md:1301-1304`、`engine/src/kernels/cuda/fused_gr.cu:1164-1165`。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:1933-1943,4732-4811` — CUDA/HIP の値判定、未検査 fallback、自己検査、選択とログ。
- `engine/src/kernels/cuda/fused_gr.cu:1156-1173,1778-1814,4561-4727` — variant の処理差、実 read での適用、自己検査内容。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2115-2125,3794-3841` — SYCL の値判定、`STRATA_HC_CHECK` 条件、fallback とログ。
- `engine/src/core/verify.cpp:956-969`、`engine/sycl/src/core/verify.cpp:625-638`、`engine/src/program/generate.cpp:8507-8514` — 初期化時の呼び出し時期。
- `engine/src/kernels/cuda/fused_gr.cu:4351-4429` — 別 read 経路との優先関係と通常 read の呼び出し。
- `docs/DETAILS.md:1301-1304` — 詳細資料との照合。
